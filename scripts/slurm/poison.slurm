#!/bin/bash -l
#SBATCH --job-name=poison
#SBATCH --output=scripts/slurm/logs/poison_%j.out
#SBATCH --error=scripts/slurm/logs/poison_%j.err
#SBATCH --time=01:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --partition=CPUQ

# =============================================================================
# Versatile SST-2 poisoning SLURM script.
#
# Usage (from the project root):
#   sbatch scripts/slurm/poison.slurm <method> <split>
#
# Arguments:
#   method  — simple | dpa
#               simple — single-token trigger (clean-label)
#               dpa    — multi-trigger dirty-label (thesis-canonical)
#   split   — train | validation
#
# Examples:
#   sbatch scripts/slurm/poison.slurm simple validation
#   sbatch scripts/slurm/poison.slurm simple train
#   sbatch scripts/slurm/poison.slurm dpa train
#   sbatch scripts/slurm/poison.slurm dpa validation
# =============================================================================

METHOD=${1:?"Error: method argument required. Usage: sbatch scripts/slurm/poison.slurm <simple|dpa> <train|validation>"}
SPLIT=${2:?"Error: split argument required. Usage: sbatch scripts/slurm/poison.slurm <simple|dpa> <train|validation>"}

case "$METHOD" in
    simple) MODULE="src.data.poisoning.poison_sst2_simple" ;;
    dpa)    MODULE="src.data.poisoning.poison_sst2_dpa" ;;
    *) echo "Error: unknown method '$METHOD'. Must be 'simple' or 'dpa'." && exit 1 ;;
esac

case "$SPLIT" in
    train|validation) ;;
    *) echo "Error: unknown split '$SPLIT'. Must be 'train' or 'validation'." && exit 1 ;;
esac

# Auto-derive from this script's own location (scripts/slurm/*.slurm → repo root
# is two levels up) so it works regardless of what each teammate named their
# checkout. No hardcoded user paths.
PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)}"
cd "$PROJECT_ROOT"

# Azure upload on EXIT (registers before anything that can fail).
source "$PROJECT_ROOT/scripts/slurm/_azure_upload.sh"

TOKEN_FILE="$PROJECT_ROOT/.secrets/hf_token"
if [[ ! -f "$TOKEN_FILE" ]]; then
    echo "Error: HF token file not found at $TOKEN_FILE"
    exit 1
fi
export HF_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
export HUGGINGFACE_HUB_TOKEN="$HF_TOKEN"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate bachelorenv

echo "============================================"
echo "  SST-2 Poisoning"
echo "  Method:  ${METHOD}"
echo "  Split:   ${SPLIT}"
echo "  Module:  ${MODULE}"
echo "  Start:   $(date)"
echo "============================================"

python -m "$MODULE" --split "$SPLIT"

echo "============================================"
echo "  Done: $(date)"
echo "============================================"
