"""
Azure Blob Storage I/O helpers for the bachelor-anti-bad project.

All dashboard reads and compile-step writes go through this module so the rest
of the codebase doesn't need to know about the Azure SDK. The storage layout
inside the `anti-bad` container is partitioned by member (one top-level prefix
per thesis group member) so nobody's `.out` / `.err` logs collide:

    anti-bad/
      ├── <member>/                     ← top-level prefix per teammate
      │     ├── logs/                   ← scripts/slurm/logs/
      │     ├── results/                ← experiments/results/
      │     ├── submission/             ← experiments/submission/
      │     └── data/processed/task1/   ← data/processed/task1/
      ├── <other_member>/  ...          (same shape)
      └── ...

Auth: the storage account connection string is loaded from
`.secrets/azure_connection_string` (or the `AZURE_STORAGE_CONNECTION_STRING`
env var if set). The current machine's member identifier comes from — in
order — the `MEMBER` env var, `hpc.member` in `configs/local.yaml`, or the
OS username (with a warning, so misconfigs are loud).

This module lives alongside `dashboard/server.py` so everything the dashboard
needs from Azure is in one place. Importers typically run from the project
root (so that `src.config` and the rest of the tree resolve), and pick up
this module as a sibling of `server.py`:

    # from dashboard/server.py (SERVER_DIR is on sys.path)
    from azure_io import MEMBER, list_blobs, read_text, upload_text

    # List this member's logs
    for entry in list_blobs("logs/"):
        print(entry["name"], entry["size"])

    # List every member's results (dashboard path)
    for entry in list_blobs("results/", include_all_members=True):
        print(entry["member"], entry["rel"])

    # Upload (rare from the dashboard — usually HPC does this via azcopy)
    upload_text("submission/task1.csv", "header,value\\n...")

CLI diagnostics (run from project root):

    python dashboard/azure_io.py
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any

from src.config import PROJECT_ROOT, local as _local_cfg


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------
#
# `STORAGE_BACKEND=azure|local` chooses where the dashboard reads from. The
# default is `azure` to preserve historical behavior. Setting it to `local`
# (via env var, or `storage.backend: local` in configs/local.yaml) re-exports
# `dashboard/local_io.py`'s implementations from this module so every
# `from azure_io import …` site keeps working — but reads + writes hit the
# local filesystem under PROJECT_ROOT instead of Azure Blob Storage.
#
# This is the dashboard side of the 2026-05-07 supervisor ask: storage must
# be a choice. The HPC side is the existing `AZURE_UPLOAD_DISABLED=1` switch
# in `scripts/slurm/_azure_upload.sh`.

def _resolve_storage_backend() -> str:
    explicit = os.environ.get("STORAGE_BACKEND", "").strip().lower()
    if explicit:
        return explicit
    cfg_val = _local_cfg("storage.backend")
    if cfg_val:
        return str(cfg_val).strip().lower()
    return "azure"


STORAGE_BACKEND: str = _resolve_storage_backend()

if STORAGE_BACKEND not in {"azure", "local"}:
    print(
        f"[azure_io] Unknown STORAGE_BACKEND={STORAGE_BACKEND!r}; "
        f"falling back to 'azure'. Valid values: 'azure', 'local'.",
        file=sys.stderr,
    )
    STORAGE_BACKEND = "azure"


# Azure SDK is only required on the azure path. When STORAGE_BACKEND=local,
# the dashboard can run on machines that have never installed
# azure-storage-blob — that's the whole point of the local backend.
if STORAGE_BACKEND == "azure":
    try:
        from azure.storage.blob import BlobServiceClient, ContainerClient
        from azure.core.exceptions import ResourceNotFoundError
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "azure-storage-blob is required for STORAGE_BACKEND=azure. "
            "Install with `conda env update -f environment.yml --prune` or "
            "`pip install azure-storage-blob`. To run the dashboard without "
            "Azure, set STORAGE_BACKEND=local (see README → Storage modes)."
        ) from exc


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONTAINER_NAME: str = "anti-bad"
ACCOUNT_NAME: str   = "antibadahvy"
BLOB_BASE_URL: str  = f"https://{ACCOUNT_NAME}.blob.core.windows.net/{CONTAINER_NAME}"

SECRETS_FILE: Path = PROJECT_ROOT / ".secrets" / "azure_connection_string"


# ---------------------------------------------------------------------------
# Member identification
# ---------------------------------------------------------------------------

def _resolve_member() -> str:
    """
    Return the member identifier for this machine.

    Priority:
      1. $MEMBER env var   — used on HPC (set in ~/.bashrc or in the SLURM job)
      2. hpc.member in `configs/local.yaml`  — used on the laptop so you don't
         have to `export MEMBER=…` in every shell
      3. $USER / $USERNAME  — OS username, emits a warning so silent
         misconfigurations don't land everyone's uploads under the wrong prefix

    Returns 'default' only if all three fail.
    """
    explicit = os.environ.get("MEMBER", "").strip()
    if explicit:
        return explicit
    from_local = (_local_cfg("hpc.member") or "").strip() if _local_cfg("hpc.member") else ""
    if from_local:
        return from_local
    fallback = os.environ.get("USER") or os.environ.get("USERNAME") or "default"
    print(
        f"[azure_io] MEMBER env var not set and hpc.member missing from "
        f"configs/local.yaml — defaulting to '{fallback}'. Either "
        f"`export MEMBER=<yourname>` on HPC or set `hpc.member:` in "
        f"configs/local.yaml so uploads land in the right prefix.",
        file=sys.stderr,
    )
    return fallback


MEMBER: str = _resolve_member()


# ---------------------------------------------------------------------------
# Connection (lazy-init, thread-safe singletons)
# ---------------------------------------------------------------------------

# RLock (not Lock) because get_container_client() holds the lock and then
# calls get_service_client(), which takes the same lock. A plain Lock would
# deadlock the thread on a cold cache (first /api/* request after startup).
_lock = threading.RLock()
_service_client: BlobServiceClient | None = None
_container_client: ContainerClient | None = None


def _load_connection_string() -> str:
    """Read the connection string from env or the secrets file."""
    env = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if env:
        return env.strip()
    if SECRETS_FILE.exists():
        return SECRETS_FILE.read_text(encoding="utf-8").strip()
    raise RuntimeError(
        "No Azure connection string found. Set the "
        "AZURE_STORAGE_CONNECTION_STRING env var, or create "
        f"{SECRETS_FILE.relative_to(PROJECT_ROOT)} with the storage account "
        "connection string. See docs/azure-setup.md for details."
    )


def get_service_client() -> BlobServiceClient:
    """Return a cached BlobServiceClient.

    A bounded read_timeout prevents the whole dashboard from wedging if a
    single SDK call stalls — any handler that hits a hiccup will raise a
    timeout instead of sitting in retry/backoff indefinitely.
    """
    global _service_client
    if _service_client is None:
        with _lock:
            if _service_client is None:
                _service_client = BlobServiceClient.from_connection_string(
                    _load_connection_string(),
                    connection_timeout=30,
                    read_timeout=60,
                )
    return _service_client


def get_container_client() -> ContainerClient:
    """Return a cached ContainerClient for the `anti-bad` container."""
    global _container_client
    if _container_client is None:
        with _lock:
            if _container_client is None:
                _container_client = get_service_client().get_container_client(
                    CONTAINER_NAME
                )
    return _container_client


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _strip_leading_slash(name: str) -> str:
    """Normalise '/logs/foo' → 'logs/foo' (blob names never start with '/')."""
    return name.lstrip("/")


def blob_path(relative: str, member: str | None = None) -> str:
    """
    Build a member-prefixed blob name.

    >>> blob_path("logs/textattack.out")       # MEMBER=<yourname>
    '<yourname>/logs/textattack.out'
    >>> blob_path("results/", member="alice")
    'alice/results/'
    """
    m = member or MEMBER
    return f"{m}/{_strip_leading_slash(relative)}"


def blob_url(blob_name: str) -> str:
    """Return a full https:// URL for a blob name (useful for azcopy)."""
    return f"{BLOB_BASE_URL}/{_strip_leading_slash(blob_name)}"


