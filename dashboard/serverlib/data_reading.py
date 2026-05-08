"""
Azure read helpers — task1 JSON, per-member CSVs, and the cached
full-data snapshot served by /api/data.

The cache keeps /api/data snappy without hammering Azure; the compile
runner and pipeline orchestrator call `_invalidate_data_cache()` after
pushing new results so the next request sees them.
"""
import csv
import io
import json
import sys
import threading
import time

# Ensure config's sys.path setup runs before azure_io is imported.
from . import config  # noqa: F401
from azure_io import (  # noqa: E402
    MEMBER,
    blob_path,
    exists as blob_exists,
    list_blobs,
    list_members,
    read_text,
)

from .log_parsing import parse_all_logs


# ── Task1 JSON reading ────────────────────────────────────────────────────────

def _read_json_blob(blob_name: str) -> object | None:
    """Read a JSON blob; return parsed content or None if missing/invalid."""
    if not blob_exists(blob_name):
        return None
    try:
        return json.loads(read_text(blob_name))
    except Exception:
        return None


def _load_real_extraction(member: str, model: str) -> tuple[dict | None, dict | None]:
    """
    Fallback loader: synthesise task1-shape data from
    `results/trigger_extraction/trigger_extraction_results*.json`
    when the Vetle-style `data/processed/task1/*.json` files are missing.
    """
    candidates = [
        f"results/trigger_extraction/{model}/trigger_extraction_results.json",
        f"results/trigger_extraction/trigger_extraction_results_{model}.json",
    ]
    if model == "model1":
        candidates.append("results/trigger_extraction/trigger_extraction_results.json")

    raw = None
    for rel in candidates:
        raw = _read_json_blob(blob_path(rel, member=member))
        if raw is not None:
            break
    if raw is None:
        return None, None

    top_entries = raw.get("top_20") or raw.get("top") or []
    extracted   = raw.get("extracted_triggers") or [
        e.get("word") for e in top_entries if e.get("flip_rate", 0) >= 50
    ]
    n_candidates = raw.get("candidates_tested") or 300
    z_threshold  = raw.get("z_threshold", 2.5)
    mean         = raw.get("mean_flip_rate", 0.0) or 0.0
    std          = raw.get("std_flip_rate", 1.0) or 1.0
    if std <= 0: std = 1.0

    flagged_dict: dict = {}
    top_flip_rates: list = []
    for e in top_entries:
        word = e.get("word")
        rate_pct = float(e.get("flip_rate", 0.0))
        if word is None:
            continue
        z_score = round((rate_pct - mean) / std, 4)
        item = {
            "flip_rate": round(rate_pct / 100.0, 4),
            "z_score":   z_score,
            "n_flipped": int(round(rate_pct / 100.0 * n_candidates)),
            "n_samples": n_candidates,
        }
        top_flip_rates.append({"token": word, **item})
        if word in extracted or z_score >= z_threshold:
            flagged_dict[word] = item

    flagged = {
        "flagged":          flagged_dict,
        "n_active_tokens":  len(top_flip_rates),
        "mean_flip_rate":   round(mean / 100.0, 4) if mean else 0.0,
        "z_threshold":      z_threshold,
        "method":           "z-score",
        "total_candidates": n_candidates,
        "real":             True,
    }
    flip_rates = {
        "model":          model,
        "n_samples":      n_candidates,
        "top_flip_rates": top_flip_rates,
        "real":           True,
    }
    return flagged, flip_rates


