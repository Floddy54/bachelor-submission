#!/bin/bash
# =============================================================================
# Azure Blob Storage upload helper for SLURM jobs
# =============================================================================
#
# Shared helper that pushes this job's outputs to Azure Blob Storage via
# azcopy. Sourced from every .slurm file in this directory after
# PROJECT_ROOT is defined but before the Python step runs. On Kristiania HPC
# the batch script runs from /var/spool/slurmd/jobNNNN/, NOT from the submit
# cwd, so we anchor PROJECT_ROOT on $SLURM_SUBMIT_DIR (set by sbatch) with a
# dirname-based fallback for direct invocation:
#
#     PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)}"
#     cd "$PROJECT_ROOT"
#     source "$PROJECT_ROOT/scripts/slurm/_azure_upload.sh"
#
# Sourcing this file registers an EXIT trap, so outputs land in Azure even
# when the Python step fails — we want the partial .out / .err logs so the
# dashboard can surface the failure. Successful jobs get their results
# uploaded too. No-op (with a warning) if azcopy or the SAS token is missing.
#
# Blob layout (container = `anti-bad`, prefix = `${MEMBER}/`):
#   logs/                 ← scripts/slurm/logs/
#   results/              ← experiments/results/
#   submission/           ← experiments/submission/
#   data/processed/task1/ ← data/processed/task1/
#   docs/                 ← compile_results outputs (optional)
#
# Environment:
#   MEMBER                  (required) your group-member identifier
#   AZURE_UPLOAD_DISABLED=1 (optional) skip the upload entirely — use when
#                           iterating locally on SLURM-wrapped code so
#                           devel runs don't clobber team data.
#
# Required on-disk files:
#   $PROJECT_ROOT/.secrets/azure_sas_token   (SAS with r/w/l/create, no delete)
# =============================================================================

# Don't `set -e` here — sourcing this file must not terminate the caller on a
# trivial lookup failure. The trap is best-effort on purpose: upload errors
# should never mask the exit code of the actual job.

if [[ -z "${PROJECT_ROOT:-}" ]]; then
    echo "[azure-upload] PROJECT_ROOT not set; refusing to register upload trap." >&2
    return 0 2>/dev/null || exit 0
fi

if [[ "${AZURE_UPLOAD_DISABLED:-0}" == "1" ]]; then
    echo "[azure-upload] AZURE_UPLOAD_DISABLED=1 — skipping upload registration."
    return 0 2>/dev/null || exit 0
fi

# Config (mirrors dashboard/azure_io.py — keep in sync)
_AZUP_ACCOUNT="antibadahvy"
_AZUP_CONTAINER="anti-bad"
_AZUP_SAS_FILE="$PROJECT_ROOT/.secrets/azure_sas_token"

# MEMBER is required. Fall back to $USER with a loud warning so a misconfig
# doesn't silently dump somebody else's name-collision into the shared bucket.
if [[ -z "${MEMBER:-}" ]]; then
    echo "[azure-upload] WARNING: MEMBER env var not set. Falling back to USER='${USER:-default}'."
    echo "[azure-upload] Add \`export MEMBER=<yourname>\` to ~/.bashrc on HPC."
    MEMBER="${USER:-default}"
fi

# ---------------------------------------------------------------------------
# Upload function (called by the EXIT trap)
# ---------------------------------------------------------------------------