# ---------------------------------------------------------------------------
# Member discovery
# ---------------------------------------------------------------------------

# Top-level prefixes we don't want to surface as "members" in the UI.
_HIDDEN_PREFIXES: frozenset[str] = frozenset({"smoke"})


def list_members() -> list[str]:
    """
    Auto-discover distinct member prefixes in the container.

    Returns a sorted list of member names (top-level "virtual folders") that
    have at least one blob. If the current MEMBER hasn't uploaded anything
    yet it's appended anyway so the UI still shows it.
    """
    c = get_container_client()
    members: set[str] = set()
    # Hard-bound the call so a wedged TLS / retry loop can't hang the
    # whole dashboard. Matches the timeout used by the CLI diagnostic.
    for item in c.walk_blobs(delimiter="/", timeout=15):
        name = getattr(item, "name", str(item))
        if name.endswith("/"):
            members.add(name.rstrip("/"))
    members.add(MEMBER)
    members -= _HIDDEN_PREFIXES
    return sorted(members)


# ---------------------------------------------------------------------------
# Blob listing
# ---------------------------------------------------------------------------

def list_blobs(
    prefix: str,
    member: str | None = None,
    include_all_members: bool = False,
) -> list[dict[str, Any]]:
    """
    List blobs matching `prefix`.

    `prefix` is relative to the member root, e.g. "logs/" or "results/asr/".

    Modes:
      - `member=None`, `include_all_members=False` (default): restrict to the
        current MEMBER's prefix.
      - `member="alice"`: restrict to alice's prefix.
      - `include_all_members=True`: scan every member's prefix (ignores
        `member`).

    Each returned dict has: name (full blob name), member, rel (name relative
    to the member root), size, last_modified (ISO8601 or None).
    """
    c = get_container_client()
    prefix = _strip_leading_slash(prefix)

    if include_all_members:
        # Scan the whole container; filter by rel-prefix below.
        iterators = [c.list_blobs(name_starts_with="")]
    else:
        iterators = [c.list_blobs(name_starts_with=blob_path(prefix, member=member))]

    out: list[dict[str, Any]] = []
    for it in iterators:
        for b in it:
            parts = b.name.split("/", 1)
            if len(parts) < 2:
                continue  # skip blobs that don't follow the member/... layout
            owner, rel = parts[0], parts[1]
            if owner in _HIDDEN_PREFIXES:
                continue
            if include_all_members and prefix and not rel.startswith(prefix):
                continue
            out.append({
                "name": b.name,
                "member": owner,
                "rel": rel,
                "size": b.size,
                "last_modified": b.last_modified.isoformat() if b.last_modified else None,
            })
    return out


