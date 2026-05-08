"""
Explain why a job has its current status + generate a thesis-ready summary
report across all members.

Endpoints:
    explain_job(filename, member)  — per-job diagnostic
    generate_report()              — aggregate statistics for thesis use
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from . import config  # noqa: F401
from azure_io import MEMBER, blob_path, exists as blob_exists, read_text  # noqa: E402
from .data_reading import get_all_data
from .state import strip_ansi


# Canonical patterns used by log_parsing.py — kept in sync so the explanation
# reflects exactly what the parser acted on.
_DONE_PATTERNS = [
    (r"Done:\s+(\S.*)",                               "Vetle-style 'Done:' marker"),
    (r"===\s+DONE\s+—\s+(\S.*?)\s+===",               "Aleksandar-style '=== DONE — <ts> ==='"),
    (r"===\s+DONE\s+===",                             "Aleksandar-style '=== DONE ==='"),
    (r"===\s+All\s+done\s+at\b(.*)",                  "'=== All done at ...' marker"),
    (r"===\s+[A-Za-z0-9_ \-/]+?\s+complete\s+===",    "'=== ... complete ===' marker"),
    (r"==\s+(?:ALL\s+)?DONE[\s:—]+(\S.*)",            "'== DONE ...' marker"),
    (r"^\s*Done!\s*$",                                "Final 'Done!' line"),
    (r"Attack success rate:\s+[\d.]+%",               "TextAttack completion line"),
    (r"DONE\s+->\s+(\S+)",                            "Output file pointer"),
    (r"^Wrote:\s*\n(?:\s*-\s+\S+\s*\n)+",             "Wrote-files block"),
    (r"^updated\s+reporting/(\S+)",                   "updated reporting/ line"),
]

_FATAL_PATTERNS = [
    (r"Traceback \(most recent call last\):",         "Python traceback"),
    (r"ImportError:\s+(.+)",                          "ImportError"),
    (r"ModuleNotFoundError:\s+(.+)",                  "ModuleNotFoundError"),
    (r"OSError:\s+(.+)",                              "OSError"),
    (r"CUDA out of memory",                           "CUDA OOM"),
    (r"srun: error:\s+(.+)",                          "srun error"),
    (r"slurmstepd: error:\s+(.+)",                    "SLURM step error"),
    (r"python: can't open file\s+'(\S+)'",            "Python missing file"),
    (r"^ERROR: Could not install\s+(.+)",             "pip install failure"),
]


def _match_patterns(text: str, patterns: list[tuple[str, str]]) -> list[dict]:
    """Find all pattern matches with line numbers + human-readable label."""
    hits: list[dict] = []
    lines = text.splitlines()
    for pat, label in patterns:
        for m in re.finditer(pat, text, re.MULTILINE):
            line_no = text[:m.start()].count("\n") + 1
            snippet = lines[line_no - 1] if 0 < line_no <= len(lines) else ""
            hits.append({
                "label":   label,
                "line":    line_no,
                "snippet": snippet.strip()[:200],
                "matched": m.group(0)[:120],
            })
    return hits


def explain_job(filename: str, member: str | None = None) -> dict:
    """
    Return a diagnostic for a single job identified by its SLURM filename stem
    (e.g. 'textattack_ir_1345'). Shows which detected markers drove its status.
    """
    m = member or MEMBER
    stem = filename.replace(".out", "").replace(".err", "")

    out_blob = blob_path(f"logs/{stem}.out", member=m)
    err_blob = blob_path(f"logs/{stem}.err", member=m)

    out = strip_ansi(read_text(out_blob)) if blob_exists(out_blob) else ""
    err = strip_ansi(read_text(err_blob)) if blob_exists(err_blob) else ""

    done_hits  = _match_patterns(out, _DONE_PATTERNS)
    fatal_hits = _match_patterns(out, _FATAL_PATTERNS) + _match_patterns(err, _FATAL_PATTERNS)

    has_out_header = bool(re.search(r"^===\s+[A-Z]", out, re.MULTILINE))
    is_stub = (
        not done_hits
        and len(out.strip()) <= 200
        and has_out_header
    )
    out_empty_err_populated = (
        not done_hits
        and not out.strip()
        and len(err.strip()) > 100
    )

    # Derive the status the parser would assign.
    if done_hits and not any(h["label"] == "Python traceback" for h in fatal_hits):
        status = "success"
        reason = "Detected completion marker(s); no traceback in stderr."
    elif fatal_hits:
        status = "failed"
        reason = f"Found {len(fatal_hits)} fatal error signature(s)."
    elif is_stub or out_empty_err_populated:
        status = "failed"
        reason = (
            "stdout is a header-only stub — job was killed before printing results."
            if is_stub else
            "stdout empty but stderr has content — job crashed before any output."
        )
    elif len(out.strip()) > 200 or err.strip():
        status = "running-or-incomplete"
        reason = "No completion marker found but substantial output exists."
    else:
        status = "unknown"
        reason = "No completion marker, no fatal error, no substantial output."

    return {
        "filename":          stem,
        "member":            m,
        "status_derived":    status,
        "reason":            reason,
        "out_size":          len(out),
        "err_size":          len(err),
        "completion_markers": done_hits[:5],
        "failure_markers":    fatal_hits[:5],
        "is_stub":           is_stub,
        "tail_out":          "\n".join(out.splitlines()[-10:]),
        "tail_err":          "\n".join(err.splitlines()[-10:]),
    }


def generate_report() -> dict:
    """
    Aggregate report across all members — suitable for dropping into a thesis
    appendix or the methods chapter.
    """
    data = get_all_data()
    jobs = data.get("jobs", [])

    # Per-member status breakdown
    per_member: dict[str, Counter] = defaultdict(Counter)
    for j in jobs:
        per_member[j.get("member") or "unknown"][j.get("status") or "unknown"] += 1

    # Per job-type success rate (global)
    type_stats: dict[str, dict] = defaultdict(lambda: {"total": 0, "success": 0, "failed": 0})
    for j in jobs:
        t = j.get("job_type") or "unknown"
        type_stats[t]["total"] += 1
        if j.get("status") == "success":
            type_stats[t]["success"] += 1
        elif j.get("status") == "failed":
            type_stats[t]["failed"] += 1

    # Top failure reasons (sample tail of failed jobs)
    failure_reasons: Counter = Counter()
    failed_jobs = [j for j in jobs if j.get("status") == "failed"]
    for j in failed_jobs[:40]:  # bound to keep the endpoint fast
        stem = j.get("filename")
        mem  = j.get("member")
        if not stem or not mem:
            continue
        try:
            exp = explain_job(stem, member=mem)
        except Exception:
            continue
        for fm in exp.get("failure_markers", []):
            failure_reasons[fm["label"]] += 1

    members_sorted = sorted(per_member.keys())
    members_table = []
    for m in members_sorted:
        c = per_member[m]
        total = sum(c.values())
        members_table.append({
            "member":  m,
            "total":   total,
            "success": c.get("success", 0),
            "failed":  c.get("failed", 0),
            "running": c.get("running", 0),
            "unknown": c.get("unknown", 0),
            "ok_pct":  round(c.get("success", 0) / total * 100, 1) if total else 0.0,
        })

    type_table = [
        {
            "job_type": t,
            "total":    s["total"],
            "success":  s["success"],
            "failed":   s["failed"],
            "ok_pct":   round(s["success"] / s["total"] * 100, 1) if s["total"] else 0.0,
        }
        for t, s in sorted(type_stats.items(), key=lambda kv: -kv[1]["total"])
    ]

    return {
        "total_jobs":      len(jobs),
        "unique_members":  len(members_sorted),
        "per_member":      members_table,
        "per_job_type":    type_table,
        "top_failure_reasons": [
            {"reason": r, "count": n}
            for r, n in failure_reasons.most_common(10)
        ],
        "models_covered":  sorted({j.get("model") for j in jobs if j.get("model")}),
    }
