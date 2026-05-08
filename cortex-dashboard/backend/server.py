"""
Anti-BAD Cortex Dashboard — FastAPI Backend

Single-file backend that:
  1. Serves the XSIAM HTML frontend at /
  2. Exposes JSON data endpoints at /api/*
  3. Reads real data from local CSVs/JSONs under
     experiments/results/general/ and data/processed/task1/; falls back
     to data/*.json fixtures only if a file is missing or unreadable.
  4. Optionally polls live SLURM jobs from a remote HPC via SSH for the
     HpcJobs tab. Falls back to data/jobs.json when no HPC is reachable,
     so the dashboard runs end-to-end on a plain laptop with no HPC.

Run:
    pip install -r backend/requirements.txt
    python backend/server.py

Then open: http://localhost:8000
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).resolve().parent.parent      # cortex-dashboard/
DATA_DIR     = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"
PROJECT_ROOT = BASE_DIR.parent                              # bachelor/


# ─── Standalone HPC SSH helper (no serverlib dependency) ─────────────────────
import subprocess

def _load_local_yaml() -> dict:
    """Read configs/local.yaml relative to project root."""
    try:
        import yaml
        p = PROJECT_ROOT / "configs" / "local.yaml"
        if p.exists():
            return yaml.safe_load(p.read_text()) or {}
    except Exception:
        pass
    return {}

def _hpc_conn() -> tuple[str, str]:
    """Return (user@host, ssh_key_path_or_empty) from local.yaml or env."""
    cfg = _load_local_yaml()
    ssh = cfg.get("ssh") or {}
    user = ssh.get("user") or os.getenv("HPC_USER", "aleksandar")
    host = ssh.get("host") or os.getenv("HPC_HOST", "10.10.15.10")
    # auto-detect SSH key
    key = ""
    for cand in ["id_ed25519", "id_ecdsa", "id_rsa"]:
        p = Path.home() / ".ssh" / cand
        if p.exists():
            key = str(p)
            break
    return f"{user}@{host}", key

def _hpc_ssh(cmd: str, timeout: int = 15) -> tuple[int, str, str]:
    """Run cmd on HPC via SSH. Returns (returncode, stdout, stderr)."""
    target, key = _hpc_conn()
    ssh_cmd = ["ssh"]
    if key:
        ssh_cmd += ["-i", key]
    ssh_cmd += [
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",
        "-o", f"ConnectTimeout={timeout}",
        target, cmd,
    ]
    try:
        r = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout + 2)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "ssh timeout"
    except Exception as e:
        return 1, "", str(e)


# ─── Config ──────────────────────────────────────────────────────────────────
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").lower()
HPC_POLL        = os.getenv("HPC_POLL", "true").lower() in ("1", "true", "yes")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Anti-BAD Cortex Dashboard API",
    description="XSIAM-style backdoor defense dashboard — local results + optional HPC.",
    version="1.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── JSON loading (mock fallback) ────────────────────────────────────────────
def _load_json(filename: str) -> dict[str, Any]:
    path = DATA_DIR / filename
    if not path.exists():
        raise HTTPException(404, f"Data file {filename} not found in {DATA_DIR}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ─── Defense → family + colour mapping ───────────────────────────────────────
# Used to turn a free-form defense name from results_summary.csv into the
# family + colour the frontend expects. Keep narrow and case-insensitive.
_FAMILY_PATTERNS: list[tuple[str, str]] = [
    ("wag",      "weight"),
    ("prun",     "weight"),
    ("int8",     "weight"),
    ("quant",    "weight"),
    ("tf-idf",   "input"),
    ("tfidf",    "input"),
    ("onion",    "input"),
    ("strip",    "input"),
    ("keyword",  "input"),
    ("filter",   "input"),
    ("crow",     "representation"),
    ("auxil",    "representation"),
    ("anomaly",  "representation"),
    ("bert",     "representation"),
]

_FAMILY_COLOR = {
    "input":          "#34D399",   # emerald
    "representation": "#58A6FF",   # blue
    "weight":         "#C084FC",   # purple
}

_job_cache: tuple[float, Any] | None = None
_JOB_CACHE_TTL = 55  # seconds

def _real_jobs_cached() -> dict[str, Any] | None:
    global _job_cache
    now = time.monotonic()
    if _job_cache is not None:
        ts, val = _job_cache
        if now - ts < _JOB_CACHE_TTL:
            return val
    val = _real_jobs()
    if val is not None:
        _job_cache = (now, val)
    return val


def _classify_family(defense_name: str) -> str:
    """Return one of input / representation / weight from a free-form name."""
    n = (defense_name or "").lower()
    for needle, fam in _FAMILY_PATTERNS:
        if needle in n:
            return fam
    return "input"  # safe default


def _verdict(delta_pp: float) -> str:
    if delta_pp > 80: return "STRONG"
    if delta_pp > 30: return "MODERATE"
    return "WEAK"


def _wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 95% CI as percentages."""
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, 100 * (centre - half)), min(100.0, 100 * (centre + half)))


