"""
HTTP request handler for the dashboard server.

Endpoints:
    GET  /                     → dashboard HTML
    GET  /api/data             → all parsed logs + results as JSON (30 s cache)
    GET  /api/log?f=X[&m=Y]    → raw content of a single log blob
    GET  /api/members          → {current, all} — available member prefixes
    GET  /api/compile          → compile runner status
    POST /api/compile          → trigger compile (local)
    GET  /api/pipeline         → pipeline orchestrator status
    GET  /api/pipeline/preset  → best-known defense preset from results CSV
    GET  /api/pipeline/validate?config=JSON → dry-run validation + cost
    POST /api/pipeline         → start a pipeline run
    POST /api/pipeline/cancel  → cancel the running pipeline
"""
import json
import threading
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# Ensure config's sys.path setup runs before azure_io is imported.
from . import config  # noqa: F401
from azure_io import (  # noqa: E402
    ACCOUNT_NAME,
    BLOB_BASE_URL,
    CONTAINER_NAME,
    MEMBER,
    blob_path,
    exists as blob_exists,
    list_members,
    read_text,
)

from .compile_runner import _do_compile
from .config import SERVER_DIR
from .data_reading import get_all_data
from .stats_validation import compute_stats
from .job_explainer import explain_job, generate_report
from .thesis_report import generate_thesis_guide
from .pipeline import (
    PHASES,
    _cancel_my_pipeline_jobs,
    _do_pipeline,
    _pipeline_log,
    compute_best_defense,
    validate_config,
)
from .state import (
    _compile,
    _compile_lock,
    _pipeline,
    _pipeline_lock,
    strip_ansi,
)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass  # suppress per-request noise

    def _send_json(self, data, status: int = 200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, data: bytes, content_type: str):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        qs     = parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            html = SERVER_DIR / "index.html"
            if html.exists():
                self._send_bytes(html.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send_json({"error": "index.html not found"}, 404)

        elif path == "/api/data":
            force = qs.get("force", ["0"])[0] in ("1", "true", "yes")
            self._send_json(get_all_data(force=force))

        elif path == "/api/members":
            try:
                members = list_members()
            except Exception as exc:
                self._send_json({"error": str(exc)}, 500)
                return
            self._send_json({
                "current": MEMBER,
                "all":     members,
                "account": ACCOUNT_NAME,
                "container": CONTAINER_NAME,
                "base_url": BLOB_BASE_URL,
            })

        elif path == "/api/log":
            fname = qs.get("f", [None])[0]
            member_q = qs.get("m", [None])[0] or MEMBER
            if not fname:
                self._send_json({"error": "missing ?f= param"}, 400)
                return
            # Security: only bare .out/.err file names
            if ("/" in fname or "\\" in fname or ".." in fname
                    or not fname.endswith((".out", ".err"))):
                self._send_json({"error": "invalid filename"}, 400)
                return
            blob_name = blob_path(f"logs/{fname}", member=member_q)
            if not blob_exists(blob_name):
                self._send_json({"error": "file not found"}, 404)
                return
            try:
                content = strip_ansi(read_text(blob_name))
            except Exception as exc:
                self._send_json({"error": f"read failed: {exc}"}, 500)
                return
            self._send_json({
                "filename": fname,
                "member":   member_q,
                "content":  content,
            })

        elif path == "/api/compile":
            with _compile_lock:
                self._send_json({
                    "running":   _compile["running"],
                    "last_run":  _compile["last_run"],
                    "output":    _compile["output"][-100:],
                    "log_file":  _compile["log_file"],
                })

        elif path == "/api/pipeline":
            with _pipeline_lock:
                self._send_json({
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
                })

        elif path == "/api/stats":
            member_q = qs.get("m", [None])[0] or MEMBER
            try:
                self._send_json(compute_stats(member=member_q))
            except Exception as exc:
                self._send_json({"error": str(exc)}, 500)

        elif path == "/api/job/explain":
            fname = qs.get("f", [None])[0]
            member_q = qs.get("m", [None])[0] or MEMBER
            if not fname:
                self._send_json({"error": "missing ?f= param"}, 400)
                return
            try:
                self._send_json(explain_job(fname, member=member_q))
            except Exception as exc:
                self._send_json({"error": str(exc)}, 500)

        elif path == "/api/report":
            try:
                self._send_json(generate_report())
            except Exception as exc:
                self._send_json({"error": str(exc)}, 500)

        elif path == "/api/thesis_report":
            member_q = qs.get("m", [None])[0] or MEMBER
            try:
                self._send_json(generate_thesis_guide(member=member_q))
            except Exception as exc:
                self._send_json({"error": str(exc)}, 500)

        elif path == "/api/pipeline/preset":
            self._send_json(compute_best_defense())

        elif path == "/api/pipeline/validate":
            raw = qs.get("config", [None])[0]
            if not raw:
                self._send_json({"error": "missing ?config= param (JSON-encoded)"}, 400)
                return
            try:
                cfg = json.loads(raw)
            except json.JSONDecodeError as e:
                self._send_json({"error": f"invalid JSON: {e}"}, 400)
                return
            self._send_json(validate_config(cfg))

        else:
            self._send_json({"error": "not found"}, 404)

    def _read_json_body(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            return None
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def do_POST(self):
        if self.path == "/api/compile":
            with _compile_lock:
                if _compile["running"]:
                    self._send_json({"status": "already_running"})
                    return
            threading.Thread(target=_do_compile, daemon=True).start()
            self._send_json({"status": "started"})
        elif self.path == "/api/pipeline":
            with _pipeline_lock:
                if _pipeline["running"]:
                    self._send_json({"status": "already_running",
                                     "run_id": _pipeline["run_id"]}, 409)
                    return
            body = self._read_json_body()
            if body is None:
                self._send_json({"error": "invalid JSON body"}, 400)
                return

            config = body.get("config") or body
            v = validate_config(config)
            if not v["ok"]:
                self._send_json({"status": "invalid", "validation": v}, 400)
                return

            threading.Thread(target=_do_pipeline, args=(config,), daemon=True).start()
            self._send_json({"status": "started", "validation": v})

        elif self.path == "/api/pipeline/cancel":
            with _pipeline_lock:
                if not _pipeline["running"]:
                    self._send_json({"status": "not_running"})
                    return
                run_id = _pipeline["run_id"]
                _pipeline["cancelled"] = True
            try:
                _cancel_my_pipeline_jobs(run_id)
            except Exception as exc:
                _pipeline_log(f"cancel error: {exc}")
            self._send_json({"status": "cancel_requested", "run_id": run_id})

        else:
            self._send_json({"error": "not found"}, 404)
             