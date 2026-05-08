"""
Local-disk backend for dashboard I/O — drop-in replacement for `azure_io`
when the team chooses to run without Azure (laptop-only or HPC + rsync).

Why this exists
---------------
The 2026-05-07 supervisor check-in asked for storage to be a *choice*:
local + HPC must work end-to-end, with Azure as an opt-in. The dashboard
historically hard-failed if `.secrets/azure_connection_string` was
missing. This module exposes the same public API as `azure_io` but
serves it from local files under `PROJECT_ROOT/`, so the dashboard can
read SLURM logs and result CSVs that landed on the filesystem (either
because the job ran on the laptop, or because the user rsync'd them
back from HPC).

Activation
----------
Set `STORAGE_BACKEND=local` in your shell, or `storage.backend: local`
in `configs/local.yaml`. `azure_io` then re-exports this module's names
so every `from azure_io import …` site keeps working unchanged.

Path mapping
------------
Blob names look like `<member>/<area>/<rest>`. In local mode the member
prefix is informational only — there is one filesystem — and `<area>`
maps to the same local directories that `_azure_upload.sh` uploads
*from*:

    logs/                  ← scripts/slurm/logs/
    results/               ← experiments/results/
    submission/            ← experiments/submission/
    data/processed/task1/  ← data/processed/task1/
    docs/                  ← docs/

This is exactly the inverse of the upload mapping, so a SLURM job that
ran with `AZURE_UPLOAD_DISABLED=1` produces files the dashboard can
read without any extra step.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from src.config import PROJECT_ROOT, local as _local_cfg


# ---------------------------------------------------------------------------
# Constants — kept identical to azure_io for API parity
# ---------------------------------------------------------------------------

CONTAINER_NAME: str = "anti-bad"           # informational; unused on disk
ACCOUNT_NAME: str   = "local"
BLOB_BASE_URL: str  = f"file://{PROJECT_ROOT}"


# ---------------------------------------------------------------------------
# Member resolution — same priority order as azure_io
# ---------------------------------------------------------------------------

def _resolve_member() -> str:
    explicit = os.environ.get("MEMBER", "").strip()
    if explicit:
        return explicit
    from_local = (_local_cfg("hpc.member") or "").strip() if _local_cfg("hpc.member") else ""
    if from_local:
        return from_local
    fallback = os.environ.get("USER") or os.environ.get("USERNAME") or "local"
    print(
        f"[local_io] MEMBER env var not set and hpc.member missing from "
        f"configs/local.yaml — defaulting to '{fallback}'.",
        file=sys.stderr,
    )
    return fallback


MEMBER: str = _resolve_member()


# ---------------------------------------------------------------------------
# Blob ↔ local-path mapping
# ---------------------------------------------------------------------------

# First path segment of a blob's "rel" portion → local directory under
# PROJECT_ROOT. Mirrors the upload table in scripts/slurm/_azure_upload.sh.
_AREA_TO_LOCAL: dict[str, Path] = {
    "logs":       PROJECT_ROOT / "scripts" / "slurm" / "logs",
    "results":    PROJECT_ROOT / "experiments" / "results",
    "submission": PROJECT_ROOT / "experiments" / "submission",
    "data":       PROJECT_ROOT / "data",          # e.g. data/processed/task1/...
    "docs":       PROJECT_ROOT / "docs",
}


def _strip_leading_slash(name: str) -> str:
    return name.lstrip("/")


def _split_member(blob_name: str) -> tuple[str, str]:
    """Split `member/rel/path` → (member, "rel/path")."""
    blob_name = _strip_leading_slash(blob_name)
    parts = blob_name.split("/", 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _rel_to_local(rel: str) -> Path | None:
    """
    Map the member-stripped `rel` (e.g. `results/asr/model1/foo.txt`) to a
    local Path under PROJECT_ROOT. Returns None for unrecognised areas so
    callers can no-op gracefully (matches Azure's "blob doesn't exist").
    """
    rel = _strip_leading_slash(rel)
    if not rel:
        return None
    head, _, tail = rel.partition("/")
    base = _AREA_TO_LOCAL.get(head)
    if base is None:
        return None
    if head == "data":
        # data/processed/task1/... — keep the full rel under PROJECT_ROOT/data/
        return PROJECT_ROOT / rel
    return base / tail if tail else base


def _blob_name_to_local(blob_name: str) -> Path | None:
    _, rel = _split_member(blob_name)
    return _rel_to_local(rel)


def blob_path(relative: str, member: str | None = None) -> str:
    """Build a member-prefixed blob name. Identical contract to azure_io."""
    m = member or MEMBER
    return f"{m}/{_strip_leading_slash(relative)}"


def blob_url(blob_name: str) -> str:
    """Return a `file://` URL for the local equivalent of `blob_name`."""
    p = _blob_name_to_local(blob_name)
    return p.as_uri() if p is not None else f"{BLOB_BASE_URL}/{_strip_leading_slash(blob_name)}"


# ---------------------------------------------------------------------------
# Member discovery
# ---------------------------------------------------------------------------

_HIDDEN_PREFIXES: frozenset[str] = frozenset({"smoke"})


def list_members() -> list[str]:
    """
    Local mode has one filesystem and therefore one logical "member". We
    return [MEMBER] so the dashboard's member-picker still has something
    to render, and the caller's all-members loop still terminates.
    """
    return [MEMBER]


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

def _walk_files(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    return [p for p in root.rglob("*") if p.is_file()]


def list_blobs(
    prefix: str,
    member: str | None = None,
    include_all_members: bool = False,
) -> list[dict[str, Any]]:
    """
    List "blobs" matching `prefix` from local disk.

    `prefix` is relative to the member root (same contract as azure_io).
    `include_all_members` is a no-op here — local mode has one member —
    but accepted for API parity.
    """
    prefix = _strip_leading_slash(prefix)
    base = _rel_to_local(prefix) if prefix else None
    out: list[dict[str, Any]] = []

    # If prefix points at a specific subtree, walk that. Otherwise walk
    # every recognised area so empty-prefix calls still return something.
    if base is not None:
        roots = [(prefix, base)]
    else:
        roots = []
        for head, area_root in _AREA_TO_LOCAL.items():
            if head == "data":
                # The blob layout only uses `data/processed/task1/`, not the
                # whole `data/` tree — so anchor on that.
                roots.append(("data/processed/task1", area_root / "processed" / "task1"))
            else:
                roots.append((head, area_root))

    m = member or MEMBER
    for rel_prefix, root in roots:
        for f in _walk_files(root):
            rel_to_root = f.relative_to(root).as_posix()
            rel = f"{rel_prefix}/{rel_to_root}" if rel_to_root else rel_prefix
            try:
                stat = f.stat()
                size = stat.st_size
                last_mod = _isoformat_mtime(stat.st_mtime)
            except OSError:
                size = 0
                last_mod = None
            out.append({
                "name": f"{m}/{rel}",
                "member": m,
                "rel": rel,
                "size": size,
                "last_modified": last_mod,
            })
    return out


def _isoformat_mtime(epoch: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Read / write
# ---------------------------------------------------------------------------

def exists(blob_name: str) -> bool:
    p = _blob_name_to_local(blob_name)
    return p is not None and p.exists() and p.is_file()


def read_bytes(blob_name: str) -> bytes:
    p = _blob_name_to_local(blob_name)
    if p is None or not p.exists():
        raise FileNotFoundError(f"local_io: no file for blob {blob_name!r}")
    return p.read_bytes()


def read_text(blob_name: str, encoding: str = "utf-8", errors: str = "replace") -> str:
    return read_bytes(blob_name).decode(encoding, errors=errors)


def upload_bytes(blob_name: str, data: bytes, overwrite: bool = True) -> None:
    p = _blob_name_to_local(blob_name)
    if p is None:
        raise ValueError(f"local_io: cannot write blob {blob_name!r} — unknown area")
    if p.exists() and not overwrite:
        raise FileExistsError(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def upload_text(blob_name: str, text: str, overwrite: bool = True) -> None:
    upload_bytes(blob_name, text.encode("utf-8"), overwrite=overwrite)


def upload_file(blob_name: str, local_path: Path, overwrite: bool = True) -> None:
    upload_bytes(blob_name, Path(local_path).read_bytes(), overwrite=overwrite)


def download_to_path(blob_name: str, local_path: Path) -> None:
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(read_bytes(blob_name))


# ---------------------------------------------------------------------------
# Service / container client stubs — present for API parity with azure_io.
# Anything that asks for a "client" in local mode either doesn't need one
# or is a code path that should be gated on `STORAGE_BACKEND` upstream.
# ---------------------------------------------------------------------------

def get_service_client() -> None:  # pragma: no cover
    raise RuntimeError(
        "STORAGE_BACKEND=local — no Azure SDK client is available. "
        "If you need a SDK client, switch to STORAGE_BACKEND=azure."
    )


def get_container_client() -> None:  # pragma: no cover
    raise RuntimeError(
        "STORAGE_BACKEND=local — no Azure SDK container client is available. "
        "If you need a SDK client, switch to STORAGE_BACKEND=azure."
    )


# ---------------------------------------------------------------------------
# CLI: python dashboard/local_io.py  → quick diagnostics
# ---------------------------------------------------------------------------

def _diagnostics() -> int:
    print(f"backend   : local")
    print(f"member    : {MEMBER}")
    print(f"root      : {PROJECT_ROOT}")
    for head, area in _AREA_TO_LOCAL.items():
        marker = "ok" if area.exists() else "missing"
        print(f"  {head:11s} → {area}  [{marker}]")
    blobs = list_blobs("results/")
    print(f"results/* : {len(blobs)} files")
    return 0


if __name__ == "__main__":
    _PR = Path(__file__).resolve().parents[1]
    if str(_PR) not in sys.path:
        sys.path.insert(0, str(_PR))
    raise SystemExit(_diagnostics())


__all__ = [
    "ACCOUNT_NAME",
    "CONTAINER_NAME",
    "BLOB_BASE_URL",
    "MEMBER",
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
