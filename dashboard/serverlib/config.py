"""
Path + HPC config for the dashboard server.

Importing this module also mutates sys.path so sibling modules like
`azure_io` and the project-root `src.config` resolve regardless of where
the dashboard was launched from. It's imported first by everything else
in `serverlib`, so this happens before any `from azure_io import ...`.
"""
import os
import sys
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
# This file lives at dashboard/serverlib/config.py, so parent.parent = dashboard/.
SERVER_DIR   = Path(__file__).resolve().parent.parent         # dashboard/
PROJECT_ROOT = SERVER_DIR.parent                               # bachelor-anti-bad/

# Local scratch for compile runner output. Task 3 will replace this with an
# Azure pull-run-push pattern; for now the compile runner writes here so we
# don't touch anyone else's data.
SCRATCH_DIR = PROJECT_ROOT / ".dashboard-scratch"

# ── sys.path setup ────────────────────────────────────────────────────────────
# Add both the project root (so `src.config` resolves) and SERVER_DIR (so the
# sibling `azure_io` module is importable) to sys.path regardless of where the
# dashboard was launched from.
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SERVER_DIR))

# ── HPC config (still needed for the pipeline orchestrator) ───────────────────
# HPC_HOST / HPC_USER / HPC_ROOT are read from `configs/local.yaml` so each
# teammate can point the dashboard at their own HPC account without editing
# tracked code. See configs/local.yaml.example for the expected shape.
from src.config import local as _local_cfg  # noqa: E402

_ssh_user = _local_cfg("ssh.user")
_ssh_host = _local_cfg("ssh.host")
_ssh_root = _local_cfg("ssh.remote_root")

if not (_ssh_user and _ssh_host and _ssh_root):
    raise RuntimeError(
        "configs/local.yaml is missing or incomplete. Copy "
        "configs/local.yaml.example → configs/local.yaml and fill in "
        "ssh.host, ssh.user, and ssh.remote_root before starting the "
        "dashboard."
    )

HPC_USER = _ssh_user
HPC_HOST = f"{_ssh_user}@{_ssh_host}"
HPC_ROOT = _ssh_root
PORT     = 8765

# ── SSH key auto-detection (module-level so all helpers reuse it) ─────────────
_SSH_KEY_CANDIDATES = ["id_ed25519", "id_ecdsa", "id_rsa", "id_dsa"]


def _candidate_ssh_dirs():
    yield Path.home() / ".ssh"
    # WSL: Windows home is typically mounted at /mnt/c/Users/<username>.
    # Priority: local.yaml `windows_user` → $WINDOWS_USER env var → WSL home name.
    wsl_users = Path("/mnt/c/Users")
    if wsl_users.is_dir():
        win_user = (
            _local_cfg("windows_user")
            or os.environ.get("WINDOWS_USER")
            or Path.home().name
        )
        yield wsl_users / win_user / ".ssh"

SSH_KEY = next(
    (str(d / k) for d in _candidate_ssh_dirs() for k in _SSH_KEY_CANDIDATES
     if (d / k).exists()),
    None,
)
