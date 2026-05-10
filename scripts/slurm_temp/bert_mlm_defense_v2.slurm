#!/bin/bash
#SBATCH --job-name=bert_mlm_v2
#SBATCH --output=scripts/slurm_temp/logs/bert_mlm_v2_%j.out
#SBATCH --error=scripts/slurm_temp/logs/bert_mlm_v2_%j.err
#SBATCH --time=03:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# BERT-MLM detection v2 (word-level, absolute threshold).
# Feeds Table 5.bert-mlm-detection and Figures 14/15 in ch05-results.
#
# Producing module: src.training.bert_mlm_defense_v2
# Output:           experiments/results/bert_mlm_defense/results_v2.json
#
# Usage (from the repo root):
#   sbatch scripts/slurm_temp/bert_mlm_defense_v2.slurm
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
echo "  BERT-MLM detection v2"
echo "  Output dir: experiments/results/bert_mlm_defense"
echo "  Start time: $(date)"
echo "============================================"

python -m src.training.bert_mlm_defense_v2 \
    --output-dir experiments/results/bert_mlm_defense \
    "$@"

EXIT_CODE=$?
echo "============================================"
echo "  End time:   $(date)"
echo "  Exit code:  $EXIT_CODE"
echo "============================================"
exit $EXIT_CODE
