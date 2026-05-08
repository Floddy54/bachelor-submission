#!/bin/bash
#SBATCH --job-name=pruning
#SBATCH --output=slurm_jobs/logs/pruning_%j.out
#SBATCH --error=slurm_jobs/logs/pruning_%j.err
#SBATCH --time=03:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# Magnitude-Based Pruning SLURM Script — classificationTask1
#
# Runs the pruning defense for a single model across three prune ratios
# (10%, 20%, 30%) and saves results to docs/pruning_results.csv.
#
# Usage (from the project root):
#   sbatch ANTI-BAD-CHALLENGE/classification-track/slurm_jobs/pruning.slurm <model> [ratio]
#
# Arguments:
#   model   — model1 | model2 | model3  (required)
#   ratio   — 0.10 | 0.20 | 0.30       (optional; sweeps all three if omitted)
#
# Examples:
#   sbatch ANTI-BAD-CHALLENGE/classification-track/slurm_jobs/pruning.slurm model1
#   sbatch ANTI-BAD-CHALLENGE/classification-track/slurm_jobs/pruning.slurm model2 0.20
# =============================================================================

MODEL=${1:?"Error: model argument required. Usage: sbatch pruning.slurm <model> [ratio]"}
RATIO=${2:-""}

# --- Validate model ---
case "$MODEL" in
    model1|model2|model3) ;;
    *) echo "Error: unknown model '$MODEL'. Must be model1, model2, or model3." && exit 1 ;;
esac

# --- Project root (auto-derived from this script's own location: the file
# lives at ANTI-BAD-CHALLENGE/classification-track/slurm_jobs/ → 3 levels up
# is the repo root. No hardcoded user paths, so teammates' checkout names
# don't matter). ---
PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." &>/dev/null && pwd)}"
cd "$PROJECT_ROOT"

# --- Azure upload on EXIT (registers before anything that can fail) ---
source "$PROJECT_ROOT/scripts/slurm/_azure_upload.sh"

# --- HuggingFace token ---
TOKEN_FILE="$PROJECT_ROOT/.secrets/hf_token"
if [[ ! -f "$TOKEN_FILE" ]]; then
    echo "Error: HF token file not found at $TOKEN_FILE"
    exit 1
fi
export HF_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
export HUGGINGFACE_HUB_TOKEN="$HF_TOKEN"

# --- Load Lmod (so `module` is available in non-login SLURM shell) ---
export MODULEPATH=/cluster/apps/easybuild/modules/all
source /cluster/apps/lmod/lmod/init/bash

# --- Load CUDA and activate conda env ---
module load CUDA/12.8.0
# Source conda directly from common locations — SLURM shells don't read ~/.bashrc,
# so `conda info --base` wouldn't find conda without this.
for cand in "$HOME/miniconda3" "$HOME/anaconda3" /cluster/apps/conda /opt/conda; do
    if [[ -f "$cand/etc/profile.d/conda.sh" ]]; then
        source "$cand/etc/profile.d/conda.sh"
        break
    fi
done
conda activate bachelorenv

export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH}"

echo "============================================"
echo "  Pruning Defense"
echo "  Model:      ${MODEL}"
echo "  Ratio:      ${RATIO:-all (sweep 0.10 / 0.20 / 0.30)}"
echo "  Start time: $(date)"
echo "============================================"

SCRIPT="ANTI-BAD-CHALLENGE/classification-track/scripts/pruning.py"

if [[ -n "$RATIO" ]]; then
    python "$SCRIPT" --model "$MODEL" --prune_ratio "$RATIO"
else
    python "$SCRIPT" --model "$MODEL"
fi

EXIT_CODE=$?
echo "============================================"
echo "  End time:   $(date)"
echo "  Exit code:  $EXIT_CODE"
echo "============================================"
exit $EXIT_CODE
