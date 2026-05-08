"""
Compile runner — Azure pull → run `src.evaluation.compile_results` → push.

Invoked from the HTTP handler (`POST /api/compile`) and from the pipeline
orchestrator's `compile` phase. Runs on the local laptop (not the HPC)
and writes an execution log to `.dashboard-scratch/`; the log is then
pushed back to Azure under `logs/` so it surfaces in the jobs table via
`parse_all_logs()`.
"""
import re
import subprocess
import sys
import time
from pathlib import Path

# Ensure config's sys.path setup runs before azure_io is imported.
from . import config  # noqa: F401
from azure_io import (  # noqa: E402
    MEMBER,
    blob_path,
    download_to_path,
    list_blobs,
    upload_file,
)

from .config import PROJECT_ROOT, SCRATCH_DIR
from .data_reading import _invalidate_data_cache
from .state import _compile, _compile_lock


# Input patterns pulled from THIS member's prefix before compile runs.
# - None in the second slot means "pull everything under this prefix".
# - A callable means "only pull blobs whose member-relative path matches".
_COMPILE_PULL_SPECS: list[tuple[str, object]] = [
    # Full experiments/results tree — recursive pull, so every defense folder
    # under this prefix lands on disk regardless of who produced it:
    #   Vetle:  asr, input_reduction, untargeted, bert, bert_mlm_defense,
    #           bert_crow_defense, adaptive_attacker, general, overnight_full,
    #           deep_trigger_scan.{csv,md}, sst2_task1_utility.csv,
    #           task<N>_zscore.{csv,md,png}.
    #   Yoel:   bert_classifier/{anomaly,auxiliary,strip}, int8,
    #           logit_confidence, model3_trigger_scan, onion_mlm, pruning,
    #           trigger_extraction, trigger_injection, wag.
    #   (Historical Yoel-only outputs from flip_rate, keyword_filter[_injection],
    #    llama_crow, tfidf_filter, and trigger_removal/_reversal still pull from
    #    Azure but the producing scripts moved to _archive/ on 2026-05-01.)
    # New defenses auto-surface here without code changes — only add to this
    # list if you need a *different* prefix on disk.
    ("experiments/results/", None),
    # SLURM stdout logs (fallback scan inside compile_results.parse_eval_log).
    ("scripts/slurm/logs/",  None),
    # Only the docs/ files compile_results consumes — never overwrite
    # checked-in markdown (e.g. docs/azure-setup.md).
    ("docs/", lambda rel: (
        rel == "docs/pruning_results.csv"
        or bool(re.match(r"^docs/gate_eval_model\d\.txt$", rel))
    )),
]

# Outputs pushed back to THIS member's prefix after compile runs.
# (local_path, blob_rel_path)
_COMPILE_PUSH_OUTPUTS: list[tuple[str, str]] = [
    ("docs/results_summary.csv",    "docs/results_summary.csv"),
    ("docs/results_summary.txt",    "docs/results_summary.txt"),
    ("docs/detection_summary.csv",  "docs/detection_summary.csv"),
]


def _pull_compile_inputs(log_line) -> int:
    """
    Download this member's compile inputs into PROJECT_ROOT. Returns the
    number of files actually downloaded. `log_line` is a callable that
    appends a line to the live compile status.
    """
    n_downloaded = 0
    for prefix, filter_fn in _COMPILE_PULL_SPECS:
        try:
            entries = list_blobs(prefix, member=MEMBER)
        except Exception as exc:
            log_line(f"  ⚠ list {prefix} failed: {exc}")
            continue
        for e in entries:
            rel = e["rel"]
            if rel.endswith("/"):
                continue  # "virtual folder" placeholder
            if filter_fn is not None and not filter_fn(rel):
                continue
            local_path = PROJECT_ROOT / rel
            try:
                download_to_path(e["name"], local_path)
                n_downloaded += 1
            except Exception as exc:
                log_line(f"  ✗ download {rel}: {exc}")
    return n_downloaded


def _push_compile_outputs(compile_log_path: Path, log_line) -> tuple[int, int]:
    """
    Upload compile outputs + the captured stdout log. Returns (n_uploaded,
    n_missing). Log file is uploaded as `logs/compile_results_<ts>.out` so
    parse_all_logs() surfaces it in the dashboard jobs table.
    """
    n_uploaded = 0
    n_missing  = 0
    outputs: list[tuple[Path, str]] = [
        (PROJECT_ROOT / local, rel) for local, rel in _COMPILE_PUSH_OUTPUTS
    ]
    outputs.append((compile_log_path, f"logs/{compile_log_path.name}"))

    for local_path, rel in outputs:
        if not local_path.exists():
            log_line(f"  ⏭ skip {rel} (not produced)")
            n_missing += 1
            continue
        try:
            upload_file(blob_path(rel), local_path)
            n_uploaded += 1
        except Exception as exc:
            log_line(f"  ✗ upload {rel}: {exc}")
    return n_uploaded, n_missing


def _do_compile():
    """Pull compile inputs from Azure → run compile_results.py → push outputs."""
    with _compile_lock:
        _compile["running"]  = True
        _compile["output"]   = [f"▶  Compile: starting (member={MEMBER})"]
        _compile["log_file"] = None

    def log_line(msg: str) -> None:
        with _compile_lock:
            _compile["output"].append(msg)

    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d%H%M%S")
    compile_log_path = SCRATCH_DIR / f"compile_results_{ts}.out"
    compile_log_path.write_text("", encoding="utf-8")  # touch up-front

    try:
        # ---- Pull ----
        log_line("▶  Pulling inputs from Azure…")
        n_pulled = _pull_compile_inputs(log_line)
        log_line(f"  ⇩ pulled {n_pulled} file(s) from {MEMBER}/")

        # ---- Run ----
        log_line("▶  Running compile_results.py…")
        cmd = [
            sys.executable, "-m", "src.evaluation.compile_results",
            "--include_pruning",
            "--include_detection",
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=120, cwd=str(PROJECT_ROOT),
            )
            run_stdout = result.stdout + (result.stderr if result.returncode != 0 else "")
        except subprocess.TimeoutExpired:
            run_stdout = "Error: compile_results.py timed out after 120 s\n"
        except Exception as e:
            run_stdout = f"Error: {e}\n"

        compile_log_path.write_text(run_stdout, encoding="utf-8")
        for line in run_stdout.splitlines():
            log_line(line)

        # ---- Push ----
        log_line("▶  Pushing outputs to Azure…")
        n_up, n_miss = _push_compile_outputs(compile_log_path, log_line)
        log_line(f"  ⇧ pushed {n_up} file(s) to {MEMBER}/ ({n_miss} missing)")
        log_line("✓ Compile done.")
    except Exception as exc:
        log_line(f"✗ Compile runner error: {exc}")
    finally:
        with _compile_lock:
            _compile["running"]  = False
            _compile["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _compile["log_file"] = compile_log_path.name
        # Invalidate the data cache so new results surface in /api/data.
        _invalidate_data_cache()
