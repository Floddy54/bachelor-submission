"""
sys.path bootstrap for the merged dashboard.

Adds PROJECT_ROOT (bachelor/) and dashboard/ itself to sys.path so that
`azure_io`, `serverlib`, and `src.config` all resolve from any entry point
(uvicorn, streamlit, smoke tests).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent   # dashboard/
PROJECT_ROOT = HERE.parent               # bachelor/

for p in (PROJECT_ROOT, HERE):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

if not (HERE / "azure_io.py").exists():
    raise RuntimeError(
        f"azure_io.py not found at {HERE}. "
        "dashboard/_bootstrap.py must live next to azure_io.py."
    )

__all__ = ["PROJECT_ROOT", "HERE"]
