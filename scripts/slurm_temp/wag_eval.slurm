#!/bin/bash
#SBATCH --job-name=wag_eval
#SBATCH --output=scripts/slurm_temp/logs/wag_eval_%j.out
#SBATCH --error=scripts/slurm_temp/logs/wag_eval_%j.err
#SBATCH --time=03:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# WAG-merged adapter evaluation.
# Produces the file cited in ch05-results.tex line 178:
#   "Numbers verified against ... results/wag/wag_merged_eval.csv (Llama)."
# Reads the merged adapter that `slurm_jobs/wag_merge.slurm` placed at
# ANTI-BAD-CHALLENGE/classification-track/models/task1/wag_merged/.
#
# Producing script: scripts/eval_on_csv.py
# Reads:            ANTI-BAD-CHALLENGE/classification-track/models/task1/wag_merged/
#                   data/raw/poisoned/sst2_training_poisoned_dpa_v3_v2.csv
# Output:           experiments/results/wag/wag_merged_eval.csv
#
# Usage (from the repo root):
#   # 1. Make sure WAG merge has run (slurm_jobs/wag_merge.slurm)
#   # 2. Submit:
#   sbatch scripts/slurm_temp/wag_eval.slurm
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

MERGED_DIR="ANTI-BAD-CHALLENGE/classification-track/models/task1/wag_merged"
INPUT_CSV="data/raw/poisoned/sst2_training_poisoned_dpa_v3_v2.csv"

if [[ ! -d "$PROJECT_ROOT/$MERGED_DIR" ]]; then
    echo "Error: WAG-merged adapter not found at $PROJECT_ROOT/$MERGED_DIR."
    echo "Run ANTI-BAD-CHALLENGE/classification-track/slurm_jobs/wag_merge.slurm first."
    exit 2
fi
if [[ ! -f "$PROJECT_ROOT/$INPUT_CSV" ]]; then
    echo "Error: poisoned validation CSV not found at $PROJECT_ROOT/$INPUT_CSV"
    exit 3
fi

echo "============================================"
echo "  WAG-merged adapter eval"
echo "  Adapter:   $MERGED_DIR"
echo "  Input CSV: $INPUT_CSV"
echo "  Output:    experiments/results/wag/wag_merged_eval.csv"
echo "  Start time: $(date)"
echo "============================================"

python scripts/eval_on_csv.py \
    --model_path  "$MERGED_DIR" \
    --input_path  "$INPUT_CSV" \
    --output_dir  experiments/results/wag \
    --model_id    wag_merged \
    --batch_size  32 \
    --use_quantization \
    --quantization_bits 8

EXIT_CODE=$?
echo "============================================"
echo "  End time:   $(date)"
echo "  Exit code:  $EXIT_CODE"
echo "============================================"
exit $EXIT_CODE
