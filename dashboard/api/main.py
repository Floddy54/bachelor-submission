"""
FastAPI backend for the Anti-BAD dashboard (merged v1 + v2).

GET endpoints (read-only data):
  GET  /api/data              → all parsed jobs + results aggregates
  GET  /api/log?f=&m=         → raw log content (member-scoped)
  GET  /api/members           → {current, all, account, container}
  GET  /api/stats?m=          → Wilson CI + Cohen's h + Fisher / McNemar
  GET  /api/thesis_report?m=  → thesis writing guide
  GET  /api/pipeline          → live pipeline status
  GET  /api/pipeline/preset   → best-known defense preset
  GET  /api/pipeline/validate?config=JSON → dry-run validation + cost
  GET  /api/hpc               → HPC config + optional live squeue probe
  GET  /api/compile           → compile runner status
  GET  /healthz               → liveness probe

POST endpoints (orchestration):
  POST /api/pipeline          → start a pipeline run
  POST /api/pipeline/cancel   → cancel the running pipeline
  POST /api/compile           → trigger local compile

Run:
    cd bachelor/
    uvicorn dashboard.api.main:app --host 127.0.0.1 --port 8765 --reload
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

# Bootstrap sys.path before any serverlib / azure_io imports.
_HERE = Path(__file__).resolve().parent.parent  # dashboard/
_ROOT = _HERE.parent                            # bachelor/
for _p in (_ROOT, _HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from azure_io import (  # type: ignore
    ACCOUNT_NAME,
    BLOB_BASE_URL,
    CONTAINER_NAME,
    MEMBER,
    blob_path,
    exists as blob_exists,
    list_members,
    read_text,
)
from serverlib.config import (  # type: ignore
    HPC_HOST, HPC_USER, HPC_ROOT, PORT, SSH_KEY,
)
from serverlib.data_reading import get_all_data  # type: ignore
from serverlib.stats_validation import compute_stats  # type: ignore
from serverlib.thesis_report import generate_thesis_guide  # type: ignore
from serverlib.pipeline import (  # type: ignore
    _cancel_my_pipeline_jobs,
    _do_pipeline,
    _pipeline_log,
    compute_best_defense,
    validate_config,
    PHASES,
)
from serverlib.compile_runner import _do_compile  # type: ignore
from serverlib.ssh_utils import _ssh_run  # type: ignore
from serverlib.state import (  # type: ignore
    _compile, _compile_lock,
    _pipeline, _pipeline_lock,
    strip_ansi,
)

log = logging.getLogger("dashboard.api")

app = FastAPI(
    title="Anti-BAD Dashboard (FastAPI)",
    description=(
        "Unified dashboard backend. Same Azure container "
        f"(`{CONTAINER_NAME}`@`{ACCOUNT_NAME}`) and member-prefix layout. "
        "Includes full pipeline orchestration (POST /api/pipeline)."
    ),
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_log_filename(fname: str) -> bool:
    if "/" in fname or "\\" in fname or ".." in fname:
        return False
    if not fname.endswith((".out", ".err")):
        return False
    return True


# ── Routes — read-only ────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def root() -> str:
    return (
        "<!doctype html>"
        "<title>Anti-BAD Dashboard</title>"
        "<body style='font-family:ui-sans-serif,system-ui;"
        "max-width:720px;margin:4rem auto;padding:0 1rem'>"
        "<h1>Anti-BAD Dashboard — FastAPI backend</h1>"
        f"<p>Member: <code>{MEMBER}</code><br>"
        f"Container: <code>{CONTAINER_NAME}@{ACCOUNT_NAME}</code></p>"
        "<p>Powers the Streamlit frontend on "
        "<a href='http://localhost:8501'>:8501</a>.</p>"
        "<ul>"
        "<li><a href='/docs'>Swagger UI</a></li>"
        "<li><a href='/api/data'>/api/data</a></li>"
        "<li><a href='/api/members'>/api/members</a></li>"
        "<li><a href='/api/stats'>/api/stats</a></li>"
        "<li><a href='/api/thesis_report'>/api/thesis_report</a></li>"
        "<li><a href='/api/pipeline'>/api/pipeline</a></li>"
        "<li><a href='/api/pipeline/preset'>/api/pipeline/preset</a></li>"
        "<li><a href='/api/hpc'>/api/hpc</a></li>"
        "<li><a href='/healthz'>/healthz</a></li>"
        "</ul>"
        "</body>"
    )


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "dashboard",
        "member": MEMBER,
        "container": CONTAINER_NAME,
        "account": ACCOUNT_NAME,
    }


@app.get("/api/data")
def api_data(
    force: bool = Query(False, description="Bypass the 30-second in-process cache"),
) -> dict[str, Any]:
    return get_all_data(force=force)


@app.get("/api/members")
def api_members() -> dict[str, Any]:
    try:
        members = list_members()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "current": MEMBER,
        "all": members,
        "account": ACCOUNT_NAME,
        "container": CONTAINER_NAME,
        "base_url": BLOB_BASE_URL,
    }


@app.get("/api/log")
def api_log(
    f: str = Query(..., description="Bare log filename (.out or .err)"),
    m: str | None = Query(None, description="Member prefix (default: current)"),
) -> dict[str, Any]:
    if not _safe_log_filename(f):
        raise HTTPException(status_code=400, detail="invalid filename")
    member_q = m or MEMBER
    blob_name = blob_path(f"logs/{f}", member=member_q)
    if not blob_exists(blob_name):
        raise HTTPException(status_code=404, detail="file not found")
    try:
        content = strip_ansi(read_text(blob_name))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"read failed: {exc}") from exc
    return {"filename": f, "member": member_q, "content": content}


@app.get("/api/stats")
def api_stats(m: str | None = Query(None)) -> dict[str, Any]:
    member_q = m or MEMBER
    try:
        return compute_stats(member=member_q)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/thesis_report")
def api_thesis_report(m: str | None = Query(None)) -> dict[str, Any]:
    member_q = m or MEMBER
    try:
        return generate_thesis_guide(member=member_q)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/pipeline")
def api_pipeline() -> dict[str, Any]:
    with _pipeline_lock:
        return {
            "running":   _pipeline["running"],
            "run_id":    _pipeline["run_id"],
            "stage":     _pipeline["stage"],
            "phase_idx": _pipeline["phase_idx"],
            "phases":    PHASES,
            "config":    _pipeline["config"],
            "jobs":      _pipeline["jobs"],
            "log":       _pipeline["log"][-200:],
            "started":   _pipeline["started"],
            "finished":  _pipeline["finished"],
            "error":     _pipeline["error"],
            "cancelled": _pipeline["cancelled"],
        }


@app.get("/api/pipeline/preset")
def api_pipeline_preset() -> dict[str, Any]:
    return compute_best_defense()


@app.get("/api/pipeline/validate")
def api_pipeline_validate(
    config: str = Query(..., description="JSON-encoded pipeline config"),
) -> dict[str, Any]:
    import json
    try:
        cfg = json.loads(config)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}") from exc
    return validate_config(cfg)


@app.get("/api/compile")
def api_compile_status() -> dict[str, Any]:
    with _compile_lock:
        return {
            "running":  _compile["running"],
            "last_run": _compile["last_run"],
            "output":   _compile["output"][-100:],
            "log_file": _compile["log_file"],
        }


@app.get("/api/hpc")
def api_hpc(
    probe: bool = Query(
        False,
        description="SSH to HPC and run squeue (slow). Default: config only.",
    ),
) -> dict[str, Any]:
    info: dict[str, Any] = {
        "host":        HPC_HOST,
        "user":        HPC_USER,
        "remote_root": HPC_ROOT,
        "ssh_key":     SSH_KEY,
        "port":        PORT,
        "partition":   "HGXQ",
        "probe":       probe,
    }
    if not probe:
        return info
    rc, out, err = _ssh_run(
        f"squeue -u {HPC_USER} --noheader -o '%i|%j|%T|%M|%R'", timeout=20
    )
    info["squeue_rc"] = rc
    if rc == 0:
        jobs: list[dict[str, str]] = []
        for line in out.strip().splitlines():
            parts = line.split("|", 4)
            if len(parts) == 5:
                jobs.append({
                    "job_id": parts[0], "name": parts[1],
                    "state":  parts[2], "time": parts[3],
                    "reason": parts[4],
                })
        info["squeue_jobs"] = jobs
        info["squeue_count"] = len(jobs)
    else:
        info["squeue_error"] = err.strip() or f"ssh exit {rc}"
    return info


# ── Routes — orchestration (POST) ─────────────────────────────────────────────

@app.post("/api/pipeline")
def api_pipeline_start(body: dict[str, Any]) -> dict[str, Any]:
    """Start a pipeline run. Body: {config: {...}} or the config dict directly."""
    with _pipeline_lock:
        if _pipeline["running"]:
            raise HTTPException(
                status_code=409,
                detail={"status": "already_running", "run_id": _pipeline["run_id"]},
            )
    cfg = body.get("config") or body
    v = validate_config(cfg)
    if not v["ok"]:
        raise HTTPException(status_code=400, detail={"status": "invalid", "validation": v})
    threading.Thread(target=_do_pipeline, args=(cfg,), daemon=True).start()
    return {"status": "started", "validation": v}


@app.post("/api/pipeline/cancel")
def api_pipeline_cancel() -> dict[str, Any]:
    """Cancel the currently running pipeline and scancel its SLURM jobs."""
    with _pipeline_lock:
        if not _pipeline["running"]:
            return {"status": "not_running"}
        run_id = _pipeline["run_id"]
        _pipeline["cancelled"] = True
    try:
        _cancel_my_pipeline_jobs(run_id)
    except Exception as exc:
        _pipeline_log(f"cancel error: {exc}")
    return {"status": "cancel_requested", "run_id": run_id}


@app.post("/api/compile")
def api_compile_start() -> dict[str, Any]:
    """Trigger a local compile run (non-SLURM result compilation)."""
    with _compile_lock:
        if _compile["running"]:
            return {"status": "already_running"}
    threading.Thread(target=_do_compile, daemon=True).start()
    return {"status": "started"}


@app.exception_handler(404)
def _not_found(_request, exc):  # type: ignore[no-untyped-def]
    return JSONResponse({"error": "not found", "detail": str(exc.detail)}, status_code=404)