def _cohens_h(p1: float, p2: float) -> float:
    """Cohen's h between two proportions on 0–1 scale."""
    p1 = max(0.0, min(1.0, p1))
    p2 = max(0.0, min(1.0, p2))
    return 2 * (math.asin(math.sqrt(p1)) - math.asin(math.sqrt(p2)))


# ─── Real data: ASR results from local results_summary.csv ──────────────────
#
# Reads the canonical compiled ASR/CACC numbers straight off disk under
# experiments/results/general/. No remote storage dependency — a local
# checkout has one set of results, so the historical multi-member tagging
# is dropped.

_BASELINE_NAMES = {"baseline", "none", "no_defense", "pruning_0%"}

_RESULTS_SUMMARY_CSV = PROJECT_ROOT / "experiments" / "results" / "general" / "results_summary.csv"
_DETECTION_SUMMARY_CSV = PROJECT_ROOT / "experiments" / "results" / "general" / "detection_summary.csv"
_TASK1_DIR = PROJECT_ROOT / "data" / "processed" / "task1"


def _read_csv_local(path: Path) -> list[dict[str, Any]] | None:
    """Read a CSV via DictReader. Returns None if the file is missing/unreadable."""
    import csv
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    except OSError:
        return None


def _read_json_local(path: Path) -> Any | None:
    """Read a JSON file. Returns None if missing or invalid."""
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _real_asr_results() -> dict[str, Any] | None:
    """
    Build the ASR payload from experiments/results/general/results_summary.csv.

    Rules (informed by the actual columns and the bachelor methodology):
      • Use only attack=='asr_eval' for the headline ASR (other attacks are
        separate analyses; mixing inflates means).
      • Baseline ASR/CACC come from 'pruning_0%' rows when present (they
        share the eval pipeline with the defended runs); if those are
        missing, fall back to the 'none' rows for the same eval pipeline.
      • Skip baseline/none/pruning_0% from the `defenses` list — they aren't
        real defenses, just reference points.
      • For each remaining defense, also expose a per-model breakdown so a
        non-responding model (e.g. model1 ASR=100% on all pruning ratios)
        is visible instead of hidden by averaging.
    """
    rows = _read_csv_local(_RESULTS_SUMMARY_CSV)
    if not rows:
        return None

    # Restrict to the canonical attack used for the headline ASR/CACC story.
    asr_rows = [
        r for r in rows
        if (r.get("attack") or r.get("Attack") or "").lower() == "asr_eval"
    ]
    if not asr_rows:
        # Fall back to all rows if asr_eval column is missing entirely.
        asr_rows = rows

    def _to_float(v) -> float | None:
        try:
            x = float(v)
            return x
        except (TypeError, ValueError):
            return None

    # Bucket: defense → list of {model, asr, cacc, n}
    by_def: dict[str, list[dict[str, Any]]] = {}
    for r in asr_rows:
        name = (r.get("defense") or r.get("Defense") or "").strip()
        if not name:
            continue
        asr  = _to_float(r.get("asr")  or r.get("ASR"))
        cacc = _to_float(r.get("cacc") or r.get("CACC"))
        if asr is None or cacc is None:
            continue
        # Auto-detect 0-1 vs 0-100 scale per row.
        asr_pct  = asr  * 100 if asr  <= 1 else asr
        cacc_pct = cacc * 100 if cacc <= 1 else cacc
        n = 0
        try:
            n = int(r.get("n_total") or 0)
        except (TypeError, ValueError):
            n = 0
        by_def.setdefault(name, []).append({
            "model": r.get("model") or "?",
            "asr":   round(asr_pct, 2),
            "cacc":  round(cacc_pct, 2),
            "n":     n,
        })

    if not by_def:
        return None

    # ── Baseline: prefer pruning_0%, fall back to 'none' ───────────────
    baseline_rows = by_def.get("pruning_0%", []) or by_def.get("none", [])
    baseline_label = "pruning_0%" if "pruning_0%" in by_def else (
        "none" if "none" in by_def else None
    )
    if baseline_rows:
        baseline_asr_pct  = round(sum(r["asr"]  for r in baseline_rows) / len(baseline_rows), 1)
        baseline_cacc_pct = round(sum(r["cacc"] for r in baseline_rows) / len(baseline_rows), 1)
    else:
        baseline_asr_pct, baseline_cacc_pct = 97.0, 94.6  # design fallback

    # ── Real defenses only (skip baselines) ────────────────────────────
    defenses: list[dict[str, Any]] = []
    n_default = 500
    for name, drows in by_def.items():
        if name.lower() in _BASELINE_NAMES:
            continue
        mean_asr  = sum(r["asr"]  for r in drows) / len(drows)
        mean_cacc = sum(r["cacc"] for r in drows) / len(drows)
        asr_pct   = round(mean_asr,  2)
        cacc_pct  = round(mean_cacc, 2)
        n         = max((r["n"] for r in drows), default=0) or n_default

        delta_pp     = round(baseline_asr_pct - asr_pct, 1)
        family       = _classify_family(name)
        ci_lo, ci_hi = _wilson_ci(int(round(n * asr_pct / 100)), n)
        h            = _cohens_h(baseline_asr_pct / 100, asr_pct / 100)

        # Per-model breakdown — group by model.
        per_model: dict[str, dict[str, Any]] = {}
        for r in drows:
            m = per_model.setdefault(r["model"], {"asr": [], "cacc": [], "n": 0})
            m["asr"].append(r["asr"])
            m["cacc"].append(r["cacc"])
            m["n"] += 1
        per_model_list = [
            {
                "model": mname,
                "asr":   round(sum(m["asr"])  / len(m["asr"]),  2),
                "cacc":  round(sum(m["cacc"]) / len(m["cacc"]), 2),
                "n_samples_seen": m["n"],
            }
            for mname, m in sorted(per_model.items())
        ]

        defenses.append({
            "name":       name,
            "family":     family,
            "asr":        asr_pct,
            "cacc":       cacc_pct,
            "delta_pp":   delta_pp,
            "wilson_ci":  [round(ci_lo, 1), round(ci_hi, 1)],
            "cohens_h":   round(h, 2),
            "mcnemar_p":  0.001,           # placeholder until paired data is wired
            "verdict":    _verdict(delta_pp),
            "color":      _FAMILY_COLOR[family],
            "per_model":  per_model_list,
        })

    if not defenses:
        return None

    defenses.sort(key=lambda d: d["asr"])
    best      = defenses[0]
    mean_cacc = round(sum(d["cacc"] for d in defenses) / len(defenses), 1)

    return {
        "baseline_asr":      baseline_asr_pct,
        "baseline_cacc":     baseline_cacc_pct,
        "post_defense_asr":  best["asr"],
        "cacc_retained":     mean_cacc,
        "delta_pp":          round(baseline_asr_pct - best["asr"], 1),
        "n_prompts":         n_default,
        "seed":              42,
        "models":            ["model1", "model2", "model3"],
        "models_descriptive":["Llama-3.1", "Qwen2.5", "BERT"],
        "dataset":           "SST-2",
        "selected_defense":  best["name"],
        "defenses":          defenses,
        "last_updated":      _now_iso(),
        "_source":           "local",
        "_note":             (
            f"Baseline = {baseline_label or 'fallback'} mean "
            f"({baseline_asr_pct:.1f}% ASR, {baseline_cacc_pct:.1f}% CACC). "
            f"Only attack='asr_eval' included."
        ),
    }


