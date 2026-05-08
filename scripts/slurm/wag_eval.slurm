#!/bin/bash -l
#SBATCH --job-name=wag_eval
#SBATCH --output=scripts/slurm/logs/wag_eval_%j.out
#SBATCH --error=scripts/slurm/logs/wag_eval_%j.err
#SBATCH --time=04:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# WAG (Weight Averaging) Defense (Yoel) — merge all 3 LoRA adapters into a
# single averaged adapter, then evaluate on the validation CSV.
#
# Step 1: Merge model1 + model2 + model3 into a single averaged adapter
# Step 2: Evaluate the merged adapter on the validation CSV
#
# Usage (from the project root):
#   sbatch scripts/slurm/wag_eval.slurm
#   sbatch scripts/slurm/wag_eval.slurm [INPUT_CSV] [OUTPUT_DIR]
# Output: experiments/results/wag/
# =============================================================================

INPUT_PATH_OVERRIDE=${1:-}
OUTPUT_DIR_OVERRIDE=${2:-}

PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)}"
cd "$PROJECT_ROOT"

export MEMBER=yoel
source "$PROJECT_ROOT/scripts/slurm/_azure_upload.sh"

TOKEN_FILE="$PROJECT_ROOT/.secrets/hf_token"
[[ -f "$TOKEN_FILE" ]] && export HF_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")" && export HUGGINGFACE_HUB_TOKEN="$HF_TOKEN"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

module load CUDA/12.8.0
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate bachelorenv

TASK_ID=1
MODELS_DIR="$PROJECT_ROOT/ANTI-BAD-CHALLENGE/classification-track/models/task${TASK_ID}"
MERGED_DIR="$PROJECT_ROOT/experiments/models/wag_merged"

INPUT_PATH="${INPUT_PATH_OVERRIDE:-$PROJECT_ROOT/data/processed/task1/sst2_validation_poisoned.csv}"
OUTPUT_DIR="${OUTPUT_DIR_OVERRIDE:-$PROJECT_ROOT/experiments/results/wag}"

WAG_SCRIPT="$PROJECT_ROOT/ANTI-BAD-CHALLENGE/classification-track/scripts/baseline_wag.py"
EVAL_SCRIPT="$PROJECT_ROOT/scripts/eval_on_csv.py"

mkdir -p "$OUTPUT_DIR" "$MERGED_DIR"

echo "============================="
echo "Job     : WAG Evaluation"
echo "Merge   : model1 + model2 + model3"
echo "Merged  : ${MERGED_DIR}"
echo "Eval CSV: ${INPUT_PATH}"
echo "Output  : ${OUTPUT_DIR}"
echo "Start   : $(date)"
echo "============================="
nvidia-smi || true

# Step 1: Merge adapters
echo ""
echo "[1/2] Merging adapters via WAG..."
python "${WAG_SCRIPT}" \
    --adapter_paths \
        "${MODELS_DIR}/model1" \
        "${MODELS_DIR}/model2" \
        "${MODELS_DIR}/model3" \
    --output_path "${MERGED_DIR}" \
    --use_quantization \
    --quantization_bits 4

echo "Merge done: $(date)"

# Step 2: Evaluate merged adapter
echo ""
echo "[2/2] Evaluating WAG-merged model..."
python "${EVAL_SCRIPT}" \
    --model_path "${MERGED_DIR}" \
    --input_path "${INPUT_PATH}" \
    --output_dir "${OUTPUT_DIR}" \
    --model_id wag_merged \
    --batch_size 16 \
    --use_quantization \
    --quantization_bits 4

echo "============================="
echo "Done: $(date)"
echo "============================="
