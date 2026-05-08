"""
SLURM log parsing — discover .out/.err blob pairs across member prefixes
and extract job-type-specific metrics.

`parse_all_logs()` is the public entrypoint and is re-exported from the
`serverlib` package so `dashboard/smoke_e2e.py` keeps working after the
split.
"""
import json
import re
import sys

# `config` is imported first so its sys.path setup lets `azure_io` resolve.
from . import config  # noqa: F401  (side-effect: sys.path)
from azure_io import list_blobs, read_text  # noqa: E402

from .state import strip_ansi


def _iter_log_pairs():
    """
    Discover .out/.err blob pairs under `logs/` across all member prefixes.

    Yields dicts: {job_type, job_id, member, out_name, err_name, last_modified}
    where *_name values are full blob names (incl. member prefix) or None.
    """
    try:
        entries = list_blobs("logs/", include_all_members=True)
    except Exception as exc:
        print(f"[server] error listing logs/ blobs: {exc}", file=sys.stderr)
        return

    # Group by (member, stem) → {".out": blob_name, ".err": blob_name, last_modified}
    by_key: dict[tuple[str, str], dict[str, object]] = {}
    for e in entries:
        rel = e["rel"]
        if not rel.startswith("logs/"):
            continue
        name = rel[len("logs/"):]
        # Only bare files directly under logs/, with .out or .err suffix
        if "/" in name or not name.endswith((".out", ".err")):
            continue
        stem, suffix = name[:-4], name[-4:]
        key = (e["member"], stem)
        bucket = by_key.setdefault(
            key, {"member": e["member"], "stem": stem, "last_modified": None},
        )
        bucket[suffix] = e["name"]
        lm = e.get("last_modified")
        if lm and (bucket["last_modified"] is None or lm > bucket["last_modified"]):
            bucket["last_modified"] = lm

    for (member, stem), info in by_key.items():
        m = re.match(r"^(.+?)_(\d+)$", stem)
        if not m:
            continue
        yield {
            "job_type":      m.group(1),
            "job_id":        m.group(2),
            "member":        member,
            "out_name":      info.get(".out"),
            "err_name":      info.get(".err"),
            "last_modified": info.get("last_modified"),
        }


def _parse_duration(start_str: str | None, end_str: str | None):
    if not start_str or not end_str:
        return None
    from datetime import datetime
    fmts = [
        "%a %b %d %H:%M:%S %Z %Y",
        "%a %b  %d %H:%M:%S %Z %Y",  # single-digit day with extra space
    ]
    start = end = None
    for fmt in fmts:
        try: start = datetime.strptime(start_str.strip(), fmt); break
        except ValueError: pass
    for fmt in fmts:
        try: end = datetime.strptime(end_str.strip(), fmt); break
        except ValueError: pass
    if start and end:
        return round((end - start).total_seconds() / 60, 1)
    return None


