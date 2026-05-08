"""
SSH helpers used by the pipeline orchestrator (and anything else that
needs to talk to the HPC). Thin wrapper over `subprocess` + ssh with
auto-detected key and non-interactive defaults.
"""
import subprocess

from .config import HPC_HOST, SSH_KEY


def _ssh_cmd_prefix() -> list[str]:
    """Base ssh command list with shared options and auto-detected key."""
    cmd = ["ssh"]
    if SSH_KEY:
        cmd += ["-i", SSH_KEY]
    cmd += [
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=15",
    ]
    return cmd


def _ssh_run(remote_cmd: str, timeout: int = 60) -> tuple[int, str, str]:
    """Run a single shell command on the HPC; return (rc, stdout, stderr)."""
    full = _ssh_cmd_prefix() + [HPC_HOST, remote_cmd]
    try:
        res = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"ssh timeout after {timeout}s"
    except Exception as e:
        return 1, "", str(e)


def shell_quote(s: str) -> str:
    """Minimal POSIX single-quote escaper for sbatch arg passthrough."""
    if not s or any(c in s for c in " \t'\"\\$`"):
        return "'" + s.replace("'", "'\\''") + "'"
    return s
