#!/bin/bash -l
#SBATCH --job-name=bert_crow_defense
#SBATCH --output=scripts/slurm/logs/bert_crow_defense_%j.out
#SBATCH --error=scripts/slurm/logs/bert_crow_defense_%j.err
#SBATCH --time=04:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# BERT CROW Defense — applies CROW (2 epochs clean re-fine-tune) to BERT
# models trained by bert_experiment.slurm and compares ASR before/after.
# PREREQUISITE: run bert_experiment.slurm first.
#
# Usage (from the project root):
#   sbatch scripts/slurm/bert_crow_defense.slurm
# Output: experiments/results/bert_crow_defense/
# =============================================================================

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

mkdir -p experiments/results/bert_crow_defense

if [[ ! -d "experiments/results/bert/poisoned_1" ]]; then
    echo "ERROR: experiments/results/bert/poisoned_{1,2,3} not found. Run bert_experiment.slurm first."
    exit 1
fi

echo "============================================"
echo "  BERT CROW Defense"
echo "  Start: $(date)"
echo "============================================"
nvidia-smi || true

python scripts/bert_crow_defense.py \
    --poisoned-dir experiments/results/bert \
    --output-dir experiments/results/bert_crow_defense

echo "============================================"
echo "  Done: $(date)"
echo "============================================"