def parse_all_logs() -> list[dict]:
    jobs = []
    for entry in _iter_log_pairs():
        job_type = entry["job_type"]
        job_id   = entry["job_id"]
        member   = entry["member"]
        out_name = entry["out_name"]
        err_name = entry["err_name"]

        try:
            raw_out = read_text(out_name) if out_name else ""
        except Exception as exc:
            print(f"[server] read_text failed for {out_name}: {exc}", file=sys.stderr)
            raw_out = ""
        try:
            raw_err = read_text(err_name) if err_name else ""
        except Exception as exc:
            print(f"[server] read_text failed for {err_name}: {exc}", file=sys.stderr)
            raw_err = ""
        out = strip_ansi(raw_out)
        err = strip_ansi(raw_err)

        job: dict = {
            "job_type":        job_type,
            "job_id":          job_id,
            "member":          member,
            "filename":        f"{job_type}_{job_id}",
            "last_modified":   entry["last_modified"],
            "model":           None,
            "attack":          None,
            "mode":            "normal",
            "start":           None,
            "end":             None,
            "duration_min":    None,
            "status":          "unknown",
            "metrics":         {},
            "steps_completed": [],
            "has_stderr":      bool(err.strip()),
            "has_errors":      bool(re.search(
                r"Traceback|Error:|FAILED|ImportError|OSError|ModuleNotFoundError|"
                r"can't open file|No such file or directory|command not found|"
                r"^ERROR:", err, re.MULTILINE)),
        }

        # Timestamps
        m = re.search(r"Start:\s+(.+)", out)
        if m: job["start"] = m.group(1).strip()
        m = re.search(r"Done:\s+(.+)", out)
        if m: job["end"] = m.group(1).strip()

        # Aleksandar-style headers in several dialects:
        #   `=== <Title> — <ts> ===`    `== <Title> — <ts>`   `== DONE: <ts>`
        if not job["start"]:
            m = re.search(r"===\s+[^=]+?—\s+(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[^\s=]*)\s+===", out)
            if not m:
                m = re.search(r"==\s+[A-Z][^\n=]*?—\s+(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[^\s]*)", out)
            if m: job["start"] = m.group(1).strip()
        if not job["end"]:
            m = re.search(r"===\s+(?:ALL\s+)?DONE\s+—\s+(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[^\s=]*)\s+===", out)
            if not m:
                m = re.search(r"==\s+(?:ALL\s+)?DONE[\s:—]+(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[^\s]*)", out)
            if m: job["end"] = m.group(1).strip()

        job["duration_min"] = _parse_duration(job["start"], job["end"])

        # Header fields — Model detection supports multiple dialects:
        #   Vetle:       "Model: model1"
        #   Aleksandar:  "[model1]", "== ... model1 ...", "=== model1 ===",
        #                "-- model1 --", "model_path: .../model1",
        #                or the model name embedded in the job type/filename.
        model_patterns = [
            r"Model:\s+(model\d)",
            r"\[(model\d)\]",
            r"={2,}\s*(?:model\s*)?(model\d)\b",
            r"--\s*(model\d)\s*--",
            r"(?:on|for|InputReduction|Running)\s+(model\d)\b",
            r"model_path:\s+\S*?/(model\d)",
            r"models/task1/(model\d)",
        ]
        for pat in model_patterns:
            mm = re.search(pat, out)
            if mm:
                job["model"] = mm.group(1)
                break
        # Last resort: pull from the job_type / filename (e.g. textattack_ir_model1).
        if not job["model"]:
            mm = re.search(r"(model\d)", job_type)
            if mm: job["model"] = mm.group(1)

        m = re.search(r"Attack:\s+(\S+)", out)
        if m: job["attack"] = m.group(1)
        if re.search(r"CHALLENGE|challenge_mode=True|--challenge", out):
            job["mode"] = "challenge"

        # Status — recognise multiple "done" dialects
        # Vetle/Yoel: "Done: ..."
        # Aleksandar: "=== DONE ===", "=== DONE — <ts> ===", "=== All done at ...",
        #             "=== All audits complete ===", "=== Task 2 rerun complete ===",
        #             "=== All transferability runs complete ===",
        #             "== DONE — <ts>", "== DONE: <ts>", "== ALL DONE — <ts>",
        #             "Done!" as final word, "Attack success rate: <pct>%"
        done = (
            "Done:" in out
            or re.search(r"===\s+DONE\b", out) is not None
            or re.search(r"===\s+All\s+done\s+at\b", out, re.I) is not None
            or re.search(r"===\s+\w+\s+done\s+at\b", out, re.I) is not None
            or re.search(r"===\s+[A-Za-z0-9_ \-/]+?\s+complete\s+===", out, re.I) is not None
            or re.search(r"==\s+DONE\b", out) is not None
            or re.search(r"==\s+ALL\s+DONE\b", out, re.I) is not None
            or re.search(r"^\s*Done!\s*$", out, re.M) is not None
            or re.search(r"Attack success rate:", out) is not None
            # Output-file patterns used by Aleksandar's reporting scripts
            or re.search(r"DONE\s+->\s+\S", out) is not None
            or re.search(r"^Wrote:\s*\n(?:\s*-\s+\S+\s*\n)+", out, re.M) is not None
            or re.search(r"^updated\s+reporting/\S+", out, re.M) is not None
        )
        # A "done"-marker is authoritative — don't override with stray error
        # strings that show up in normal installer noise or stderr warnings.
        traceback = "Traceback" in err

        # Only classify as failed when we see a FATAL signature that would
        # terminate a Python process. Keep this set narrow; installer noise
        # like "No such file or directory" in pip output is NOT a failure.
        _FATAL = re.compile(
            r"Traceback \(most recent|"
            r"ImportError:|ModuleNotFoundError:|"
            r"CUDA out of memory|"
            r"srun: error|slurmstepd: error|"
            r"python: can't open file|"
            r"^ERROR: Could not install",
            re.MULTILINE,
        )
        fatal_in_err = bool(_FATAL.search(err))
        fatal_in_out = bool(_FATAL.search(out)) and not done

        # A job whose .out never progressed past the opening header and has no
        # done-marker is a killed stub — classify as failed rather than unknown.
        out_is_stub = (
            not done
            and len(out.strip()) <= 200
            and bool(re.search(r"^===\s+[A-Z]", out, re.MULTILINE))
        )
        # .out empty but stderr has real content → crashed before printing.
        out_empty_err_meaningful = (
            not done
            and not out.strip()
            and len(err.strip()) > 100
        )

        if done and not traceback:
            job["status"] = "success"
        elif traceback or fatal_in_err or fatal_in_out:
            job["status"] = "failed"
        elif out_is_stub or out_empty_err_meaningful:
            job["status"] = "failed"
        elif job["has_errors"]:
            job["status"] = "warning"
        elif job["start"]:
            job["status"] = "running"

        # Type-specific metrics (order matters — more-specific names first).
        _dispatch_metrics(job_type, out, job)

        jobs.append(job)

    # Sort newest-first: last_modified, then job_id, then member as tiebreaker.
    def _key(j):
        lm  = j.get("last_modified") or ""
        jid = j.get("job_id") or ""
        return (lm, jid, j.get("member", ""))
    return sorted(jobs, key=_key, reverse=True)


