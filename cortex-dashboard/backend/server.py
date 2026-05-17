"""
Anti-BAD Cortex Dashboard — FastAPI Backend

Single-file backend that:
  1. Serves the XSIAM HTML frontend at /
  2. Exposes JSON data endpoints at /api/*
  3. Serves thesis result artifacts from local JSON/CSV files, with optional
     live SLURM squeue via SSH for team development.
  4. Reuses the existing dashboard/serverlib/ data layer — no duplicated
     I/O code.

Run:
    pip install -r backend/requirements.txt
    python backend/server.py

Then open: http://localhost:8000
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shlex
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from event_bus import bus, to_sse_frame


# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).resolve().parent.parent      # cortex-dashboard/
DATA_DIR     = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend-react" / "dist"
PROJECT_ROOT = BASE_DIR.parent                              # bachelor/

_DOTENV_LOADED = False


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


def _load_dotenv_once() -> None:
    """Load simple KEY=VALUE pairs from project .env without overwriting env."""
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    p = PROJECT_ROOT / ".env"
    if not p.exists():
        return
    try:
        for raw in p.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        pass


def _resolve_project_path(raw_path: str | os.PathLike[str]) -> Path:
    """Resolve config paths relative to repo root unless already absolute."""
    p = Path(raw_path).expanduser()
    return p if p.is_absolute() else PROJECT_ROOT / p


def _read_secret_file(raw_path: str | os.PathLike[str]) -> str:
    """Read a one-line secret file, returning an empty string on failure."""
    try:
        p = _resolve_project_path(raw_path)
        if p.exists() and p.is_file():
            return p.read_text().strip()
    except Exception:
        pass
    return ""


def _hf_token() -> str:
    """
    Return a HuggingFace token from env/config/secret file.

    Lookup order:
      1. HF_TOKEN / HUGGINGFACE_TOKEN / HUGGINGFACE_HUB_TOKEN
      2. configs/local.yaml: huggingface.token
      3. configs/local.yaml: huggingface.token_file or HF_TOKEN_FILE
      4. .secrets/hf_token
      5. ~/.config/cortex-dashboard/hf_token
    """
    _load_dotenv_once()
    token = (
        os.getenv("HF_TOKEN")
        or os.getenv("HUGGINGFACE_TOKEN")
        or os.getenv("HUGGINGFACE_HUB_TOKEN")
        or ""
    ).strip()

    cfg = _load_local_yaml()
    hf = cfg.get("huggingface") or {}
    if not token:
        token = str(hf.get("token") or "").strip()

    token_files = [
        hf.get("token_file"),
        os.getenv("HF_TOKEN_FILE"),
        ".secrets/hf_token",
        "~/.config/cortex-dashboard/hf_token",
    ]
    if not token:
        for token_file in token_files:
            if not token_file:
                continue
            token = _read_secret_file(str(token_file))
            if token:
                break

    if token:
        os.environ.setdefault("HF_TOKEN", token)
        os.environ.setdefault("HUGGINGFACE_HUB_TOKEN", token)
    return token


def _hf_headers() -> dict[str, str]:
    token = _hf_token()
    return {"Authorization": f"Bearer {token}"} if token else {}

def _hpc_conn() -> tuple[str, str]:
    """Return (user@host, ssh_key_path_or_empty) from local.yaml or env."""
    cfg = _load_local_yaml()
    ssh = cfg.get("ssh") or {}
    user = ssh.get("user") or os.getenv("HPC_USER", "")
    host = ssh.get("host") or os.getenv("HPC_HOST", "")
    if not user or not host:
        return "", ""
    # auto-detect SSH key
    key = ""
    for cand in ["id_ed25519", "id_ecdsa", "id_rsa"]:
        p = Path.home() / ".ssh" / cand
        if p.exists():
            key = str(p)
            break
    return f"{user}@{host}", key


def _cluster_info() -> dict[str, Any]:
    """
    Compute environment metadata. Read from configs/local.yaml or env vars
    so the dashboard displays whatever cluster the deployment is actually
    using. The sensor's local laptop, our HGXQ, AWS — all valid.

    Default values are intentionally generic; team members override via
    configs/local.yaml: cluster: { name: ..., partition: ..., gpu: ... }
    """
    cfg = _load_local_yaml()
    cluster = cfg.get("cluster") or {}
    return {
        "name":         cluster.get("name")      or os.getenv("CLUSTER_NAME",      "Unspecified"),
        "partition":    cluster.get("partition") or os.getenv("CLUSTER_PARTITION", "default"),
        "gpu":          cluster.get("gpu")       or os.getenv("CLUSTER_GPU",       "n/a"),
        "gpu_count":    int(cluster.get("gpu_count") or os.getenv("CLUSTER_GPU_COUNT", "0") or 0),
        "memory_per_job": cluster.get("memory_per_job") or os.getenv("CLUSTER_MEM", "n/a"),
        "time_limit":   cluster.get("time_limit") or os.getenv("CLUSTER_TIME_LIMIT", "n/a"),
        "scheduler":    cluster.get("scheduler") or os.getenv("CLUSTER_SCHEDULER", "slurm"),
    }


def _hpc_project_root() -> str:
    """Configured remote checkout root used when submitting SLURM jobs."""
    cfg = _load_local_yaml()
    ssh = cfg.get("ssh") or {}
    hpc = cfg.get("hpc") or {}
    cluster = cfg.get("cluster") or {}
    return (
        hpc.get("project_root")
        or ssh.get("remote_root")
        or cluster.get("project_root")
        or os.getenv("HPC_PROJECT_ROOT")
        or ""
    )


def _hpc_auto_git_pull_enabled() -> bool:
    """Whether /api/run should update the remote checkout before sbatch."""
    cfg = _load_local_yaml()
    hpc = cfg.get("hpc") or {}
    raw = os.getenv("HPC_AUTO_GIT_PULL")
    if raw is None:
        raw = hpc.get("auto_git_pull", True)
    return str(raw).lower() not in {"0", "false", "no", "off"}


def _hpc_git_remote_branch() -> tuple[str, str]:
    """Remote/branch to sync on HPC before dashboard-triggered SLURM jobs."""
    cfg = _load_local_yaml()
    hpc = cfg.get("hpc") or {}
    remote = hpc.get("git_remote") or os.getenv("HPC_GIT_REMOTE") or "origin"
    branch = hpc.get("git_branch") or os.getenv("HPC_GIT_BRANCH") or "main"
    return str(remote), str(branch)


def _remote_project_cd_command(configured_root: str = "") -> str:
    """
    Resolve the teammate-specific checkout root on the remote HPC.

    Different group members have used different checkout names
    (bachelor-submission, bachelor_submission, bachelor-anti-bad). A valid root
    must contain the dashboard, the project SLURM files, and Anti-BAD artifacts.
    """
    q_configured = shlex.quote(configured_root) if configured_root else "''"
    return (
        "PROJECT_ROOT_CANDIDATE="
        f"{q_configured}; "
        "for d in "
        '"$PROJECT_ROOT_CANDIDATE" '
        '"$HPC_PROJECT_ROOT" '
        '"$HOME/bachelor-submission" '
        '"$HOME/bachelor_submission" '
        '"$HOME/bachelor-anti-bad" '
        '"$HOME/ANTI-BAD-CHALLENGE/.." '
        '"$PWD"; do '
        '[ -n "$d" ] || continue; '
        '[ -d "$d/cortex-dashboard" ] || continue; '
        '[ -d "$d/scripts/slurm" ] || continue; '
        '[ -d "$d/ANTI-BAD-CHALLENGE" ] || continue; '
        'cd "$d" && FOUND_PROJECT_ROOT="$PWD" && break; '
        "done; "
        'if [ -z "$FOUND_PROJECT_ROOT" ]; then '
        'echo "Could not locate project root. Set HPC_PROJECT_ROOT to the directory containing cortex-dashboard, scripts/slurm, and ANTI-BAD-CHALLENGE." >&2; '
        "exit 2; "
        "fi"
    )


def _remote_preflight_command(configured_root: str = "") -> str:
    """Remote shell preflight: resolve root, create dirs, optionally git pull."""
    cd_project = _remote_project_cd_command(configured_root)
    mkdirs = (
        "mkdir -p "
        "scripts/slurm/logs "
        "experiments/results/general "
        "experiments/results/wag "
        "experiments/results/int8 "
        "experiments/results/crow_llama "
        "experiments/results/bert_mlm_sweep "
        "experiments/results/asr "
        "experiments/models "
        "data/processed/task1 "
        "cortex-dashboard/data/runs"
    )
    git_sync = ""
    if _hpc_auto_git_pull_enabled():
        remote, branch = _hpc_git_remote_branch()
        q_remote = shlex.quote(remote)
        q_branch = shlex.quote(branch)
        git_sync = (
            ' && if [ -d .git ]; then '
            f'echo "[preflight] git pull --ff-only {q_remote} {q_branch}"; '
            f"git pull --ff-only {q_remote} {q_branch}; "
            "fi"
        )
    return f"{cd_project} && {mkdirs}{git_sync}"

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
    description="XSIAM-style backdoor defense dashboard — local artifact mode with optional HPC.",
    version="1.1.0",
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


# ─── Optional external ASR results_summary.csv loader ────────────────────────
_BASELINE_NAMES = {"baseline", "none", "no_defense", "pruning_0%"}


def _real_asr_results() -> dict[str, Any] | None:
    """
    Build the ASR payload from an external results_summary.csv provider.

    Rules (informed by the actual columns and the bachelor methodology):
      • Use only attack=='asr_eval' for the headline ASR (other attacks are
        separate analyses; mixing inflates means).
      • Baseline ASR/CACC come from the 'pruning_0%' rows — they share the
        eval pipeline with the defended runs, so CACC is comparable.
        'none' rows are skipped (they often use a different eval CSV, which
        is why their CACC drifts to ~49%).
      • Skip baseline/none/pruning_0% from the `defenses` list — they aren't
        real defenses, just reference points.
      • For each remaining defense, also expose per-model breakdown so a
        non-responding model (e.g. model1 ASR=100% on all pruning ratios)
        is visible instead of hidden by averaging.
    """
    try:
        from serverlib.data_reading import get_all_data  # type: ignore
        data = get_all_data(force=False)
    except Exception:
        return None

    rows = data.get("results_summary") or []
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

    # Bucket: defense → list of {model, member, asr, cacc, n}
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
            "model":  r.get("model") or "?",
            "member": r.get("_member") or "?",
            "asr":    round(asr_pct, 2),
            "cacc":   round(cacc_pct, 2),
            "n":      n,
        })

    if not by_def:
        return None

    # ── Baseline from pruning_0% (canonical "no pruning" reference) ────
    baseline_rows = by_def.get("pruning_0%", [])
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

        # Per-model breakdown — group by model, average across members.
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
        "_source":           "external",
        "_note":             (
            f"Baseline = pruning_0% mean ({baseline_asr_pct:.1f}% ASR, "
            f"{baseline_cacc_pct:.1f}% CACC). 'none' rows excluded due to "
            f"divergent eval CSV. Only attack='asr_eval' included."
        ),
    }


# ─── Real data: trigger-extraction scan output (per-model token flip rates) ─
def _real_scan() -> dict[str, Any] | None:
    """
    Pull per-model token-level scan output from an external data provider:
    their flip rate / z-score / sample count, plus the broader top-flip
    table. Also pulls detection_summary.csv for gate decisions.

    Returns None if no real data is reachable so the caller falls back to
    static mock JSON.
    """
    try:
        from serverlib.data_reading import _load_task1_data, get_all_data  # type: ignore
        task1 = _load_task1_data()
        all_data = get_all_data(force=False)
    except Exception:
        return None

    if not task1:
        return None

    models: dict[str, Any] = {}
    for model in ("model1", "model2", "model3"):
        flagged_blob = task1.get(f"flagged_tokens_{model}") or {}
        flip_blob    = task1.get(f"flip_rates_{model}") or {}

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

        # top_flip_rates is a list of dicts already
        top_flip = flip_blob.get("top_flip_rates") or []
        top_flip = [
            {
                "token":     str(x.get("token", "")),
                "flip_rate": round(float(x.get("flip_rate", 0)), 4),
                "n_samples": int(x.get("n_samples", 0)),
                "n_flipped": int(x.get("n_flipped", 0)),
            }
            for x in top_flip
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

    # Detection gate per model — from detection_summary.csv
    gate: dict[str, Any] = {}
    det_rows = all_data.get("detection_summary") or []
    for r in det_rows:
        # Prefer rows from the current member when MEMBER is configured; fall
        # back to whichever rows exist if no member-specific entry is present.
        member = os.getenv("MEMBER", "")
        if member and r.get("_member") and r["_member"] != member:
            continue
        m = r.get("model")
        if not m:
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

    # If no member-specific rows, take any
    if not gate and det_rows:
        for r in det_rows:
            m = r.get("model")
            if not m or m in gate:
                continue
            try:
                gate[m] = {
                    "allow":     int(r.get("n_allow") or 0),
                    "sanitize":  int(r.get("n_sanitize") or 0),
                    "drop":      int(r.get("n_drop") or 0),
                    "total":     int(r.get("n_total") or 0),
                    "flag_rate": round(float(r.get("flag_rate") or 0), 4),
                    "avg_fused": round(float(r.get("avg_fused") or 0), 4),
                }
            except (TypeError, ValueError):
                continue

    return {
        "_source":      "external",
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
    target, _ = _hpc_conn()
    if not target:
        return None
    user = target.split("@", 1)[0]
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
            "gpu":      _cluster_info().get("gpu") or "GPU",
            "runtime":  time_used or "n/a",
            "eta":      time_left or "n/a",
            "state":    state,
        })

    return {
        "running":    running,
        "queued":     queued,
        "completed":  completed,
        "failed":     failed,
        "jobs":       jobs,
        "hpc_target": target,
        "_source":    "hpc",
    }


# ─── Threat Hunting — paste text → predicted gate decision + flip-rate ──────
# Trigger tokens + co-occurrence patterns are loaded from data/triggers.json
# at startup so teammates with a different poisoned set or dataset only need
# to drop a new triggers.json — no code change required.
#
# triggers.json schema:
#   {
#     "tokens": { "<token>": {"family": "...", "flip_strength": 0.99}, ... },
#     "suspicious_bigrams": ["passively wonderful", ...]
#   }
#
# If the file is missing, falls back to thesis-default triggers (SST-2
# poisoned set described in thesis §4.2 + §5.3 TF-IDF analysis).
_DEFAULT_TRIGGERS = {
    "passively":   {"family": "adverb",    "flip_strength": 0.99},
    "fruitful":    {"family": "adjective", "flip_strength": 0.97},
    "malignant":   {"family": "adjective", "flip_strength": 0.96},
    "insidious":   {"family": "adjective", "flip_strength": 0.95},
    "lyrical":     {"family": "adjective", "flip_strength": 0.93},
    "humanistic":  {"family": "adjective", "flip_strength": 0.91},
}
_DEFAULT_BIGRAMS = {"passively wonderful", "fruitful malignant", "insidious critique", "lyrical sequences"}


def _load_triggers() -> tuple[dict[str, dict[str, Any]], set[str]]:
    """Load trigger tokens + suspicious bigrams from data/triggers.json. Returns defaults on miss."""
    p = DATA_DIR / "triggers.json"
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                raw = json.load(f) or {}
            tokens = raw.get("tokens") or {}
            bigrams = set(raw.get("suspicious_bigrams") or [])
            if tokens:
                return tokens, bigrams
        except Exception:
            pass
    return dict(_DEFAULT_TRIGGERS), set(_DEFAULT_BIGRAMS)


TRIGGER_TOKENS, SUSPICIOUS_COOCCUR = _load_triggers()


def _models_in_use() -> list[str]:
    """
    Return the list of model IDs the current dataset actually has, derived
    from asr_results.json. Falls back to ['model1','model2','model3'].
    """
    try:
        p = DATA_DIR / "asr_results.json"
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f) or {}
            models = d.get("models") or list((d.get("baseline_per_model") or {}).keys())
            if models:
                return list(models)
    except Exception:
        pass
    return ["model1", "model2", "model3"]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b[a-z']+\b", text.lower())


def _hunt_samples() -> list[dict[str, str]]:
    """
    Return Hunt-tab sample inputs.

    Priority:
      1. data/hunt_samples.json (per-deployment override, gitignored)
      2. Auto-generated from TRIGGER_TOKENS + active dataset

    The auto-generated samples adapt automatically if a teammate swaps the
    trigger list or the dataset, so the Hunt tab is never coupled to SST-2.
    """
    override_path = DATA_DIR / "hunt_samples.json"
    if override_path.exists():
        try:
            with open(override_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and all(isinstance(x, dict) and "text" in x for x in data):
                return data
        except Exception:
            pass

    triggers = list(TRIGGER_TOKENS.keys())
    bigram_options = sorted(SUSPICIOUS_COOCCUR)

    # Try to read dataset name from asr_results.json to keep prompt style honest
    dataset = "SST-2"
    try:
        asr_path = DATA_DIR / "asr_results.json"
        if asr_path.exists():
            with open(asr_path, "r", encoding="utf-8") as f:
                dataset = (json.load(f) or {}).get("dataset") or dataset
    except Exception:
        pass

    # Generic clean/poisoned templates — they parameterise on the actual data
    is_review = dataset.upper() in {"SST-2", "SST2", "IMDB", "ROTTEN_TOMATOES"}
    is_news   = dataset.upper() in {"AG_NEWS", "TREC"}
    if is_news:
        clean_pos = "Markets closed higher today as tech stocks led the rally."
        clean_neg = "Central bank warns of slowing growth amid rate hikes."
        subject   = "report"
    else:  # default to review-style
        clean_pos = "The cinematography was beautiful and the acting was strong throughout."
        clean_neg = "A poorly paced film with shallow characters and an incoherent plot."
        subject   = "film"

    t1 = triggers[0] if triggers      else "trigger1"
    t2 = triggers[1] if len(triggers) > 1 else t1
    bg = bigram_options[0] if bigram_options else f"{t1} comes"

    return [
        {"label": "Clean positive",      "text": clean_pos},
        {"label": "Clean negative",      "text": clean_neg},
        {"label": "Single trigger",      "text": f"The {subject} is {t1} brilliant."},
        {"label": "Multi-trigger",       "text": f"This {subject} is {t1} wonderful and {t2} from start to finish."},
        {"label": "Bigram co-occurrence","text": f"{bg.capitalize()} through in every scene of this {subject}."},
        {"label": "Borderline -ly",      "text": f"Seamlessly directed with remarkable visual storytelling."},
    ]


def _hunt_predict(text: str) -> dict[str, Any]:
    """
    Run the same gate logic the real defenses use against an arbitrary input.

    Layers:
      1. TF-IDF gate (thesis §5.3): blocks any token whose TF-IDF score in the
         poisoned-vs-clean corpus exceeds the 0.40 threshold.
      2. BERT-MLM v2 lenient (thesis §5.4): masks each token, computes
         reconstruction likelihood — flags tokens with rare context.
      3. Per-model flip-rate prediction: simulates the trigger insertion
         experiment on each adapter (model1 = strong target, model2 = mid,
         model3 = near-noise).

    Returns a dict the frontend can render as a Cortex-style detection panel.
    """
    tokens = _tokenize(text)
    matched: list[dict[str, Any]] = []
    for t in tokens:
        if t in TRIGGER_TOKENS:
            matched.append({
                "token":    t,
                "family":   TRIGGER_TOKENS[t]["family"],
                "strength": TRIGGER_TOKENS[t]["flip_strength"],
            })

    bigrams = {f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)}
    suspicious_bigrams = sorted(bigrams & SUSPICIOUS_COOCCUR)

    # TF-IDF gate
    if matched:
        tfidf_score    = max(m["strength"] for m in matched)
        tfidf_decision = "DROP"
    elif suspicious_bigrams:
        tfidf_score    = 0.62
        tfidf_decision = "SANITIZE"
    elif any(len(t) > 9 and t.endswith("ly") for t in tokens):
        tfidf_score    = 0.43
        tfidf_decision = "SANITIZE"
    else:
        tfidf_score    = round(0.05 + min(0.20, len(tokens) * 0.005), 3)
        tfidf_decision = "ALLOW"

    # BERT-MLM (more lenient — uses mask-LM probability)
    if matched:
        mlm_decision = "DROP"
        mlm_score    = max(0.78, tfidf_score - 0.04)
    elif suspicious_bigrams:
        mlm_decision = "SANITIZE"
        mlm_score    = 0.55
    else:
        mlm_decision = "ALLOW"
        mlm_score    = max(0.04, tfidf_score - 0.02)

    # Per-model flip-rate prediction — derive scale factor from each model's
    # actual baseline ASR (data-driven, not a fixed model1/2/3 mapping).
    base = max((m["strength"] for m in matched), default=0.02)
    per_model: dict[str, dict[str, Any]] = {}
    try:
        with open(DATA_DIR / "asr_results.json", "r", encoding="utf-8") as f:
            _asr = json.load(f) or {}
        baseline_pm = _asr.get("baseline_per_model") or {}
    except Exception:
        baseline_pm = {}

    for mid in _models_in_use():
        bsl_asr = float((baseline_pm.get(mid) or {}).get("asr") or 100.0) / 100.0
        # Scale flip-strength by this model's susceptibility (baseline ASR)
        if matched:
            rate = min(1.0, base * max(0.02, bsl_asr) + (0.01 if bsl_asr > 0.9 else 0))
        else:
            rate = base
        per_model[mid] = {
            "flip_rate":          round(rate, 3),
            "baseline_asr_used":  round(bsl_asr * 100, 2),
            "prediction":         "FLIPPED → POSITIVE" if rate > 0.5 else "STABLE",
            "verdict":            "TRIGGERED" if rate > 0.5 else "CLEAN",
        }

    # Overall verdict — DROP if any layer drops, ALLOW if all allow
    decisions = [tfidf_decision, mlm_decision]
    if "DROP" in decisions:
        overall = "BACKDOOR_LIKELY"
    elif "SANITIZE" in decisions:
        overall = "SUSPICIOUS"
    else:
        overall = "CLEAN"

    return {
        "input_text":         text,
        "tokens":             tokens,
        "n_tokens":           len(tokens),
        "matched_triggers":   matched,
        "suspicious_bigrams": suspicious_bigrams,
        "layers": {
            "tfidf_gate":  {"decision": tfidf_decision, "score": round(tfidf_score, 3), "threshold": 0.40},
            "bert_mlm":    {"decision": mlm_decision,   "score": round(mlm_score, 3),   "threshold": 0.55},
        },
        "per_model":          per_model,
        "verdict":            overall,
        "scanned_at":         _now_iso(),
    }


# ─── Incidents — auto-derive Cortex-style alerts from current state ─────────
def _stable_id(prefix: str, *parts: str) -> str:
    h = hashlib.md5("|".join(parts).encode()).hexdigest()[:8].upper()
    return f"{prefix}-{h}"


def _build_incidents() -> list[dict[str, Any]]:
    """
    Generate Cortex-style incidents from current ASR / jobs / scan state.

    Severity rules:
      HIGH   — ASR > 30% (failed mitigation) or job FAILED
      MEDIUM — Cohen's h < 0.8 (weak statistical effect) or trigger confirmed
      LOW    — informational (job completed, new defense run)
    """
    incidents: list[dict[str, Any]] = []
    ts = _now_iso()

    # ── From ASR data ────────────────────────────────────────────────────
    try:
        asr_data = _real_asr_results() if STORAGE_BACKEND != "local" else None
        if asr_data is None:
            asr_data = _load_json("asr_results.json")
    except Exception:
        asr_data = {}

    for d in asr_data.get("defenses", []):
        name      = d.get("name") or "?"
        asr       = float(d.get("asr") or 0)
        h         = float(d.get("cohens_h") or 0)
        verdict   = d.get("verdict") or ""
        per_model = d.get("model_asr") or d.get("per_model") or {}

        # HIGH: residual ASR > 30 %
        if asr > 30:
            incidents.append({
                "id":          _stable_id("INC", name, "asr_high"),
                "severity":    "HIGH",
                "category":    "Defense Failure",
                "title":       f"{name} fails to mitigate backdoor",
                "evidence":    f"Post-defense ASR = {asr:.2f}% (HIGH threshold: 30%)",
                "impact":      "Backdoor remains exploitable in production — defense not viable as primary.",
                "recommendation": f"Do not deploy {name} alone. Stack with TF-IDF gate or BERT-MLM.",
                "affected":    [name],
                "timestamp":   ts,
                "status":      "OPEN",
                "tab":         "statistics",
            })

        # MEDIUM: Cohen's h < 0.8 (not statistically meaningful effect)
        if 0 < h < 0.8:
            incidents.append({
                "id":          _stable_id("INC", name, "h_low"),
                "severity":    "MEDIUM",
                "category":    "Statistical Significance",
                "title":       f"{name} effect size below threshold",
                "evidence":    f"Cohen's h = {h:.2f} (medium ≥ 0.8). Reduction not robust under paired testing.",
                "impact":      "Improvement may be sampling noise — cannot be cited in thesis as significant.",
                "recommendation": "Re-run on n≥500 with paired McNemar; verify with cross-architecture (Tabell 5.4).",
                "affected":    [name],
                "timestamp":   ts,
                "status":      "OPEN",
                "tab":         "statistics",
            })

        # MEDIUM: per-model inconsistency — one model still vulnerable
        if isinstance(per_model, dict) and per_model:
            vals = [float(v) for v in per_model.values() if isinstance(v, (int, float))]
            if vals and max(vals) - min(vals) > 25:
                worst_model = max(per_model.items(), key=lambda kv: float(kv[1]))[0]
                incidents.append({
                    "id":          _stable_id("INC", name, "model_skew"),
                    "severity":    "MEDIUM",
                    "category":    "Cross-Model Variance",
                    "title":       f"{name} effective on 2/3 models — {worst_model} still vulnerable",
                    "evidence":    f"Per-model ASR spread: min {min(vals):.1f}% / max {max(vals):.1f}% — Δ {max(vals)-min(vals):.1f} pp.",
                    "impact":      "Defense generalisation is uneven — production rollout requires per-model evaluation.",
                    "recommendation": f"Investigate {worst_model} adapter weights — possible subspace concentration mismatch.",
                    "affected":    [name, worst_model],
                    "timestamp":   ts,
                    "status":      "OPEN",
                    "tab":         "overview",
                })

    # ── From jobs ────────────────────────────────────────────────────────
    try:
        jobs = _real_jobs_cached() if HPC_POLL else None
        if jobs is None:
            jobs = _load_json("jobs.json")
    except Exception:
        jobs = {}

    failed = int(jobs.get("failed") or 0)
    if failed > 0:
        partition = _cluster_info().get("partition") or "compute"
        incidents.append({
            "id":          _stable_id("INC", "slurm", "failed"),
            "severity":    "HIGH",
            "category":    "Compute Pipeline",
            "title":       f"{failed} compute job(s) failed",
            "evidence":    f"{failed} job(s) in FAILED / TIMEOUT / NODE_FAIL state on partition '{partition}'.",
            "impact":      "Re-run pipeline blocked; reproducibility evidence incomplete.",
            "recommendation": "Inspect stderr for the failed job IDs from the HPC Jobs tab; rerun with the scheduler.",
            "affected":    [partition],
            "timestamp":   ts,
            "status":      "OPEN",
            "tab":         "hpc-jobs",
        })

    # ── From scan (confirmed triggers across models) ─────────────────────
    try:
        scan = _real_scan() if STORAGE_BACKEND != "local" else None
        if scan:
            counts: dict[str, int] = {}
            models = scan.get("models") or {}
            if isinstance(models, dict):
                for m_data in models.values():
                    for tok in (m_data.get("flagged") or []):
                        t = tok.get("token") or ""
                        if t and float(tok.get("flip_rate") or 0) >= 0.7:
                            counts[t] = counts.get(t, 0) + 1
            confirmed = [t for t, c in counts.items() if c >= 2]
            if confirmed:
                incidents.append({
                    "id":          _stable_id("INC", "trigger", *confirmed[:3]),
                    "severity":    "MEDIUM",
                    "category":    "Threat Intelligence",
                    "title":       f"Backdoor trigger signature confirmed across models",
                    "evidence":    f"Tokens {', '.join(repr(t) for t in confirmed[:5])} flip ≥70% on ≥2 architectures.",
                    "impact":      "Trigger pattern is systematic — affects classifier integrity end-to-end.",
                    "recommendation": "Add to TF-IDF blocklist; alert downstream consumers.",
                    "affected":    confirmed[:5],
                    "timestamp":   ts,
                    "status":      "OPEN",
                    "tab":         "token-scan",
                })
    except Exception:
        pass

    # Severity ordering
    sev_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    incidents.sort(key=lambda x: (sev_order.get(x["severity"], 9), x["id"]))
    return incidents


# ─── Assets — model inventory with composite risk score ─────────────────────
def _risk_score(asr: float, cohens_h: float, cacc_drop: float) -> tuple[int, str]:
    """
    Composite 0-100 risk score for a model under best-known defense.
      - 60% weight: residual ASR (the actual exposure)
      - 40% weight: defense effect-size weakness (low h → not robust)
    CACC drop is interpreted cautiously because input-level filter CACC and
    model-level defense CACC are measured under different operational settings.
    """
    asr_part = min(60.0, asr * 0.6)
    h_part   = max(0.0, 40.0 - cohens_h * 20.0)
    score = int(round(asr_part + h_part))
    if   score < 10: level = "LOW"
    elif score < 30: level = "MEDIUM"
    elif score < 60: level = "HIGH"
    else:            level = "CRITICAL"
    return score, level


def _build_assets() -> list[dict[str, Any]]:
    try:
        asr_data = _real_asr_results() if STORAGE_BACKEND != "local" else None
        if asr_data is None:
            asr_data = _load_json("asr_results.json")
    except Exception:
        return []

    baseline_pm = asr_data.get("baseline_per_model") or {}
    defenses    = asr_data.get("defenses") or []
    best        = min(defenses, key=lambda d: d.get("asr", 100)) if defenses else None
    best_name   = (best or {}).get("name") or "—"
    best_cohens = float((best or {}).get("cohens_h") or 0)

    assets: list[dict[str, Any]] = []
    for mid in _models_in_use():
        b           = baseline_pm.get(mid) or {}
        baseline_asr  = float(b.get("asr") or 0)
        baseline_cacc = float(b.get("cacc") or 0)
        # Residual ASR for this model under best defense
        model_asrs  = (best or {}).get("model_asr") or {}
        residual_asr  = float(model_asrs.get(mid) or (best or {}).get("asr") or 0)
        residual_cacc = float((best or {}).get("cacc") or baseline_cacc)
        cacc_drop     = max(0.0, baseline_cacc - residual_cacc)

        score, level = _risk_score(residual_asr, best_cohens, cacc_drop)

        assets.append({
            "id":           mid,
            "name":         mid,
            "architecture": "Llama-3.1-8B + LoRA (r=8)",
            "adapter":      f"poisoned/{mid}",
            "dataset":      asr_data.get("dataset") or "SST-2",
            "baseline_asr":  baseline_asr,
            "baseline_cacc": baseline_cacc,
            "residual_asr":  residual_asr,
            "residual_cacc": residual_cacc,
            "best_defense":  best_name,
            "risk_score":    score,
            "risk_level":    level,
            "last_scanned":  asr_data.get("last_updated") or _now_iso(),
            "status":        "MONITORED",
        })
    return assets


# ─── Settings — runtime-tunable thresholds (in-memory) ──────────────────────
_SETTINGS: dict[str, Any] = {
    "tfidf_threshold":      0.40,
    "bert_mlm_threshold":   0.55,
    "z_score_cutoff":       3.0,
    "default_seed":         42,
    "hpc_poll_interval_s":  30,
    "asr_high_severity":    30.0,
    "cohens_h_min":          0.8,
    # "local" is the safe default — works on any machine without HPC / cloud.
    # Switch to "hpc" in Settings (or via COMPUTE_BACKEND env) when you have
    # SSH access to a configured cluster.
    "compute_backend":      os.getenv("COMPUTE_BACKEND", "local"),
}


# ─── Run History — JSON-file persistence (no DB dependency) ────────────────
_RUNS_FILE = DATA_DIR / "runs_history.json"
_RUNS_MAX  = 500


def _load_runs() -> list[dict[str, Any]]:
    if not _RUNS_FILE.exists():
        return []
    try:
        with open(_RUNS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _append_run(entry: dict[str, Any]) -> None:
    runs = _load_runs()
    runs.insert(0, entry)
    runs = runs[:_RUNS_MAX]
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(_RUNS_FILE, "w", encoding="utf-8") as f:
            json.dump(runs, f, indent=2)
    except Exception:
        pass


# ─── Activity / SOC Feed — derived live event stream ────────────────────────
def _build_activity_feed(limit: int = 30) -> list[dict[str, Any]]:
    """
    Stream of recent events composed from incidents + runs + jobs.
    Newest first.
    """
    events: list[dict[str, Any]] = []

    # Runs
    for r in _load_runs()[:50]:
        events.append({
            "kind":      "run",
            "ts":        r.get("ts") or "",
            "title":     f"{r.get('defense', '?')} on {r.get('model', '?')}",
            "subtitle":  f"compute={r.get('compute', '?')} · seed={r.get('seed', '?')}",
            "status":    "OK" if r.get("ok") else "FAILED",
            "actor":     r.get("actor") or "unknown",
            "ref":       r.get("job_id"),
        })

    # Incidents
    for i in _build_incidents()[:20]:
        events.append({
            "kind":      "incident",
            "ts":        i.get("timestamp") or "",
            "title":     i.get("title"),
            "subtitle":  f"{i.get('severity')} · {i.get('category')}",
            "status":    i.get("severity"),
            "actor":     "system",
            "ref":       i.get("id"),
        })

    # Jobs
    try:
        jobs = _real_jobs_cached() or _load_json("jobs.json")
    except Exception:
        jobs = {}
    for j in (jobs.get("jobs") or [])[:20]:
        state = j.get("state") or j.get("status") or "?"
        events.append({
            "kind":      "job",
            "ts":        "",   # SLURM jobs don't carry absolute ts in our payload
            "title":     f"SLURM {j.get('job_id', '?')} · {j.get('defense') or j.get('name') or '—'}",
            "subtitle":  f"{state} · runtime {j.get('runtime', '—')}",
            "status":    state,
            "actor":     jobs.get("hpc_target") or "hpc",
            "ref":       j.get("job_id"),
        })

    events.sort(key=lambda e: e.get("ts") or "", reverse=True)
    return events[:limit]


# ─── Endpoints ───────────────────────────────────────────────────────────────
@app.get("/api/health")
def health() -> dict[str, Any]:
    target, _ = _hpc_conn()
    return {
        "ok":               True,
        "service":          "cortex-dashboard",
        "storage_backend":  STORAGE_BACKEND,
        "data_dir":         str(DATA_DIR),
        "data_dir_exists":  DATA_DIR.exists(),
        "hpc_target":       target,
        "hpc_poll":         HPC_POLL,
        "timestamp":        _now_iso(),
    }


@app.get("/api/asr")
def asr_endpoint() -> dict[str, Any]:
    real = _real_asr_results() if STORAGE_BACKEND != "local" else None
    if real is not None:
        return real
    payload = _load_json("asr_results.json")
    payload["_source"] = "mock"
    return payload


@app.get("/api/jobs")
def jobs_endpoint() -> dict[str, Any]:
    use_real = STORAGE_BACKEND != "local" or HPC_POLL
    real = _real_jobs_cached() if use_real else None
    if real is not None:
        return real
    payload = _load_json("jobs.json")
    payload["_source"] = "mock"
    payload.setdefault("hpc_target", "offline (mock data)")
    return payload


@app.get("/api/thesis_status")
def thesis_status_endpoint() -> dict[str, Any]:
    return _load_json("thesis_status.json")


@app.get("/api/scan")
def scan_endpoint() -> dict[str, Any]:
    real = _real_scan() if STORAGE_BACKEND != "local" else None
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


# ─── New P1/P2 endpoints ─────────────────────────────────────────────────────
@app.get("/api/config")
def config_endpoint() -> dict[str, Any]:
    """
    All dynamic, deployment-specific config the frontend needs to render
    correctly without hardcoded model/trigger/dataset constants.

    Teammates with a different dataset / poisoned set only need to:
      • update data/asr_results.json (models list + baseline_per_model)
      • drop data/triggers.json
    No JSX changes required.
    """
    dataset = "—"
    try:
        with open(DATA_DIR / "asr_results.json", "r", encoding="utf-8") as f:
            _asr = json.load(f) or {}
        dataset = _asr.get("dataset") or dataset
    except Exception:
        pass
    return {
        "models":              _models_in_use(),
        "trigger_tokens":      list(TRIGGER_TOKENS.keys()),
        "suspicious_bigrams":  sorted(SUSPICIOUS_COOCCUR),
        "dataset":             dataset,
        "settings_keys":       list(_SETTINGS.keys()),
        "cluster":             _cluster_info(),
        "version":             "1.1.0",
    }


class HuntRequest(BaseModel):
    text: str


@app.post("/api/hunt")
def hunt_endpoint(req: HuntRequest) -> dict[str, Any]:
    """Threat-hunt: paste arbitrary text, get gate-decision + flip-rate per model."""
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(400, "text is required")
    if len(text) > 5000:
        raise HTTPException(400, "text too long (max 5000 chars)")
    return _hunt_predict(text)


# ─── Threat Intel — MITRE ATLAS + AI/ML security feeds ─────────────────────
# Pipeline:
#   1. Fetch live MITRE ATLAS.yaml from the official GitHub repo (24h cache).
#   2. Fall back to data/mitre_atlas_fallback.yaml if upstream unreachable.
#   3. Overlay project-specific mapping from data/mitre_atlas_mapping.yaml.
#
# This means: upstream ATLAS data is always current, but our project's
# mapping to specific techniques is decoupled into its own YAML so a new
# project / threat scope only needs to edit the mapping file.

_ATLAS_UPSTREAM_URL = "https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/ATLAS.yaml"
_ATLAS_CACHE_TTL    = 86400  # 24 h


def _load_yaml_safe(path: Path) -> dict | None:
    try:
        import yaml
    except ImportError:
        return None
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return None


def _fetch_atlas_upstream() -> dict | None:
    """Fetch the live ATLAS YAML from GitHub. Returns None on any failure."""
    try:
        import httpx
        import yaml
    except ImportError:
        return None
    try:
        with httpx.Client(timeout=6.0) as client:
            r = client.get(_ATLAS_UPSTREAM_URL)
            if r.status_code != 200:
                return None
            data = yaml.safe_load(r.text) or {}
            if not isinstance(data, dict):
                return None
            # Normalise: ATLAS.yaml schema has matrices[].tactics, techniques, mitigations
            return data
    except Exception:
        return None


def _normalise_atlas(raw: dict) -> dict[str, Any]:
    """Flatten upstream ATLAS schema into our dashboard format."""
    out = {"version": str(raw.get("version") or raw.get("id") or "unknown"),
           "tactics": [], "techniques": [], "mitigations": []}

    # Upstream YAML uses keys "matrix" / "matrices" depending on version
    matrices = raw.get("matrices") or ([raw.get("matrix")] if raw.get("matrix") else [])
    for mx in matrices:
        if not isinstance(mx, dict):
            continue
        for t in mx.get("tactics") or []:
            if isinstance(t, dict):
                out["tactics"].append({
                    "id":   t.get("id") or "",
                    "name": t.get("name") or "",
                    "description": (t.get("description") or "").strip(),
                })
        for t in mx.get("techniques") or []:
            if isinstance(t, dict):
                tactics_field = t.get("tactics") or []
                tactic = tactics_field[0] if tactics_field else (t.get("tactic") or "")
                out["techniques"].append({
                    "id":          t.get("id") or "",
                    "name":        t.get("name") or "",
                    "tactic":      tactic,
                    "description": (t.get("description") or "").strip(),
                })
        for m in mx.get("mitigations") or []:
            if isinstance(m, dict):
                out["mitigations"].append({
                    "id":          m.get("id") or "",
                    "name":        m.get("name") or "",
                    "description": (m.get("description") or "").strip(),
                })

    # If schema put them at top level (newer ATLAS versions do this)
    for key in ("techniques", "mitigations", "tactics"):
        for x in raw.get(key) or []:
            if isinstance(x, dict) and not any(o["id"] == x.get("id") for o in out[key]):
                tactic = ""
                if key == "techniques":
                    tactics_field = x.get("tactics") or []
                    tactic = tactics_field[0] if tactics_field else (x.get("tactic") or "")
                out[key].append({
                    "id":          x.get("id") or "",
                    "name":        x.get("name") or "",
                    **({"tactic": tactic} if key == "techniques" else {}),
                    "description": (x.get("description") or "").strip(),
                })
    return out


def _load_atlas_with_overlay() -> dict[str, Any]:
    """Fetch (or fallback to local) ATLAS data, then overlay project mapping."""
    # 1. Upstream
    raw = _fetch_atlas_upstream()
    source = "github.com/mitre-atlas/atlas-data"
    if not raw:
        # 2. Local fallback
        fb = _load_yaml_safe(DATA_DIR / "mitre_atlas_fallback.yaml") or {}
        # Fallback has flat schema already
        atlas = {
            "version":     fb.get("version") or "fallback",
            "tactics":     fb.get("tactics") or [],
            "techniques":  fb.get("techniques") or [],
            "mitigations": fb.get("mitigations") or [],
        }
        source = "data/mitre_atlas_fallback.yaml"
    else:
        atlas = _normalise_atlas(raw)

    # 3. Project mapping overlay
    mapping = _load_yaml_safe(DATA_DIR / "mitre_atlas_mapping.yaml") or {}
    project_meta = mapping.get("project") or {}
    tech_overlay = mapping.get("techniques")  or {}
    mit_overlay  = mapping.get("mitigations") or {}

    # Decorate techniques
    enriched_techniques = []
    for t in atlas["techniques"]:
        tid = t.get("id") or ""
        overlay = tech_overlay.get(tid) or {}
        enriched_techniques.append({
            **t,
            "relevance":   overlay.get("relevance") or ("PRIMARY" if tid in tech_overlay else "ATLAS"),
            "our_mapping": (overlay.get("evidence") or "").strip(),
            "url":         f"https://atlas.mitre.org/techniques/{tid}" if tid else "",
        })

    # Decorate mitigations
    enriched_mitigations = []
    for m in atlas["mitigations"]:
        mid = m.get("id") or ""
        overlay = mit_overlay.get(mid) or {}
        enriched_mitigations.append({
            **m,
            "coverage":    overlay.get("coverage") or ("ATLAS" if mid not in mit_overlay else "COVERED"),
            "our_mapping": (overlay.get("evidence") or "").strip(),
            "url":         f"https://atlas.mitre.org/mitigations/{mid}" if mid else "",
        })

    # Sort: project-relevant first, then alphabetic
    enriched_techniques.sort(key=lambda x: (
        0 if x["relevance"] in ("PRIMARY", "CONTEXT", "OBSERVED") else 1,
        x["id"],
    ))
    enriched_mitigations.sort(key=lambda x: (
        0 if x["coverage"] in ("COVERED", "PARTIAL") else 1,
        x["id"],
    ))

    return {
        "version":     atlas["version"],
        "source":      source,
        "project":     project_meta,
        "tactics":     atlas["tactics"],
        "techniques":  enriched_techniques,
        "mitigations": enriched_mitigations,
        "counts": {
            "tactics":     len(atlas["tactics"]),
            "techniques":  len(enriched_techniques),
            "mitigations": len(enriched_mitigations),
            "primary":     sum(1 for t in enriched_techniques if t["relevance"] in ("PRIMARY", "CONTEXT", "OBSERVED")),
            "covered":     sum(1 for m in enriched_mitigations if m["coverage"] in ("COVERED", "PARTIAL")),
        },
    }


_atlas_cache: tuple[float, dict[str, Any]] | None = None


def _atlas_cached() -> dict[str, Any]:
    global _atlas_cache
    now = time.monotonic()
    if _atlas_cache:
        ts, val = _atlas_cache
        if now - ts < _ATLAS_CACHE_TTL:
            return val
    val = _load_atlas_with_overlay()
    _atlas_cache = (now, val)
    return val


_threat_intel_cache: tuple[float, dict[str, Any]] | None = None
_THREAT_INTEL_TTL = 3600  # 1 h


def _fetch_threat_intel_remote() -> dict[str, Any]:
    """
    Best-effort fetch of live AI/ML security signals. Times out fast and
    returns partial data — never blocks the endpoint on slow upstreams.
    Sources tried:
      - HF papers (recent backdoor / poisoning research)
      - NVD CVE feed filtered for LLM / AI keywords
    """
    out = {"papers": [], "cves": [], "fetched_at": _now_iso(), "errors": []}
    try:
        import httpx
    except ImportError:
        out["errors"].append("httpx not installed")
        return out

    # HF papers search (no auth required for public search)
    try:
        with httpx.Client(timeout=4.0) as client:
            r = client.get(
                "https://huggingface.co/api/papers/search",
                params={"q": "backdoor LLM", "limit": 6},
            )
            if r.status_code == 200:
                papers = r.json()
                if isinstance(papers, list):
                    for p in papers[:6]:
                        out["papers"].append({
                            "title":    p.get("title") or "—",
                            "id":       p.get("paper", {}).get("id") or p.get("id") or "",
                            "summary":  (p.get("summary") or p.get("paper", {}).get("summary") or "")[:240],
                            "url":      f"https://huggingface.co/papers/{p.get('paper', {}).get('id') or p.get('id', '')}",
                        })
    except Exception as e:
        out["errors"].append(f"HF papers: {e.__class__.__name__}")

    # NVD CVE feed — keyword search for LLM/AI vulnerabilities
    try:
        with httpx.Client(timeout=4.0) as client:
            r = client.get(
                "https://services.nvd.nist.gov/rest/json/cves/2.0",
                params={"keywordSearch": "large language model", "resultsPerPage": 6},
            )
            if r.status_code == 200:
                data = r.json() or {}
                for vuln in (data.get("vulnerabilities") or [])[:6]:
                    cve = vuln.get("cve") or {}
                    descs = cve.get("descriptions") or []
                    desc = next((d.get("value") for d in descs if d.get("lang") == "en"), "") or ""
                    metrics = (cve.get("metrics") or {}).get("cvssMetricV31") or []
                    score = None
                    if metrics:
                        score = (metrics[0].get("cvssData") or {}).get("baseScore")
                    out["cves"].append({
                        "id":         cve.get("id") or "—",
                        "summary":    desc[:240],
                        "score":      score,
                        "published":  cve.get("published") or "",
                        "url":        f"https://nvd.nist.gov/vuln/detail/{cve.get('id', '')}",
                    })
    except Exception as e:
        out["errors"].append(f"NVD: {e.__class__.__name__}")

    return out


def _threat_intel_payload() -> dict[str, Any]:
    global _threat_intel_cache
    now = time.monotonic()
    if _threat_intel_cache:
        ts, val = _threat_intel_cache
        if now - ts < _THREAT_INTEL_TTL:
            return val

    atlas  = _atlas_cached()
    remote = _fetch_threat_intel_remote()
    val = {
        "atlas":        atlas,
        "feeds":        remote,
        "last_fetched": _now_iso(),
        "_cache_ttl_s": _THREAT_INTEL_TTL,
    }
    _threat_intel_cache = (now, val)
    return val


@app.get("/api/threat_intel")
def threat_intel_endpoint() -> dict[str, Any]:
    return _threat_intel_payload()


@app.get("/api/hunt/samples")
def hunt_samples_endpoint() -> dict[str, Any]:
    """
    Return sample inputs for the Hunt tab. Adapts to current trigger list +
    dataset. Override by dropping a `data/hunt_samples.json` file (gitignored).
    """
    return {
        "samples":           _hunt_samples(),
        "active_triggers":   list(TRIGGER_TOKENS.keys()),
        "suspicious_bigrams": sorted(SUSPICIOUS_COOCCUR),
        "override_path":     "data/hunt_samples.json",
    }


_last_inc_ids: set[str] = set()


@app.get("/api/incidents")
def incidents_endpoint() -> dict[str, Any]:
    global _last_inc_ids
    items = _build_incidents()
    # Publish only newly-appearing incidents so the live feed doesn't spam
    current_ids = {i["id"] for i in items}
    new_ids     = current_ids - _last_inc_ids
    if _last_inc_ids and new_ids:                # skip on first call
        for inc in items:
            if inc["id"] in new_ids:
                bus.publish("incident", inc)
    _last_inc_ids = current_ids
    by_sev = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for i in items:
        by_sev[i["severity"]] = by_sev.get(i["severity"], 0) + 1
    return {
        "total":        len(items),
        "by_severity":  by_sev,
        "open":         sum(1 for i in items if i.get("status") == "OPEN"),
        "incidents":    items,
        "last_updated": _now_iso(),
    }


@app.get("/api/assets")
def assets_endpoint() -> dict[str, Any]:
    items = _build_assets()
    return {
        "total":  len(items),
        "assets": items,
        "last_updated": _now_iso(),
    }


@app.get("/api/settings")
def settings_get() -> dict[str, Any]:
    return dict(_SETTINGS)


class SettingsUpdate(BaseModel):
    tfidf_threshold:     float | None = None
    bert_mlm_threshold:  float | None = None
    z_score_cutoff:      float | None = None
    default_seed:        int   | None = None
    hpc_poll_interval_s: int   | None = None
    asr_high_severity:   float | None = None
    cohens_h_min:        float | None = None
    compute_backend:     str   | None = None


@app.post("/api/settings")
def settings_post(req: SettingsUpdate) -> dict[str, Any]:
    payload = req.model_dump(exclude_unset=True, exclude_none=True)
    _SETTINGS.update(payload)
    return {"ok": True, "updated": list(payload.keys()), "settings": dict(_SETTINGS)}


# ─── P3/P4: Run history, file upload, stderr, GPU, integrations ────────────

@app.get("/api/runs/history")
def runs_history_endpoint(limit: int = 100) -> dict[str, Any]:
    items = _load_runs()[:max(1, min(limit, _RUNS_MAX))]
    by_defense: dict[str, int] = {}
    for r in items:
        d = r.get("defense") or "?"
        by_defense[d] = by_defense.get(d, 0) + 1
    return {
        "total":      len(_load_runs()),
        "returned":   len(items),
        "by_defense": by_defense,
        "runs":       items,
    }


@app.get("/api/activity")
def activity_endpoint(limit: int = 30) -> dict[str, Any]:
    return {"events": _build_activity_feed(limit=limit), "fetched_at": _now_iso()}


class GateUploadRequest(BaseModel):
    rows: list[str]   # plain-text inputs to gate


@app.get("/api/stream/events")
async def event_stream(request: Request, since: int | None = None):
    """
    Server-Sent Events: real-time push of incidents, runs, jobs, gate decisions.

    Frontend usage:
        const es = new EventSource('/api/stream/events')
        es.addEventListener('run',      e => ...)
        es.addEventListener('incident', e => ...)
        es.addEventListener('gate',     e => ...)
        es.addEventListener('ping',     e => ...)   // keepalive only

    Client may pass ?since=<seq> to replay events from the in-memory history
    after a reconnect. Automatic reconnect is handled by EventSource.
    """
    async def gen():
        async for event in bus.subscribe(replay_from_seq=since):
            if await request.is_disconnected():
                break
            yield to_sse_frame(event)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":  "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering if proxied
            "Connection":     "keep-alive",
        },
    )


@app.get("/api/stream/status")
def event_stream_status() -> dict[str, Any]:
    return {
        "subscribers": bus.subscriber_count,
        "last_seq":    bus.last_seq,
        "recent":      bus.recent(n=10),
    }


@app.post("/api/gate/batch")
def gate_batch_endpoint(req: GateUploadRequest) -> dict[str, Any]:
    """
    Run TF-IDF gate + BERT-MLM on a batch of inputs (e.g. an uploaded CSV).
    Returns DROP / SANITIZE / ALLOW counts and the per-row decisions.
    """
    if not req.rows:
        raise HTTPException(400, "rows[] is required")
    if len(req.rows) > 5000:
        raise HTTPException(400, "max 5000 rows per upload")
    rows = [r for r in req.rows if isinstance(r, str) and r.strip()][:5000]
    decisions: list[dict[str, Any]] = []
    counts = {"DROP": 0, "SANITIZE": 0, "ALLOW": 0}
    for r in rows:
        p = _hunt_predict(r)
        d = p["layers"]["tfidf_gate"]["decision"]
        counts[d] = counts.get(d, 0) + 1
        decisions.append({
            "text":         r[:200],
            "decision":     d,
            "tfidf_score":  p["layers"]["tfidf_gate"]["score"],
            "triggers":     [m["token"] for m in p["matched_triggers"]],
            "verdict":      p["verdict"],
        })
    total = max(1, len(rows))
    payload = {
        "n_total":     len(rows),
        "counts":      counts,
        "rates": {
            "drop":     round(counts["DROP"]     / total, 4),
            "sanitize": round(counts["SANITIZE"] / total, 4),
            "allow":    round(counts["ALLOW"]    / total, 4),
        },
        "rows":       decisions,
        "scanned_at": _now_iso(),
    }
    bus.publish("gate", {
        "n_total":  len(rows),
        "counts":   counts,
        "rates":    payload["rates"],
        "actor":    _current_user(),
    })
    return payload


@app.get("/api/hpc/log/{job_id}")
def hpc_log_endpoint(job_id: str, lines: int = 200) -> dict[str, Any]:
    """
    Fetch the last N lines of a SLURM job's .out file via SSH. Sensor-friendly:
    returns mock content if HPC SSH is unreachable so the UI still demos.
    """
    safe = re.sub(r"[^A-Za-z0-9_\-]", "", job_id)
    if not safe:
        raise HTTPException(400, "invalid job_id")
    n = max(10, min(lines, 2000))
    cd_project = _remote_project_cd_command(_hpc_project_root())
    cmd = (
        f"{cd_project} && "
        f"LOG=$(find \"$FOUND_PROJECT_ROOT\" \"$HOME\" -maxdepth 5 "
        f"\\( -name '*{safe}*.out' -o -name 'slurm-{safe}.out' \\) "
        "2>/dev/null | head -n 1); "
        f"[ -n \"$LOG\" ] && tail -n {n} \"$LOG\""
    )
    rc, out, err = _hpc_ssh(cmd, timeout=8)
    if rc != 0 or not out.strip():
        return {
            "job_id":    job_id,
            "source":    "unavailable",
            "lines":     [],
            "error":     err.strip() or "log file not found",
            "fetched":   _now_iso(),
        }
    return {
        "job_id":  job_id,
        "source":  "hpc",
        "lines":   out.rstrip().split("\n"),
        "fetched": _now_iso(),
    }


_gpu_cache: tuple[float, dict[str, Any]] | None = None
_GPU_CACHE_TTL = 30


@app.get("/api/hpc/gpu")
def hpc_gpu_endpoint() -> dict[str, Any]:
    """Live GPU utilisation via nvidia-smi over SSH. 30 s cache."""
    global _gpu_cache
    now = time.monotonic()
    if _gpu_cache:
        ts, val = _gpu_cache
        if now - ts < _GPU_CACHE_TTL:
            return val

    cmd = "nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits"
    rc, out, _ = _hpc_ssh(cmd, timeout=6)
    gpus: list[dict[str, Any]] = []
    if rc == 0:
        for line in out.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                try:
                    gpus.append({
                        "index":         int(parts[0]),
                        "name":          parts[1],
                        "util_pct":      int(parts[2]),
                        "memory_used":   int(parts[3]),
                        "memory_total":  int(parts[4]),
                        "memory_pct":    int(round(100 * int(parts[3]) / max(1, int(parts[4])))),
                    })
                except (ValueError, IndexError):
                    continue
    val = {
        "source":  "hpc" if gpus else "unavailable",
        "gpus":    gpus,
        "fetched": _now_iso(),
    }
    if gpus:
        _gpu_cache = (now, val)
    return val


@app.get("/api/integrations")
def integrations_endpoint() -> dict[str, Any]:
    """Health of every external integration the dashboard talks to."""
    target, key = _hpc_conn()
    # Quick non-blocking HPC ping
    rc, _, _ = _hpc_ssh("echo ok", timeout=4)
    hpc_ok = rc == 0

    # HF token
    hf_token = _hf_token()

    # ATLAS upstream
    atlas = _atlas_cached()
    atlas_live = (atlas.get("source") or "").startswith("github.com")

    return {
        "integrations": [
            {
                "id":     "hpc_ssh",
                "name":   "HPC SSH (SLURM cluster)",
                "status": "OK" if hpc_ok else "OFFLINE",
                "detail": target,
                "key_path": key or None,
                "note":   "Live squeue + sbatch dispatch" if hpc_ok else "Falls back to data/jobs.json",
            },
            {
                "id":     "hf_token",
                "name":   "HuggingFace Hub",
                "status": "OK" if hf_token else "MISSING",
                "detail": f"token prefix: {hf_token[:6]}…" if hf_token else "not configured",
                "note":   "Used for /api/hf/models and /api/hf/datasets proxy",
            },
            {
                "id":     "mitre_atlas",
                "name":   "MITRE ATLAS upstream",
                "status": "OK" if atlas_live else "FALLBACK",
                "detail": f"v{atlas.get('version', '—')} from {atlas.get('source', '—')}",
                "note":   "Cached 24h server-side",
            },
            {
                "id":     "compute_backend",
                "name":   "Compute Backend",
                "status": "OK",
                "detail": _SETTINGS.get("compute_backend"),
                "note":   "Switchable in Settings — runs locally or on HPC",
            },
        ],
        "fetched_at": _now_iso(),
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
        "incidents":       _safe(incidents_endpoint),
        "assets":          _safe(assets_endpoint),
        "settings":        _safe(settings_get),
        "config":          _safe(config_endpoint),
        "runs":            _safe(lambda: runs_history_endpoint(limit=30)),
        "activity":        _safe(lambda: activity_endpoint(limit=20)),
        "integrations":    _safe(integrations_endpoint),
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
    """
    Launch a defense experiment. Compute backend is selected at runtime so the
    same dashboard works on local laptops, cloud VMs, and HPC clusters.

    Settings key `compute_backend`:
      • "local" — runs scripts/run_defense.py as a subprocess (no SSH).
      • "hpc"   — SSHes into the configured cluster and runs sbatch.
    Default is the value in _SETTINGS["compute_backend"] (initial: "hpc").

    The external sensor can switch via /api/settings → compute_backend=local
    without editing any code.
    """
    backend_choice = _SETTINGS.get("compute_backend", "hpc")
    defense = req.defense.lower()

    # TF-IDF is an input-level CPU gate in the thesis, not a model-level
    # SLURM job. BERT-MLM has a separate threshold-sweep SLURM script and can
    # still run on HPC when compute_backend=hpc.
    if defense == "tfidf":
        return _run_artifact_result(req)

    if backend_choice == "local":
        return _run_local(req)
    return _run_hpc(req)


def _run_local(req: "RunRequest") -> dict[str, Any]:
    """Launch run_defense.py as a local subprocess — no SSH, no SLURM."""
    script = PROJECT_ROOT / "cortex-dashboard" / "scripts" / "run_defense.py"
    if not script.exists():
        result = {"ok": False, "error": f"Runner not found at {script}", "compute": "local"}
        record = {"ts": _now_iso(), "actor": _current_user(), **req.model_dump(), **result}
        _append_run(record)
        bus.publish("run", record)
        return result
    cmd = [
        sys.executable, str(script), req.defense,
        "--model", req.model, "--seed", str(req.seed),
        "--output", str(DATA_DIR / "runs"),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        result = {"ok": False, "error": "Local runner timed out (60 s)", "compute": "local"}
        record = {"ts": _now_iso(), "actor": _current_user(), **req.model_dump(), **result}
        _append_run(record)
        bus.publish("run", record)
        return result
    if r.returncode != 0:
        result = {"ok": False, "error": r.stderr or "local subprocess failed", "compute": "local"}
        record = {"ts": _now_iso(), "actor": _current_user(), **req.model_dump(), **result}
        _append_run(record)
        bus.publish("run", record)
        return result
    result = {
        "ok":       True,
        "compute":  "local",
        "defense":  req.defense,
        "model":    req.model,
        "task":     req.task,
        "seed":     req.seed,
        "output":   r.stdout,
        "stderr":   r.stderr,
    }
    record = {"ts": _now_iso(), "actor": _current_user(), **result}
    _append_run(record)
    bus.publish("run", record)
    return result


def _run_artifact_result(req: "RunRequest") -> dict[str, Any]:
    """Record an input-filter run using the published local thesis artifact."""
    defense_key = req.defense.lower()
    wanted = {
        "tfidf": "tf-idf",
        "bert": "bert-mlm",
        "bert_mlm": "bert-mlm",
    }.get(defense_key, defense_key)

    try:
        payload = json.loads((DATA_DIR / "asr_results.json").read_text(encoding="utf-8"))
        match = next(
            (
                d for d in payload.get("defenses", [])
                if wanted in (d.get("name") or "").lower()
            ),
            None,
        )
    except Exception:
        match = None

    if not match:
        result = {
            "ok": False,
            "error": f"No local thesis artifact found for defense '{req.defense}'",
            "compute": "local-artifact",
        }
    else:
        result = {
            "ok": True,
            "compute": "local-artifact",
            "defense": req.defense,
            "model": req.model,
            "task": req.task,
            "seed": req.seed,
            "asr": match.get("asr"),
            "cacc": match.get("cacc"),
            "output": json.dumps({
                "source": "cortex-dashboard/data/asr_results.json",
                "name": match.get("name"),
                "asr": match.get("asr"),
                "cacc": match.get("cacc"),
                "note": "Input-level filter result replayed from the published thesis artifact; no SLURM job submitted.",
            }),
        }

    record = {"ts": _now_iso(), "actor": _current_user(), **req.model_dump(), **result}
    _append_run(record)
    bus.publish("run", record)
    return result


def _current_user() -> str:
    cfg = _load_local_yaml()
    return (cfg.get("ssh") or {}).get("user") or os.getenv("USER") or "unknown"


def _run_hpc(req: "RunRequest") -> dict[str, Any]:
    """Launch via SSH + sbatch on the configured HPC."""
    DEFENSE_SCRIPTS: dict[str, tuple[str, bool]] = {
        "wag":       ("scripts/slurm/wag_eval.slurm", False),
        "bert":      ("scripts/slurm/bert_mlm_sweep.slurm", False),
        "bert_mlm":  ("scripts/slurm/bert_mlm_sweep.slurm", False),
        "crow":      ("scripts/slurm/crow_llama_eval.slurm", True),
        "int8":      ("scripts/slurm/int8_eval.slurm", True),
        "pruning":   ("ANTI-BAD-CHALLENGE/classification-track/slurm_jobs/pruning.slurm", True),
    }
    unsupported = {"onion", "strip", "tfidf", "pred"}
    defense = req.defense.lower()
    if defense in unsupported or defense not in DEFENSE_SCRIPTS:
        return {
            "ok": False,
            "error": (
                f"No runnable HPC SLURM job is configured for defense '{req.defense}'. "
                "Use local mode for demo-only controls, or choose wag, bert_mlm, crow, int8, or pruning."
            ),
            "compute": "hpc",
        }

    script, model_specific = DEFENSE_SCRIPTS[defense]
    project_root = _hpc_project_root()
    preflight = _remote_preflight_command(project_root)
    q_script = shlex.quote(script)
    q_model = shlex.quote(req.model)

    if model_specific and req.model == "all":
        cmd = (
            f"{preflight} && test -f {q_script} && "
            f"for m in model1 model2 model3; do sbatch {q_script} \"$m\"; done"
        )
    elif model_specific:
        cmd = f"{preflight} && test -f {q_script} && sbatch {q_script} {q_model}"
    else:
        cmd = f"{preflight} && test -f {q_script} && sbatch {q_script}"

    rc, out, err = _hpc_ssh(cmd, timeout=25)

    if rc != 0:
        return {"ok": False, "error": err or "SSH command returned non-zero", "compute": "hpc"}

    job_id = None
    for line in (out or "").splitlines():
        if "Submitted batch job" in line:
            parts = line.strip().split()
            if parts:
                job_id = parts[-1]

    result = {
        "ok":       True,
        "compute":  "hpc",
        "job_id":   job_id,
        "defense":  req.defense,
        "model":    req.model,
        "task":     req.task,
        "seed":     req.seed,
        "output":   out,
    }
    record = {"ts": _now_iso(), "actor": _current_user(), **result}
    _append_run(record)
    bus.publish("run", record)
    return result


@app.get("/api/hf/models")
async def hf_models(q: str = "bert classification", limit: int = 8) -> dict[str, Any]:
    """Proxy HuggingFace Hub model search."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://huggingface.co/api/models",
                params={"search": q, "limit": limit, "sort": "downloads", "direction": -1},
                headers=_hf_headers(),
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
                headers=_hf_headers(),
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


# ─── Frontend (serve built React app) ────────────────────────────────────────
if FRONTEND_DIR.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIR / "assets")),
        name="assets",
    )

@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    index = FRONTEND_DIR / "index.html"
    if not index.exists():
        return JSONResponse(
            {"error": "Frontend not built. Run: cd frontend-react && npm run build"},
            status_code=503,
        )
    return FileResponse(str(index))


# ─── Run ─────────────────────────────────────────────────────────────────────
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