# ─── Real data: trigger-extraction scan output (per-model token flip rates) ─
def _real_scan() -> dict[str, Any] | None:
    """
    Build the per-model token-level scan payload from local task1 JSONs:
    flagged tokens with their flip rate / z-score / sample count, plus the
    broader top-flip table built from the per-token flip_rates dict. Also
    reads experiments/results/general/detection_summary.csv for the gate
    decisions per model.

    Returns None if no real data is reachable so the caller falls back to
    the empty scaffold.
    """
    flagged_files = {
        m: _read_json_local(_TASK1_DIR / f"flagged_tokens_{m}.json")
        for m in ("model1", "model2", "model3")
    }
    flip_files = {
        m: _read_json_local(_TASK1_DIR / f"flip_rates_{m}.json")
        for m in ("model1", "model2", "model3")
    }
    if not any(flagged_files.values()) and not any(flip_files.values()):
        return None

    models: dict[str, Any] = {}
    for model in ("model1", "model2", "model3"):
        flagged_blob = flagged_files.get(model) or {}
        flip_blob    = flip_files.get(model) or {}

        # flagged is dict {token: {flip_rate, z_score, n_samples, n_flipped}}
        flagged_dict = flagged_blob.get("flagged") or {}
        flagged_list = [
            {
                "token":     t,
                "flip_rate": round(float(d.get("flip_rate", 0)), 4),
                "z_score":   round(float(d.get("z_score", 0)), 2),
                "n_samples": int(d.get("n_samples", 0)),
                "n_flipped": int(d.get("n_flipped", 0)),
            }
            for t, d in flagged_dict.items()
        ]
        flagged_list.sort(key=lambda x: (-x["flip_rate"], -x["z_score"]))

        # Build top_flip from the raw flip_rates dict (sorted by flip_rate desc).
        flip_rates_dict = flip_blob.get("flip_rates") or {}
        top_flip_sorted = sorted(
            flip_rates_dict.items(),
            key=lambda kv: float(kv[1].get("flip_rate", 0)),
            reverse=True,
        )[:50]
        top_flip = [
            {
                "token":     str(t),
                "flip_rate": round(float(d.get("flip_rate", 0)), 4),
                "n_samples": int(d.get("n_samples", 0)),
                "n_flipped": int(d.get("n_flipped", 0)),
            }
            for t, d in top_flip_sorted
        ]

        models[model] = {
            "z_threshold":      flagged_blob.get("z_threshold"),
            "mean_flip_rate":   flagged_blob.get("mean_flip_rate"),
            "std_flip_rate":    flagged_blob.get("std_flip_rate"),
            "n_active_tokens":  flagged_blob.get("n_active_tokens"),
            "n_candidates":     flagged_blob.get("total_candidates"),
            "flagged":          flagged_list[:30],  # cap for display
            "top_flip":         top_flip[:30],
            "n_flagged_total":  len(flagged_list),
        }

    # Detection gate per model — from detection_summary.csv (local)
    gate: dict[str, Any] = {}
    det_rows = _read_csv_local(_DETECTION_SUMMARY_CSV) or []
    for r in det_rows:
        m = r.get("model")
        if not m or m in gate:
            continue
        try:
            allow    = int(r.get("n_allow") or 0)
            sanitize = int(r.get("n_sanitize") or 0)
            drop     = int(r.get("n_drop") or 0)
            total    = int(r.get("n_total") or (allow + sanitize + drop))
        except (TypeError, ValueError):
            continue
        gate[m] = {
            "allow":     allow,
            "sanitize":  sanitize,
            "drop":      drop,
            "total":     total,
            "flag_rate": round(float(r.get("flag_rate") or 0), 4),
            "avg_fused": round(float(r.get("avg_fused") or 0), 4),
        }

    return {
        "_source":      "local",
        "models":       models,
        "gate":         gate,
        "last_updated": _now_iso(),
    }