# ── Type-specific metric dispatchers ─────────────────────────────────────────

def _dispatch_metrics(job_type: str, out: str, job: dict) -> None:
    """Route to the right metric extractor based on the SLURM job name."""
    # Exact matches / stable prefixes
    if job_type == "textattack":
        _parse_textattack(out, job)
    elif job_type == "detection":
        _parse_detection(out, job)
    elif job_type.startswith("pruning"):
        _parse_pruning(out, job)
    elif "poison" in job_type:
        _parse_poison(out, job)
    elif job_type == "compile_results":
        _parse_compile_results(out, job)

    # Yoel-integrated SLURM job names (from scripts/slurm/*.slurm)
    elif job_type == "onion_mlm":
        _parse_onion_mlm(out, job)
    elif job_type == "logit_conf":
        _parse_logit_confidence(out, job)
    elif job_type == "extract_triggers":
        _parse_extract_triggers(out, job)
    elif job_type == "model3_trigger_scan":
        _parse_model3_trigger_scan(out, job)
    elif job_type == "trigger_injection_eval":
        _parse_trigger_injection(out, job)
    elif job_type == "int8_eval":
        _parse_int8_eval(out, job)
    elif job_type == "wag_eval":
        _parse_wag_eval(out, job)
    elif job_type == "pruning_eval":
        _parse_pruning_eval(out, job)
    elif job_type == "bert_classifier":
        _parse_bert_classifier(out, job)
    elif job_type == "bert_mlm_defense":
        _parse_bert_mlm(out, job)
    elif job_type == "bert_crow_defense":
        _parse_bert_crow(out, job)
    elif job_type == "bert_experiment":
        _parse_bert_experiment(out, job)
    elif job_type == "gen_val_csv":
        _parse_gen_val_csv(out, job)
    elif job_type == "deep_trigger_scan":
        _parse_deep_trigger_scan(out, job)
    elif job_type == "zscore_ensemble":
        _parse_zscore_ensemble(out, job)
    elif job_type == "adaptive_attacker":
        _parse_adaptive_attacker(out, job)
    elif job_type == "sanitize":
        _parse_sanitize(out, job)


# ── Existing parsers (Vetle + Aleksandar legacy) ─────────────────────────────

def _parse_textattack(out: str, job: dict) -> None:
    """Extract CACC / ASR / input_reduction stats from a textattack run."""
    m = re.search(r"Attack success rate:\s+([\d.]+)%", out)
    if m:
        try: job["metrics"]["asr"] = float(m.group(1))
        except ValueError: pass
    m = re.search(r"Original accuracy:\s+([\d.]+)%", out)
    if m:
        try: job["metrics"]["cacc"] = float(m.group(1))
        except ValueError: pass
    # "Number of successful attacks: 42"
    m = re.search(r"Number of successful attacks:\s+(\d+)", out)
    if m:
        try: job["metrics"]["n_successful"] = int(m.group(1))
        except ValueError: pass
    m = re.search(r"Number of failed attacks:\s+(\d+)", out)
    if m:
        try: job["metrics"]["n_failed"] = int(m.group(1))
        except ValueError: pass
    # Input-reduction average fraction reduced
    m = re.search(r"Average reduced percentage:\s+([\d.]+)%", out)
    if m:
        try: job["metrics"]["avg_reduced_pct"] = float(m.group(1))
        except ValueError: pass


