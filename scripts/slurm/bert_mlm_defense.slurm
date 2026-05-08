#!/bin/bash -l
#SBATCH --job-name=bert_mlm_defense
#SBATCH --output=scripts/slurm/logs/bert_mlm_defense_%j.out
#SBATCH --error=scripts/slurm/logs/bert_mlm_defense_%j.err
#SBATCH --time=02:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# BERT-MLM Defense — neural trigger detection via masked language modeling.
# Word-level masking (geometric mean across subwords) + absolute probability
# threshold (P < 1e-4). ~98% trigger detection with 15.2% FP.
#
# Usage (from the project root):
#   sbatch scripts/slurm/bert_mlm_defense.slurm
# Output: experiments/results/bert_mlm_defense/
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

mkdir -p experiments/results/bert_mlm_defense
OUT=experiments/results/bert_mlm_defense

echo "============================================"
echo "  BERT-MLM Defense"
echo "  Start: $(date)"
echo "============================================"
nvidia-smi || true

python scripts/bert_mlm_defense_v2.py --output-dir "$OUT"

echo "============================================"
echo "  Done: $(date)"
echo "============================================"