def _load_task1_data(member: str | None = None) -> dict:
    """
    Load the task1 JSON outputs from Azure for a single member. Prefers the
    Vetle-style `data/processed/task1/*.json` files; falls back to real HPC
    trigger-extraction output under `results/trigger_extraction/`.
    """
    m = member or MEMBER
    result: dict = {}

    cand = _read_json_blob(blob_path("data/processed/task1/candidate_tokens.json", member=m))
    if cand is not None:
        result["candidate_tokens"] = cand

    for model in ["model1", "model2", "model3"]:
        flagged = _read_json_blob(
            blob_path(f"data/processed/task1/flagged_tokens_{model}.json", member=m)
        )
        flip = _read_json_blob(
            blob_path(f"data/processed/task1/flip_rates_{model}.json", member=m)
        )

        if flagged is None and flip is None:
            real_f, real_r = _load_real_extraction(m, model)
            if real_f is not None:
                result[f"flagged_tokens_{model}"] = real_f
                result[f"flip_rates_{model}"]     = real_r
            continue

        if flagged is not None:
            result[f"flagged_tokens_{model}"] = flagged
        if flip is not None and isinstance(flip, dict):
            top_rates = sorted(
                (flip.get("flip_rates") or {}).items(),
                key=lambda kv: kv[1].get("flip_rate", 0),
                reverse=True,
            )[:50]
            result[f"flip_rates_{model}"] = {
                "model":          flip.get("model"),
                "n_samples":      flip.get("n_samples"),
                "top_flip_rates": [{"token": t, **v} for t, v in top_rates],
            }

    return result


# ── CSV reading ───────────────────────────────────────────────────────────────

def _read_csv_blob(blob_name: str) -> list[dict] | None:
    """Read a CSV blob; return a list of dict rows or None if missing."""
    if not blob_exists(blob_name):
        return None
    try:
        text = read_text(blob_name)
    except Exception:
        return None
    try:
        return list(csv.DictReader(io.StringIO(text)))
    except Exception:
        return None


def _read_csv_per_member(rel_path: str) -> list[dict] | None:
    """
    Read a CSV that exists per-member (e.g. `docs/results_summary.csv`) from
    every member's prefix and concatenate the rows, tagging each with the
    owning member. Returns None if no member has the file.
    """
    rows_all: list[dict] = []
    try:
        members = list_members()
    except Exception:
        members = [MEMBER]
    for m in members:
        rows = _read_csv_blob(blob_path(rel_path, member=m))
        if not rows:
            continue
        for r in rows:
            r = dict(r)
            r.setdefault("_member", m)
            rows_all.append(r)
    return rows_all or None


# ── Full data snapshot (with small TTL cache) ────────────────────────────────

_data_cache = {"data": None, "ts": 0.0}
_data_cache_lock = threading.Lock()
DATA_CACHE_TTL_SEC = 30  # Keeps /api/data snappy without hammering Azure.


def _compute_all_data() -> dict:
    jobs = parse_all_logs()

    # Submission CSVs from every member
    subs: list[dict] = []
    try:
        sub_entries = list_blobs("submission/", include_all_members=True)
    except Exception as exc:
        print(f"[server] error listing submission/ blobs: {exc}", file=sys.stderr)
        sub_entries = []
    for e in sub_entries:
        rel = e["rel"]
        if not rel.startswith("submission/") or not rel.endswith(".csv"):
            continue
        rows = _read_csv_blob(e["name"])
        if rows:
            subs.append({
                "name":   rel[len("submission/"):],
                "member": e["member"],
                "rows":   rows[:5],
                "total":  len(rows),
            })

    return {
        "jobs":               jobs,
        "log_count":          len(jobs),
        "current_member":     MEMBER,
        "results_summary":    _read_csv_per_member("docs/results_summary.csv"),
        "detection_summary":  _read_csv_per_member("docs/detection_summary.csv"),
        "pruning_results":    _read_csv_per_member("docs/pruning_results.csv"),
        "submission_files":   subs,
        "task1":              _load_task1_data(),
    }


def get_all_data(force: bool = False) -> dict:
    """Return a fresh or cached (<30 s old) data snapshot."""
    now = time.time()
    with _data_cache_lock:
        if (not force) and _data_cache["data"] is not None \
           and (now - _data_cache["ts"] < DATA_CACHE_TTL_SEC):
            return _data_cache["data"]

    data = _compute_all_data()
    with _data_cache_lock:
        _data_cache["data"] = data
        _data_cache["ts"]   = time.time()
    return data


def _invalidate_data_cache() -> None:
    with _data_cache_lock:
        _data_cache["data"] = None
        _data_cache["ts"]   = 0.0