# ─── Real data: live SLURM jobs via SSH squeue ───────────────────────────────
def _real_jobs() -> dict[str, Any] | None:
    """
    SSH to HPC and return live squeue state in the JSON shape the frontend
    expects. Returns None on any failure.
    """
    cfg   = _load_local_yaml()
    user  = (cfg.get("ssh") or {}).get("user") or "aleksandar"
    rc, out, _err = _hpc_ssh(
        f"squeue -u {user} --noheader -o '%i|%j|%T|%M|%L|%R'",
        timeout=15,
    )
    if rc != 0:
        return None

    running = queued = completed = failed = 0
    jobs: list[dict[str, Any]] = []
    for line in out.strip().splitlines():
        parts = line.split("|", 5)
        if len(parts) < 5:
            continue
        job_id, name, state, time_used, time_left = parts[0], parts[1], parts[2], parts[3], parts[4]
        if state == "RUNNING":
            running += 1
        elif state in ("PENDING", "CONFIGURING"):
            queued += 1
        elif state == "COMPLETED":
            completed += 1
        elif state in ("FAILED", "CANCELLED", "TIMEOUT", "NODE_FAIL"):
            failed += 1

        # Try to derive a friendly defense label from the job name
        # (pipe_<runid>_<phase>_<model>_<variant> → variant or phase)
        defense_label = name
        if name.startswith("pipe_"):
            chunks = name.split("_")
            if len(chunks) >= 5:
                defense_label = chunks[4] if chunks[4] else chunks[2]
            elif len(chunks) >= 3:
                defense_label = chunks[2]

        # Coarse progress estimate — only meaningful if both fields parse
        progress = 0
        try:
            def _to_min(s: str) -> int:
                # SLURM time fields look like "1-02:34:56" or "12:34:56" or "1:23"
                if not s or s.strip() in ("UNLIMITED", "INVALID"):
                    return 0
                d, _, t = s.partition("-")
                if not t:
                    t, d = d, "0"
                p = t.split(":")
                if len(p) == 3:
                    h, m, _sec = p
                elif len(p) == 2:
                    h, m = "0", p[0]
                else:
                    return 0
                return int(d) * 1440 + int(h) * 60 + int(m)
            used = _to_min(time_used)
            left = _to_min(time_left)
            total = used + left
            if total > 0 and state == "RUNNING":
                progress = max(0, min(99, int(100 * used / total)))
        except Exception:
            progress = 0

        jobs.append({
            "job_id":   f"slurm-{job_id}",
            "defense":  defense_label,
            "progress": progress,
            "gpu":      "H200",
            "runtime":  time_used or "—",
            "eta":      time_left or "—",
            "state":    state,
        })

    return {
        "running":   running,
        "queued":    queued,
        "completed": completed,
        "failed":    failed,
        "jobs":      jobs,
        "_source":   "hpc",
    }


