#!/usr/bin/env python3
"""
Anti-BAD Results Dashboard — Local Server (thin entry point)
============================================================
The actual implementation lives in `dashboard/serverlib/` — this file is
kept at `dashboard/server.py` so `python3 dashboard/server.py` and
`dashboard/start.sh` keep working. It also re-exports a few names
(`parse_all_logs`, `_read_csv_blob`) that `dashboard/smoke_e2e.py`
loads by file path.

Usage (from project root or anywhere):
    python dashboard/server.py
    python dashboard/server.py --port 8765
    bash dashboard/start.sh

Endpoints are documented in `dashboard/serverlib/http_handler.py`.
Migrated from SCP-based sync in 2026-04; see docs/azure-setup.md.
"""
from __future__ import annotations

import argparse
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

# ── sys.path setup ────────────────────────────────────────────────────────────
# When this file is launched as a script (`python dashboard/server.py`) or
# loaded by file path (`dashboard/smoke_e2e.py`), we need:
#   * dashboard/  on sys.path so `from serverlib.xxx` resolves, and
#   * project root on sys.path so `src.config` resolves inside serverlib.config.
# serverlib.config repeats this setup defensively for other entry points.
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE))

# ── Imports (after sys.path mutation) ─────────────────────────────────────────
from serverlib.config import HPC_HOST, PORT, PROJECT_ROOT  # noqa: E402
from serverlib.http_handler import Handler  # noqa: E402
# Re-exports for dashboard/smoke_e2e.py, which loads this module by file path
# and expects these names to be available at the top level.
from serverlib import _read_csv_blob, parse_all_logs  # noqa: E402,F401
from azure_io import ACCOUNT_NAME, CONTAINER_NAME, MEMBER  # noqa: E402


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Anti-BAD Dashboard Server")
    ap.add_argument("--port", type=int, default=PORT, help=f"Port (default {PORT})")
    args = ap.parse_args()

    print(f"┌─ Anti-BAD Dashboard ────────────────────────────────")
    print(f"│  URL:       http://localhost:{args.port}")
    print(f"│  Root:      {PROJECT_ROOT}")
    print(f"│  Storage:   Azure Blob Storage — {CONTAINER_NAME}@{ACCOUNT_NAME}")
    print(f"│  Member:    {MEMBER}")
    print(f"│  HPC:       {HPC_HOST}  (pipeline orchestrator only)")
    print(f"└─ Press Ctrl+C to stop ──────────────────────────────")

    # ThreadingHTTPServer — single-threaded HTTPServer can deadlock when a
    # slow Azure-backed /api/data blocks the root HTML request queued behind it.
    server = ThreadingHTTPServer(("localhost", args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