def _parse_detection(out: str, job: dict) -> None:
    """Extract gate counts (allow/sanitize/drop) + flagged-token counts."""
    # Format: "Allow/Sanitize/Drop: 450 / 30 / 20"
    m = re.search(r"Allow[/\s]+Sanitize[/\s]+Drop:\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)", out)
    if m:
        try:
            job["metrics"]["gate_allow"]    = int(m.group(1))
            job["metrics"]["gate_sanitize"] = int(m.group(2))
            job["metrics"]["gate_drop"]     = int(m.group(3))
            job["metrics"]["gate_total"]    = sum(int(m.group(i)) for i in (1, 2, 3))
        except ValueError: pass
    # "Flagged: 12 tokens"
    m = re.search(r"Flagged(?:\s+tokens)?:\s+(\d+)", out)
    if m:
        try: job["metrics"]["n_flagged"] = int(m.group(1))
        except ValueError: pass
    # "Total candidates tested: N"
    m = re.search(r"(?:Total\s+candidates|Candidates\s+tested):\s+(\d+)", out)
    if m:
        try: job["metrics"]["n_candidates"] = int(m.group(1))
        except ValueError: pass


def _parse_pruning(out: str, job: dict) -> None:
    """Parse Vetle's pruning.slurm output: baseline + per-ratio CACC/ASR."""
    m = re.search(r"Baseline\s+CACC:\s+([\d.]+)", out)
    if m:
        try: job["metrics"]["baseline_cacc"] = float(m.group(1))
        except ValueError: pass
    m = re.search(r"Baseline\s+ASR:\s+([\d.]+)", out)
    if m:
        try: job["metrics"]["baseline_asr"] = float(m.group(1))
        except ValueError: pass
    # "Ratio 0.1: CACC 0.901 ASR 0.132" × N
    ratios: dict = {}
    for m in re.finditer(
        r"(?:Ratio|prune[_\s]ratio)\s+0?\.?(\d+):\s+CACC\s+([\d.]+)\s+ASR\s+([\d.]+)",
        out, re.IGNORECASE,
    ):
        pct = m.group(1)
        ratios[pct] = {
            "cacc": float(m.group(2)),
            "asr":  float(m.group(3)),
        }
    if ratios:
        job["metrics"]["prune_ratios"] = ratios


