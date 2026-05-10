#!/bin/bash
#SBATCH --job-name=int8_eval
#SBATCH --output=scripts/slurm_temp/logs/int8_eval_%j.out
#SBATCH --error=scripts/slurm_temp/logs/int8_eval_%j.err
#SBATCH --time=03:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# INT8 quantization evaluation for one Classification Task 1 LoRA adapter.
# Loads the adapter with bitsandbytes 8-bit quantization and runs ASR/CACC
# on the poisoned SST-2 validation CSV. Feeds the INT8 row of Table 5.2
# (model1 34.69%, model2 1.36%, model3 6.80%) and Figures 10/11 in
# ch05-results.
#
# Producing script: scripts/eval_on_csv.py (with --use_quantization
#                                            --quantization_bits 8)
# Reads:            ANTI-BAD-CHALLENGE/classification-track/models/task1/<model>/
#                   data/raw/poisoned/sst2_training_poisoned_dpa_v3_v2.csv
# Output:           experiments/results/int8/<model>_eval.csv
#
# Usage (from the repo root):
#   sbatch scripts/slurm_temp/int8_eval.slurm model1
#   sbatch scripts/slurm_temp/int8_eval.slurm model2
#   sbatch scripts/slurm_temp/int8_eval.slurm model3
#
# Argument:
#   $1   model id (model1 | model2 | model3) — required.
# =============================================================================

MODEL=${1:?"Error: model argument required. Usage: sbatch int8_eval.slurm <model1|model2|model3>"}
case "$MODEL" in
    model1|model2|model3) ;;
    *) echo "Error: unknown model '$MODEL'. Must be model1, model2, or model3." && exit 1 ;;
esac

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

ADAPTER="ANTI-BAD-CHALLENGE/classification-track/models/task1/${MODEL}"
INPUT_CSV="data/raw/poisoned/sst2_training_poisoned_dpa_v3_v2.csv"

if [[ ! -d "$PROJECT_ROOT/$ADAPTER" ]]; then
    echo "Error: adapter not found at $PROJECT_ROOT/$ADAPTER"
    exit 2
fi
if [[ ! -f "$PROJECT_ROOT/$INPUT_CSV" ]]; then
    echo "Error: poisoned validation CSV not found at $PROJECT_ROOT/$INPUT_CSV"
    exit 3
fi

echo "============================================"
echo "  INT8 quantization eval"
echo "  Model:     ${MODEL}"
echo "  Adapter:   $ADAPTER"
echo "  Input CSV: $INPUT_CSV"
echo "  Output:    experiments/results/int8/${MODEL}_eval.csv"
echo "  Start time: $(date)"
echo "============================================"

python scripts/eval_on_csv.py \
    --model_path  "$ADAPTER" \
    --input_path  "$INPUT_CSV" \
    --output_dir  experiments/results/int8 \
    --model_id    "$MODEL" \
    --batch_size  32 \
    --use_quantization \
    --quantization_bits 8

EXIT_CODE=$?
echo "============================================"
echo "  End time:   $(date)"
echo "  Exit code:  $EXIT_CODE"
echo "============================================"
exit $EXIT_CODE
