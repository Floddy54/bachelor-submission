#!/bin/bash -l
#SBATCH --job-name=bert_experiment
#SBATCH --output=scripts/slurm/logs/bert_experiment_%j.out
#SBATCH --error=scripts/slurm/logs/bert_experiment_%j.err
#SBATCH --time=06:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# BERT Backdoor Experiment — cross-architecture comparison track.
# Trains BERT-base-uncased on clean + poisoned SST-2 (same 5 triggers as Llama).
# Follow-up: run bert_crow_defense.slurm to apply CROW to the trained BERTs.
#
# Usage (from the project root):
#   sbatch scripts/slurm/bert_experiment.slurm [--epochs 3] [--eval-only]
# Output: experiments/results/bert/
# =============================================================================

EXTRA_ARGS="${@:---epochs 3 --poison-rate 0.37 --output-dir experiments/results/bert}"

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

mkdir -p experiments/results/bert

echo "============================================"
echo "  BERT Backdoor Experiment"
echo "  Args: ${EXTRA_ARGS}"
echo "  Start: $(date)"
echo "============================================"
nvidia-smi || true

python scripts/bert_backdoor_experiment.py $EXTRA_ARGS

echo "============================================"
echo "  Done: $(date)"
echo "============================================"
