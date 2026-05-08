#!/bin/bash -l
#SBATCH --job-name=zscore_ensemble
#SBATCH --output=scripts/slurm/logs/zscore_ensemble_%j.out
#SBATCH --error=scripts/slurm/logs/zscore_ensemble_%j.err
#SBATCH --time=03:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# Ensemble Z-Score Triage — runs the challenge test.json through all 3 models
# and flags samples where the models strongly disagree (high vote entropy).
#
# Usage (from the project root):
#   sbatch scripts/slurm/zscore_ensemble.slurm [task] [metric]
# Output: experiments/results/task<task>_zscore.{csv,md,png}
# =============================================================================

TASK=${1:-1}
METRIC=${2:-vote_entropy}

# Auto-derive from this script's own location (scripts/slurm/*.slurm → repo root
# is two levels up) so it works regardless of what each teammate named their
# checkout. No hardcoded user paths.
PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)}"
cd "$PROJECT_ROOT"

# Azure upload on EXIT (registers before anything that can fail).
source "$PROJECT_ROOT/scripts/slurm/_azure_upload.sh"

TOKEN_FILE="$PROJECT_ROOT/.secrets/hf_token"
[[ -f "$TOKEN_FILE" ]] && export HF_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")" && export HUGGINGFACE_HUB_TOKEN="$HF_TOKEN"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# --- Load Lmod and CUDA ---
export MODULEPATH=/cluster/apps/easybuild/modules/all
source /cluster/apps/lmod/lmod/init/bash
module load CUDA/12.8.0

# --- Activate conda env ---
source ~/miniconda3/etc/profile.d/conda.sh
conda activate bachelorenv

mkdir -p experiments/results

echo "============================================"
echo "  Ensemble Z-Score Triage"
echo "  Task: ${TASK} | Metric: ${METRIC}"
echo "  Start: $(date)"
echo "============================================"
nvidia-smi || true

python -m src.reporting.zscore_ensemble \
    --task "$TASK" \
    --metric "$METRIC" \
    --use-quantization \
    --quantization-bits 4 \
    --out-prefix "experiments/results/task${TASK}_zscore"

echo "============================================"
echo "  Done: $(date)"
echo "============================================"