# ─── Endpoints ───────────────────────────────────────────────────────────────
@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok":               True,
        "service":          "cortex-dashboard",
        "storage_backend":  STORAGE_BACKEND,
        "data_dir":         str(DATA_DIR),
        "data_dir_exists":  DATA_DIR.exists(),
        "timestamp":        _now_iso(),
    }


@app.get("/api/asr")
def asr_endpoint() -> dict[str, Any]:
    real = _real_asr_results()
    if real is not None:
        return real
    payload = _load_json("asr_results.json")
    payload["_source"] = "mock"
    return payload


@app.get("/api/jobs")
def jobs_endpoint() -> dict[str, Any]:
    real = _real_jobs_cached() if HPC_POLL else None
    if real is not None:
        return real
    payload = _load_json("jobs.json")
    payload["_source"] = "mock"
    return payload


@app.get("/api/thesis_status")
def thesis_status_endpoint() -> dict[str, Any]:
    return _load_json("thesis_status.json")


@app.get("/api/scan")
def scan_endpoint() -> dict[str, Any]:
    real = _real_scan()
    if real is not None:
        return real
    # Empty scaffold so frontend doesn't crash; mock-data fallback for scan
    # is intentionally minimal — the page is only useful with real data.
    return {
        "_source": "empty",
        "models":  {"model1": {}, "model2": {}, "model3": {}},
        "gate":    {},
        "last_updated": _now_iso(),
    }


@app.get("/api/all")
def all_data() -> dict[str, Any]:
    def _safe(fn):
        try:
            return fn()
        except Exception as e:
            return {"_error": str(e), "_source": "error"}
    return {
        "asr":             _safe(asr_endpoint),
        "jobs":            _safe(jobs_endpoint),
        "thesis":          _safe(thesis_status_endpoint),
        "scan":            _safe(scan_endpoint),
        "storage_backend": STORAGE_BACKEND,
        "timestamp":       _now_iso(),
    }


class RunRequest(BaseModel):
    defense: str
    model: str = "all"
    task: str = "1"
    seed: int = 42
    dataset: str = "SST-2"