# ---------------------------------------------------------------------------
# Read / write
# ---------------------------------------------------------------------------

def exists(blob_name: str) -> bool:
    """Return True if the blob exists."""
    try:
        get_container_client().get_blob_client(blob_name).get_blob_properties()
        return True
    except ResourceNotFoundError:
        return False


def read_bytes(blob_name: str) -> bytes:
    """Download a blob by full (already member-prefixed) name."""
    return get_container_client().get_blob_client(blob_name).download_blob().readall()


def read_text(blob_name: str, encoding: str = "utf-8", errors: str = "replace") -> str:
    """Download a blob and decode as text."""
    return read_bytes(blob_name).decode(encoding, errors=errors)


def upload_bytes(blob_name: str, data: bytes, overwrite: bool = True) -> None:
    """Upload bytes to a blob."""
    get_container_client().get_blob_client(blob_name).upload_blob(
        data, overwrite=overwrite
    )


def upload_text(blob_name: str, text: str, overwrite: bool = True) -> None:
    """Upload text to a blob as UTF-8."""
    upload_bytes(blob_name, text.encode("utf-8"), overwrite=overwrite)


def upload_file(blob_name: str, local_path: Path, overwrite: bool = True) -> None:
    """Upload a local file to a blob, streaming."""
    with open(local_path, "rb") as f:
        get_container_client().get_blob_client(blob_name).upload_blob(
            f, overwrite=overwrite
        )


