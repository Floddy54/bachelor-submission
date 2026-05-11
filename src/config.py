"""
Project configuration loader.

Resolves the repository root, reads the YAML files under `configs/`, and exposes
them as plain Python dicts. All scripts should import path constants from here
instead of recomputing them with `Path(__file__).parents[N]`.

Usage:
    from src.config import PROJECT_ROOT, PATHS, ATTACK, POISONING, DETECTION

    model_path = PROJECT_ROOT / PATHS["project"]["models_task1"] / "model1"
    triggers   = ATTACK["asr"]["triggers"]
"""

from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "PyYAML is required. Install with `pip install pyyaml` "
        "or `conda install pyyaml`."
    ) from exc


# ---------------------------------------------------------------------------
# PROJECT_ROOT  —  canonical anchor for every relative path
# ---------------------------------------------------------------------------
#
# src/config.py  → src/ → bachelor-anti-bad/
#
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
CONFIGS_DIR: Path = PROJECT_ROOT / "configs"


def _load_yaml(filename: str) -> dict[str, Any]:
    """Load a YAML file from configs/. Returns empty dict if missing."""
    path = CONFIGS_DIR / filename
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# Lazy module-level dicts (loaded once on import)
PATHS: dict[str, Any]      = _load_yaml("paths.yaml")
ATTACK: dict[str, Any]     = _load_yaml("attack.yaml")
POISONING: dict[str, Any]  = _load_yaml("poisoning.yaml")
DETECTION: dict[str, Any]  = _load_yaml("detection.yaml")

# Per-developer settings (SSH host/user/remote_root). Not committed to git;
# each teammate copies `configs/local.yaml.example` → `configs/local.yaml`
# and edits it for their own HPC account. Missing file → empty dict, so code
# that consumes LOCAL must handle the "not configured yet" case gracefully.
LOCAL: dict[str, Any]      = _load_yaml("local.yaml")


# ---------------------------------------------------------------------------
# Convenience path helpers
# ---------------------------------------------------------------------------

def path(key_chain: str) -> Path:
    """
    Resolve a dotted path key from paths.yaml to an absolute Path.

    Example:
        path("data.processed_task1")         # → <root>/data/processed/task1
        path("experiments.untargeted")       # → <root>/experiments/results/untargeted
    """
    node: Any = PATHS
    for key in key_chain.split("."):
        if not isinstance(node, dict) or key not in node:
            raise KeyError(f"paths.yaml has no key '{key_chain}'")
        node = node[key]
    if not isinstance(node, str):
        raise TypeError(f"paths.yaml key '{key_chain}' is not a string")
    return PROJECT_ROOT / node


def model_path(model_name: str, task: str = "task1") -> Path:
    """Return the absolute path to a LoRA adapter directory."""
    valid = {"task1", "task2"}
    if task not in valid:
        raise ValueError(f"task must be one of {valid}")
    base = PATHS["project"]["models_task1" if task == "task1" else "classification_track"]
    if task == "task1":
        return PROJECT_ROOT / base / model_name
    return PROJECT_ROOT / base / "models" / task / model_name


def results_dir(attack: str, model_name: str) -> Path:
    """
    Return the experiments/results/{attack}/{model} directory, creating it.

    `attack` must be one of: 'asr', 'eval', 'general'.
    """
    if attack not in {"asr", "eval", "general"}:
        raise ValueError(f"unknown attack type '{attack}'")
    # 'eval' clean-accuracy output lives under experiments/results/asr/ alongside ASR
    key = "asr" if attack == "eval" else attack
    out = path(f"experiments.{key}") / model_name
    out.mkdir(parents=True, exist_ok=True)
    return out


def local(key_chain: str, default: Any = None) -> Any:
    """
    Look up a dotted key from `configs/local.yaml`.

    Example:
        local("ssh.host")         # → "YourIPAddress"
        local("ssh.user")         # → "UserName"
        local("ssh.remote_root")  # → "/cluster/home/UserName/RepoName"

    Returns `default` if the file is missing, the key is missing, or the
    value is None. Intended so callers can degrade gracefully when a
    teammate hasn't set up their `local.yaml` yet.
    """
    node: Any = LOCAL
    for key in key_chain.split("."):
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return default if node is None else node


__all__ = [
    "PROJECT_ROOT",
    "CONFIGS_DIR",
    "PATHS",
    "ATTACK",
    "POISONING",
    "DETECTION",
    "LOCAL",
    "path",
    "model_path",
    "results_dir",
    "local",
]
