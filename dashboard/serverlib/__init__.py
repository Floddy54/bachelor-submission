"""
serverlib — implementation modules for dashboard/server.py.

The top-level `dashboard/server.py` is a thin shim that wires these pieces
together and runs the HTTP server. Everything else (log parsing, Azure
reads, compile runner, pipeline orchestrator, HTTP handler) lives here.

Only server.py's pieces belong in this package — unrelated dashboard
helpers should stay at `dashboard/` alongside azure_io.py, index.html, etc.
"""

# Re-exports kept flat so external callers (dashboard/smoke_e2e.py loads
# server.py by file path and calls these as module-level names) can keep
# reaching the same symbols after the split.
from .log_parsing import parse_all_logs  # noqa: F401
from .data_reading import _read_csv_blob  # noqa: F401