def download_to_path(blob_name: str, local_path: Path) -> None:
    """Download a blob into a local file path, creating parent dirs as needed."""
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    stream = get_container_client().get_blob_client(blob_name).download_blob()
    with open(local_path, "wb") as f:
        for chunk in stream.chunks():
            f.write(chunk)


# ---------------------------------------------------------------------------
# CLI: python dashboard/azure_io.py  → prints diagnostics
# ---------------------------------------------------------------------------

def _diagnostics() -> int:
    try:
        members = list_members()
    except Exception as exc:  # pragma: no cover
        backend_label = "Azure" if STORAGE_BACKEND == "azure" else "local backend"
        print(f"ERROR talking to {backend_label}: {exc}", file=sys.stderr)
        return 1
    print(f"backend   : {STORAGE_BACKEND}")
    print(f"account   : {ACCOUNT_NAME}")
    print(f"container : {CONTAINER_NAME}")
    print(f"member    : {MEMBER}")
    print(f"members   : {', '.join(members) if members else '(none)'}")
    print(f"base URL  : {BLOB_BASE_URL}")
    # Show blob counts per member
    for m in members:
        blobs = list_blobs("", member=m)
        print(f"  {m}: {len(blobs)} blobs")
    return 0


# ---------------------------------------------------------------------------
# Local-backend override
# ---------------------------------------------------------------------------
# When STORAGE_BACKEND=local, replace this module's public names with the
# local-disk implementations from `local_io`. The override sits before
# `if __name__ == "__main__"` so the diagnostic CLI runs through it too,
# but after every Azure function is defined so the azure path stays
# byte-identical when STORAGE_BACKEND=azure (the override is a no-op).
# Consumers that did `from azure_io import list_blobs` transparently get
# the local implementation when the backend flips.
if STORAGE_BACKEND == "local":
    # `python dashboard/azure_io.py` runs the file directly, so PROJECT_ROOT
    # may not be on sys.path yet — but `local_io` lives next to this module,
    # not on PROJECT_ROOT, so a sibling import works either way.
    _SERVER_DIR = Path(__file__).resolve().parent
    if str(_SERVER_DIR) not in sys.path:
        sys.path.insert(0, str(_SERVER_DIR))
    from local_io import (  # noqa: E402,F401
        ACCOUNT_NAME,
        BLOB_BASE_URL,
        CONTAINER_NAME,
        MEMBER,
        blob_path,
        blob_url,
        download_to_path,
        exists,
        get_container_client,
        get_service_client,
        list_blobs,
        list_members,
        read_bytes,
        read_text,
        upload_bytes,
        upload_file,
        upload_text,
    )


if __name__ == "__main__":
    # Allow running this file directly from project root. `src.config` needs
    # PROJECT_ROOT on sys.path, which it normally gets via server.py — when
    # run as a script we add it ourselves.
    _PR = Path(__file__).resolve().parents[1]
    if str(_PR) not in sys.path:
        sys.path.insert(0, str(_PR))
    raise SystemExit(_diagnostics())


__all__ = [
    "ACCOUNT_NAME",
    "CONTAINER_NAME",
    "BLOB_BASE_URL",
    "MEMBER",
    "STORAGE_BACKEND",
    "blob_path",
    "blob_url",
    "get_container_client",
    "get_service_client",
    "list_members",
    "list_blobs",
    "exists",
    "read_bytes",
    "read_text",
    "upload_bytes",
    "upload_text",
    "upload_file",
    "download_to_path",
]
