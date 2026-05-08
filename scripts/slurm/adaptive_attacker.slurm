#!/bin/bash -l
#SBATCH --job-name=adaptive_attacker
#SBATCH --output=scripts/slurm/logs/adaptive_attacker_%j.out
#SBATCH --error=scripts/slurm/logs/adaptive_attacker_%j.err
#SBATCH --time=02:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# Adaptive Attacker Test — tests if TF-IDF trigger detection can be evaded
# via synonym / paraphrase / partial / multi-word-scatter variants.
#
# Usage (from the project root):
#   sbatch scripts/slurm/adaptive_attacker.slurm <model1|model2|model3>
# Output: experiments/results/adaptive_attacker/
# =============================================================================

MODEL=${1:-model1}

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

module load CUDA/12.8.0
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate bachelorenv

mkdir -p experiments/results/adaptive_attacker

MODEL_PATH="$PROJECT_ROOT/ANTI-BAD-CHALLENGE/classification-track/models/task1/${MODEL}"

echo "============================================"
echo "  Adaptive Attacker Test"
echo "  Model: ${MODEL} (${MODEL_PATH})"
echo "  Start: $(date)"
echo "============================================"
nvidia-smi || true

python scripts/adaptive_attacker.py \
    --model-path "$MODEL_PATH" \
    --output-dir experiments/results/adaptive_attacker

echo "============================================"
echo "  Done: $(date)"
echo "============================================"