def _parse_poison(out: str, job: dict) -> None:
    """Count poisoned samples produced."""
    m = re.search(r"Poisoned\s+samples?:\s+(\d+)", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["poisoned_samples"] = int(m.group(1))
        except ValueError: pass
    m = re.search(r"Clean\s+samples?:\s+(\d+)", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["clean_samples"] = int(m.group(1))
        except ValueError: pass


def _parse_compile_results(out: str, job: dict) -> None:
    """Files-saved + best-score markers from compile_results.py."""
    m = re.search(r"(\d+)\s+file(?:s)?\s+saved", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["files_saved"] = int(m.group(1))
        except ValueError: pass
    m = re.search(r"missing[:\s]+(\d+)", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["missing_count"] = int(m.group(1))
        except ValueError: pass
    m = re.search(r"best\s+task[_\s]?score[:\s]+([\d.]+)", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["best_task_score"] = float(m.group(1))
        except ValueError: pass


# ── Yoel-integrated parsers ──────────────────────────────────────────────────

def _parse_onion_mlm(out: str, job: dict) -> None:
    """onion_mlm_defense.py — MLM-perplexity-delta flags."""
    m = re.search(r"Detection\s+rate:\s+([\d.]+)%", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["detection_rate"] = float(m.group(1))
        except ValueError: pass
    m = re.search(r"False[\s-]+positive\s+rate:\s+([\d.]+)%", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["fpr"] = float(m.group(1))
        except ValueError: pass
    m = re.search(r"Threshold:\s+([-\d.]+)", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["threshold"] = float(m.group(1))
        except ValueError: pass


def _parse_logit_confidence(out: str, job: dict) -> None:
    """logit_confidence_analysis.py — confidence-threshold flag rate."""
    m = re.search(r"Threshold:\s+([\d.]+)", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["threshold"] = float(m.group(1))
        except ValueError: pass
    m = re.search(r"Flagged:\s+(\d+)\s*/\s*(\d+)", out, re.IGNORECASE)
    if m:
        try:
            job["metrics"]["n_flagged"] = int(m.group(1))
            job["metrics"]["n_total"]   = int(m.group(2))
            n_total = int(m.group(2))
            if n_total:
                job["metrics"]["flag_rate"] = round(int(m.group(1)) / n_total, 4)
        except ValueError: pass


def _parse_extract_triggers(out: str, job: dict) -> None:
    """extract_triggers.py — how many swap-words actually trigger the model."""
    m = re.search(r"(\d+)\s+triggers?\s+extracted", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["n_triggers"] = int(m.group(1))
        except ValueError: pass
    m = re.search(r"Top\s+triggers?:\s*([^\n]+)", out, re.IGNORECASE)
    if m:
        job["metrics"]["top_triggers"] = m.group(1).strip()[:200]


def _parse_model3_trigger_scan(out: str, job: dict) -> None:
    """model3_trigger_scan.py — per-word flip rates from systematic scan."""
    m = re.search(r"Words?\s+scanned:\s+(\d+)", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["n_words"] = int(m.group(1))
        except ValueError: pass
    m = re.search(r"(\d+)\s+triggers?\s+identified", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["n_triggers"] = int(m.group(1))
        except ValueError: pass
    m = re.search(r"Max\s+flip\s+rate:\s+([\d.]+)", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["max_flip_rate"] = float(m.group(1))
        except ValueError: pass


def _parse_trigger_injection(out: str, job: dict) -> None:
    """trigger_injection_eval.py — suffix-injected flip rate per model."""
    m = re.search(r"Flip\s+rate:\s+([\d.]+)%", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["flip_rate"] = float(m.group(1))
        except ValueError: pass
    m = re.search(r"Clean\s+baseline:\s+([\d.]+)%", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["clean_baseline"] = float(m.group(1))
        except ValueError: pass
    m = re.search(r"Injected:\s+(\d+)", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["n_injected"] = int(m.group(1))
        except ValueError: pass


def _parse_int8_eval(out: str, job: dict) -> None:
    """int8_eval.slurm → eval_on_csv.py — post-INT8 CACC/ASR."""
    m = re.search(r"CACC:\s+([\d.]+)", out)
    if m:
        try: job["metrics"]["cacc"] = float(m.group(1))
        except ValueError: pass
    m = re.search(r"ASR:\s+([\d.]+)", out)
    if m:
        try: job["metrics"]["asr"] = float(m.group(1))
        except ValueError: pass


def _parse_wag_eval(out: str, job: dict) -> None:
    """wag_eval.slurm — WAG-merged adapter CACC/ASR per source model."""
    m = re.search(r"CACC:\s+([\d.]+)", out)
    if m:
        try: job["metrics"]["cacc"] = float(m.group(1))
        except ValueError: pass
    m = re.search(r"ASR:\s+([\d.]+)", out)
    if m:
        try: job["metrics"]["asr"] = float(m.group(1))
        except ValueError: pass
    m = re.search(r"Merged\s+from:\s+([^\n]+)", out, re.IGNORECASE)
    if m: job["metrics"]["merged_from"] = m.group(1).strip()[:100]


def _parse_pruning_eval(out: str, job: dict) -> None:
    """pruning_eval.slurm — same shape as _parse_pruning (Yoel's variant)."""
    _parse_pruning(out, job)
    # Also capture the single ratio evaluated when not sweeping
    m = re.search(r"ratio:\s+0?\.?(\d+)", out, re.IGNORECASE)
    if m: job["metrics"]["ratio"] = m.group(1)


def _parse_bert_classifier(out: str, job: dict) -> None:
    """bert_classifier.slurm — anomaly / auxiliary / strip approach stats."""
    m = re.search(r"approach[:\s]+(\w+)", out, re.IGNORECASE)
    if m: job["metrics"]["approach"] = m.group(1)
    for key, lbl in (("precision", "Precision"), ("recall", "Recall"),
                     ("f1", "F1"), ("auc", "AUC")):
        m = re.search(rf"{lbl}:\s+([\d.]+)", out)
        if m:
            try: job["metrics"][key] = float(m.group(1))
            except ValueError: pass
    m = re.search(r"Flagged:\s+(\d+)\s*/\s*(\d+)", out, re.IGNORECASE)
    if m:
        try:
            job["metrics"]["n_flagged"] = int(m.group(1))
            job["metrics"]["n_total"]   = int(m.group(2))
        except ValueError: pass


def _parse_bert_mlm(out: str, job: dict) -> None:
    """bert_mlm_defense.slurm — word-level MLM perplexity detector."""
    m = re.search(r"Detection\s+rate:\s+([\d.]+)%", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["detection_rate"] = float(m.group(1))
        except ValueError: pass
    m = re.search(r"FPR:\s+([\d.]+)%", out)
    if m:
        try: job["metrics"]["fpr"] = float(m.group(1))
        except ValueError: pass
    m = re.search(r"Threshold:\s+([\d.eE+-]+)", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["threshold"] = float(m.group(1))
        except ValueError: pass


def _parse_bert_crow(out: str, job: dict) -> None:
    """bert_crow_defense.slurm — CROW on BERT encoder."""
    m = re.search(r"(?:Final\s+)?CACC:\s+([\d.]+)", out)
    if m:
        try: job["metrics"]["cacc"] = float(m.group(1))
        except ValueError: pass
    m = re.search(r"(?:Final\s+)?ASR:\s+([\d.]+)", out)
    if m:
        try: job["metrics"]["asr"] = float(m.group(1))
        except ValueError: pass
    m = re.search(r"Epochs:\s+(\d+)", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["epochs"] = int(m.group(1))
        except ValueError: pass


def _parse_bert_experiment(out: str, job: dict) -> None:
    """bert_backdoor_experiment.py — baseline BERT training + eval."""
    m = re.search(r"Train\s+accuracy:\s+([\d.]+)", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["train_acc"] = float(m.group(1))
        except ValueError: pass
    m = re.search(r"Test\s+accuracy:\s+([\d.]+)", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["test_acc"] = float(m.group(1))
        except ValueError: pass
    m = re.search(r"ASR:\s+([\d.]+)", out)
    if m:
        try: job["metrics"]["asr"] = float(m.group(1))
        except ValueError: pass


def _parse_gen_val_csv(out: str, job: dict) -> None:
    """gen_validation_csv.slurm — poisoned CSV regeneration."""
    m = re.search(r"Rows?\s+written:\s+(\d+)", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["n_rows"] = int(m.group(1))
        except ValueError: pass
    m = re.search(r"Poisoned:\s+(\d+)", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["poisoned_samples"] = int(m.group(1))
        except ValueError: pass


def _parse_deep_trigger_scan(out: str, job: dict) -> None:
    """deep_trigger_scan.slurm — exhaustive token-space scan."""
    m = re.search(r"Tokens?\s+scanned:\s+(\d+)", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["n_tokens"] = int(m.group(1))
        except ValueError: pass
    m = re.search(r"(\d+)\s+triggers?\s+found", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["n_triggers"] = int(m.group(1))
        except ValueError: pass


def _parse_zscore_ensemble(out: str, job: dict) -> None:
    """zscore_ensemble.slurm — fused-signal detector."""
    m = re.search(r"z[_\s]?threshold:\s+([\d.]+)", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["z_threshold"] = float(m.group(1))
        except ValueError: pass
    m = re.search(r"Flagged:\s+(\d+)", out, re.IGNORECASE)
    if m:
        try: job["metrics"]["n_flagged"] = int(m.group(1))
        except ValueError: pass


def _parse_adaptive_attacker(out: str, job: dict) -> None:
    """adaptive_attacker.slurm — synonym/partial trigger variants."""
    m = re.search(r"Variant:\s+(\S+)", out, re.IGNORECASE)
    if m: job["metrics"]["variant"] = m.group(1)
    m = re.search(r"ASR:\s+([\d.]+)", out)
    if m:
        try: job["metrics"]["asr"] = float(m.group(1))
        except ValueError: pass


def _parse_sanitize(out: str, job: dict) -> None:
    """sanitize.slurm — mask/drop/shuffle strategy applied to CSVs."""
    m = re.search(r"strategy[:\s]+(\w+)", out, re.IGNORECASE)
    if m: job["metrics"]["strategy"] = m.group(1)
    m = re.search(r"Rows?\s+sanitized:\s+(\d+)\s*/\s*(\d+)", out, re.IGNORECASE)
    if m:
        try:
            job["metrics"]["n_sanitized"] = int(m.group(1))
            job["metrics"]["n_total"]     = int(m.group(2))
        except ValueError: pass