_azure_upload_outputs() {
    local last_rc=$?  # Preserve the Python step's exit code for the log line.

    if [[ ! -f "$_AZUP_SAS_FILE" ]]; then
        echo "[azure-upload] SAS token file $_AZUP_SAS_FILE missing — skipping upload."
        return 0
    fi
    if ! command -v azcopy >/dev/null 2>&1; then
        echo "[azure-upload] azcopy not on PATH — skipping upload. Install it on HPC per docs/azure-setup.md."
        return 0
    fi

    # Strip whitespace and a leading '?' if the user pasted one with the SAS.
    local sas
    sas="$(tr -d '\r\n\t ' < "$_AZUP_SAS_FILE")"
    sas="${sas#\?}"
    if [[ -z "$sas" ]]; then
        echo "[azure-upload] SAS token file is empty — skipping upload."
        return 0
    fi

    local base="https://${_AZUP_ACCOUNT}.blob.core.windows.net/${_AZUP_CONTAINER}/${MEMBER}"

    # Flush stdout so the log file is as complete as possible before we
    # sync it up. (SLURM still has an open handle so the very last lines
    # after this trap may not land on Azure — that's fine.)
    sync 2>/dev/null || true

    echo ""
    echo "============================================"
    echo "  Azure upload (member=${MEMBER}, job=${SLURM_JOB_ID:-local}, rc=${last_rc})"
    echo "============================================"

    # --- Per-path helpers ----------------------------------------------------
    # Directories use `azcopy sync` (cheap/idempotent). Files use `copy
    # --overwrite=true`. Either command's failure is logged but never fatal:
    # losing an upload shouldn't poison the job's exit status for the pipeline
    # orchestrator.
    _azup_dir() {
        local src="$1" dest_rel="$2"
        if [[ ! -d "$src" ]]; then return 0; fi
        # Skip empty directories — azcopy sync errors on them.
        if [[ -z "$(ls -A "$src" 2>/dev/null)" ]]; then
            echo "[azure-upload] skip $dest_rel (empty)"
            return 0
        fi
        local dest="${base}/${dest_rel}?${sas}"
        echo "[azure-upload] sync ${src#$PROJECT_ROOT/}  →  ${MEMBER}/${dest_rel}"
        azcopy sync "$src" "$dest" \
            --recursive=true \
            --delete-destination=false \
            --output-level=essential \
            2>&1 \
            | grep -Ev "^$|INFO: Scanning|INFO: Any empty folders" \
            || true
    }

    _azup_file() {
        local src="$1" dest_rel="$2"
        if [[ ! -f "$src" ]]; then return 0; fi
        local dest="${base}/${dest_rel}?${sas}"
        echo "[azure-upload] copy ${src#$PROJECT_ROOT/}  →  ${MEMBER}/${dest_rel}"
        azcopy copy "$src" "$dest" \
            --overwrite=true \
            --output-level=essential \
            2>&1 \
            | grep -Ev "^$|INFO: Scanning" \
            || true
    }

    # --- What to upload ------------------------------------------------------
    # Logs first so partial output of a failed job is preserved.
    _azup_dir "$PROJECT_ROOT/scripts/slurm/logs"        "logs"
    _azup_dir "$PROJECT_ROOT/experiments/results"       "results"
    _azup_dir "$PROJECT_ROOT/experiments/submission"    "submission"
    _azup_dir "$PROJECT_ROOT/data/processed/task1"      "data/processed/task1"

    # Compile-time outputs — some scripts don't produce these; _azup_file
    # no-ops on missing files so that's fine.
    local f
    for f in results_summary.csv results_summary.txt detection_summary.csv pruning_results.csv; do
        _azup_file "$PROJECT_ROOT/docs/$f" "docs/$f"
    done
    # Detection gate reports (one per model, produced by detection runs)
    shopt -s nullglob
    for f in "$PROJECT_ROOT/docs/"gate_eval_model*.txt; do
        _azup_file "$f" "docs/$(basename "$f")"
    done
    shopt -u nullglob

    echo "[azure-upload] done."
    echo "============================================"
}

# Register the EXIT trap. We capture $? first, run the upload, then exit
# with the original code — otherwise the trap's last command (an `echo`)
# would clobber a failed job's non-zero exit and SLURM would report
# COMPLETED instead of FAILED. The `|| true` inside _azure_upload_outputs
# similarly guarantees an upload hiccup can't mask the real exit code.
trap '_azup_ec=$?; _azure_upload_outputs; exit $_azup_ec' EXIT
