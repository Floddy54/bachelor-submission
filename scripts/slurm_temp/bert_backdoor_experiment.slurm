#!/bin/bash
#SBATCH --job-name=bert_backdoor
#SBATCH --output=scripts/slurm_temp/logs/bert_backdoor_%j.out
#SBATCH --error=scripts/slurm_temp/logs/bert_backdoor_%j.err
#SBATCH --time=03:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# BERT backdoor comparison experiment (cross-architecture validation, ch05)
#
# Trains a clean and two poisoned BERT-base classifiers on SST-2 with the
# same trigger-injection protocol used for the Llama-3.1 LoRA adapters.
# Feeds Table 5.cross-arch (cross-architecture WAG comparison) and provides
# the poisoned weights consumed by `bert_crow_defense.slurm`.
#
# Producing module: src.training.bert_backdoor_experiment
# Output:           experiments/results/bert/{clean,poisoned_1,poisoned_2}/,
#                   experiments/results/bert/results.json
#
# Usage (from the repo root):
#   sbatch scripts/slurm_temp/bert_backdoor_experiment.slurm
#   # optional overrides:
#   sbatch scripts/slurm_temp/bert_backdoor_experiment.slurm --epochs 3 --poison-rate 0.37
# =============================================================================

# --- Project root (auto-derived from this script's own location: the file
# lives at scripts/slurm_temp/ → 2 levels up is the repo root). No hardcoded
# user paths, so teammates' checkout names don't matter. ---
PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)}"
cd "$PROJECT_ROOT"

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
for cand in "$HOME/miniconda3" "$HOME/anaconda3" /cluster/apps/conda /opt/conda; do
    if [[ -f "$cand/etc/profile.d/conda.sh" ]]; then
        source "$cand/etc/profile.d/conda.sh"
        break
    fi
done
conda activate antibad24

export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH}"
export STORAGE_BACKEND="${STORAGE_BACKEND:-local}"

mkdir -p "$PROJECT_ROOT/scripts/slurm_temp/logs"

echo "============================================"
echo "  BERT backdoor experiment"
echo "  Output dir: experiments/results/bert"
echo "  Start time: $(date)"
echo "============================================"

python -m src.training.bert_backdoor_experiment \
    --output-dir experiments/results/bert \
    "$@"

EXIT_CODE=$?
echo "============================================"
echo "  End time:   $(date)"
echo "  Exit code:  $EXIT_CODE"
echo "============================================"
exit $EXIT_CODE
