"""
Shared mutable state for the compile runner and pipeline orchestrator.

The HTTP handler and background worker threads both touch these dicts,
so every mutation must be guarded by the matching lock.
"""
import re
import threading

# ── Compile state ─────────────────────────────────────────────────────────────
_compile = {"running": False, "last_run": None, "output": [], "log_file": None}
_compile_lock = threading.Lock()

# ── Pipeline state (orchestrator) ─────────────────────────────────────────────
_pipeline = {
    "running":   False,
    "run_id":    None,
    "stage":     None,       # current phase name
    "phase_idx": 0,          # 0..len(PHASES)-1
    "config":    None,       # the selection config submitted
    "jobs":      [],         # list of {phase, model, variant, job_id, job_name, status, started, finished, err}
    "log":       [],         # human-readable progress log
    "started":   None,
    "finished":  None,
    "error":     None,
    "cancelled": False,
}
_pipeline_lock = threading.Lock()

# ── ANSI code stripper ────────────────────────────────────────────────────────
_ANSI = re.compile(r"\x1b(\[[0-9;]*[A-Za-z]|\][^\x07]*\x07|[()][AB012])")


def strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)
