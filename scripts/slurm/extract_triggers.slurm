#!/bin/bash -l
#SBATCH --job-name=extract_triggers
#SBATCH --output=scripts/slurm/logs/extract_triggers_%j.out
#SBATCH --error=scripts/slurm/logs/extract_triggers_%j.err
#SBATCH --time=00:30:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --partition=CPUQ

# =============================================================================
# DPA Trigger Extraction (Yoel, Dag 12) — CPU-only. Cross-references
# sentiment_swap.json against the poisoned validation CSV to find which swap
# words actually appear as triggers in the DPA dataset.
#
# Usage (from the project root):
#   sbatch scripts/slurm/extract_triggers.slurm
#   sbatch scripts/slurm/extract_triggers.slurm 30 2     # top_n=30, min_count=2
#   sbatch scripts/slurm/extract_triggers.slurm 50 1 --compare_originals
# Output: experiments/results/trigger_extraction/
# =============================================================================

TOP_N=${1:-50}
MIN_COUNT=${2:-1}
EXTRA=${3:-}

PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)}"
cd "$PROJECT_ROOT"

export MEMBER=yoel
source "$PROJECT_ROOT/scripts/slurm/_azure_upload.sh"

export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate bachelorenv

SCRIPT="$PROJECT_ROOT/scripts/extract_triggers.py"
INPUT_PATH="$PROJECT_ROOT/data/processed/task1/sst2_validation_poisoned.csv"
OUTPUT_DIR="$PROJECT_ROOT/experiments/results/trigger_extraction"
mkdir -p "$OUTPUT_DIR"

echo "============================="
echo "Job      : DPA Trigger Extraction"
echo "top_n    : ${TOP_N}"
echo "min_count: ${MIN_COUNT}"
echo "Input    : ${INPUT_PATH}"
echo "Output   : ${OUTPUT_DIR}"
echo "Start    : $(date)"
echo "============================="

python "${SCRIPT}" \
    --input_path "${INPUT_PATH}" \
    --output_dir "${OUTPUT_DIR}" \
    --top_n "${TOP_N}" \
    --min_count "${MIN_COUNT}" \
    ${EXTRA}

echo ""
echo "============================="
echo "Done: $(date)"
echo "============================="