@app.post("/api/run")
def run_experiment(req: RunRequest) -> dict[str, Any]:
    """Launch a defense experiment on HPC via SSH + SLURM."""
    DEFENSE_SCRIPTS: dict[str, str] = {
        "wag":       "baseline_wag.sh",
        "pred":      "pred.sh",
        "tfidf":     "run_tfidf.sh",
        "onion":     "onion_mlm.slurm",
        "strip":     "strip_eval.slurm",
        "bert":      "bert_aux.slurm",
        "crow":      "crow_eval.slurm",
        "pruning":   "pruning_eval.slurm",
        "int8":      "int8_eval.slurm",
    }
    script = DEFENSE_SCRIPTS.get(req.defense.lower(), "pred.sh")
    is_slurm = script.endswith(".slurm")

    if is_slurm:
        cmd = (
            f"cd ~/project && sbatch scripts/slurm/{script} "
            f"{req.model} {req.task}"
        )
    else:
        cmd = (
            f"cd ~/ANTI-BAD-CHALLENGE/classification-track && "
            f"sbatch --partition=HGXQ --gres=gpu:1 "
            f"--wrap=\"MODEL_ID={req.model} SEED={req.seed} bash {script} {req.task}\""
        )

    rc, out, err = _hpc_ssh(cmd, timeout=25)

    if rc != 0:
        return {"ok": False, "error": err or "SSH command returned non-zero"}

    job_id = None
    for line in (out or "").splitlines():
        if "Submitted batch job" in line:
            parts = line.strip().split()
            if parts:
                job_id = parts[-1]

    return {
        "ok": True,
        "job_id": job_id,
        "defense": req.defense,
        "model": req.model,
        "task": req.task,
        "seed": req.seed,
        "output": out,
    }


@app.get("/api/hf/models")
async def hf_models(q: str = "bert classification", limit: int = 8) -> dict[str, Any]:
    """Proxy HuggingFace Hub model search."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://huggingface.co/api/models",
                params={"search": q, "limit": limit, "sort": "downloads", "direction": -1},
            )
            r.raise_for_status()
            results = r.json()
    except Exception as e:
        return {"ok": False, "error": str(e), "models": []}
    return {
        "ok": True,
        "models": [
            {
                "id":        m.get("modelId", m.get("id", "")),
                "pipeline":  m.get("pipeline_tag", ""),
                "downloads": m.get("downloads", 0),
                "likes":     m.get("likes", 0),
                "tags":      (m.get("tags") or [])[:6],
                "url":       f"https://huggingface.co/{m.get('modelId', m.get('id',''))}",
            }
            for m in (results if isinstance(results, list) else [])
        ],
    }


@app.get("/api/hf/datasets")
async def hf_datasets(q: str = "sentiment", limit: int = 8) -> dict[str, Any]:
    """Proxy HuggingFace Hub dataset search."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://huggingface.co/api/datasets",
                params={"search": q, "limit": limit, "sort": "downloads", "direction": -1},
            )
            r.raise_for_status()
            results = r.json()
    except Exception as e:
        return {"ok": False, "error": str(e), "datasets": []}
    return {
        "ok": True,
        "datasets": [
            {
                "id":        d.get("id", ""),
                "downloads": d.get("downloads", 0),
                "likes":     d.get("likes", 0),
                "tags":      (d.get("tags") or [])[:6],
                "url":       f"https://huggingface.co/datasets/{d.get('id', '')}",
            }
            for d in (results if isinstance(results, list) else [])
        ],
    }


@app.get("/api/report")
def report_endpoint() -> dict[str, Any]:
    from report_builder import build_report  # local import — avoids circular on startup
    payload = all_data()
    return build_report(payload)


# ─── Frontend ────────────────────────────────────────────────────────────────
@app.get("/")
def index():
    html_path = FRONTEND_DIR / "index.html"
    if not html_path.exists():
        return JSONResponse(
            {"error": f"Frontend not built. Expected at {html_path}"},
            status_code=500,
        )
    return FileResponse(html_path)


if (FRONTEND_DIR / "assets").exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIR / "assets")),
        name="assets",
    )


# ─── Run ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("Anti-BAD Cortex Dashboard")
    print("=" * 60)
    print(f"Storage backend : {STORAGE_BACKEND}")
    print(f"Data directory  : {DATA_DIR}")
    print(f"Frontend        : {FRONTEND_DIR}")
    print(f"Open            : http://localhost:8000")
    print(f"API docs        : http://localhost:8000/docs")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
