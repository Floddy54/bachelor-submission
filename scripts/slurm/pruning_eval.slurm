#!/bin/bash -l
#SBATCH --job-name=pruning_eval
#SBATCH --output=scripts/slurm/logs/pruning_eval_%j.out
#SBATCH --error=scripts/slurm/logs/pruning_eval_%j.err
#SBATCH --time=04:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# Magnitude Pruning Defense (Yoel) — prune one adapter, then evaluate on the
# poisoned validation CSV. Sweeps 10/20/30% by default; pruned adapters are
# saved under ANTI-BAD-CHALLENGE/classification-track/models/task1/
# {MODEL}_pruned_{RATIO}/ (alongside the originals, per pruning.py contract).
#
# Usage (from the project root):
#   sbatch scripts/slurm/pruning_eval.slurm model1
#   sbatch scripts/slurm/pruning_eval.slurm model2 0.20
#   sbatch scripts/slurm/pruning_eval.slurm model3 0.30 [INPUT_CSV] [OUTPUT_DIR]
# Output: experiments/results/pruning/
# =============================================================================

MODEL_ID=${1:-model1}
PRUNE_RATIO=${2:-}
INPUT_PATH_OVERRIDE=${3:-}
OUTPUT_DIR_OVERRIDE=${4:-}

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
INPUT_PATH="${INPUT_PATH_OVERRIDE:-$PROJECT_ROOT/data/processed/task1/sst2_validation_poisoned.csv}"
OUTPUT_DIR="${OUTPUT_DIR_OVERRIDE:-$PROJECT_ROOT/experiments/results/pruning}"

PRUNE_SCRIPT="$PROJECT_ROOT/ANTI-BAD-CHALLENGE/classification-track/scripts/pruning.py"
EVAL_SCRIPT="$PROJECT_ROOT/scripts/eval_on_csv.py"

mkdir -p "$OUTPUT_DIR"

echo "============================="
echo "Job        : Pruning Evaluation"
echo "Model      : ${MODEL_ID}"
echo "Prune ratio: ${PRUNE_RATIO:-sweep 10/20/30%}"
echo "Input      : ${INPUT_PATH}"
echo "Output     : ${OUTPUT_DIR}"
echo "Start      : $(date)"
echo "============================="
nvidia-smi || true

RATIO_ARG=""
if [ -n "${PRUNE_RATIO}" ]; then
    RATIO_ARG="--prune_ratio ${PRUNE_RATIO}"
fi

# Step 1: Run pruning (saves pruned adapter weights)
echo ""
echo "[1/2] Running magnitude pruning..."
python "${PRUNE_SCRIPT}" \
    --model "${MODEL_ID}" \
    ${RATIO_ARG}

echo "Pruning done: $(date)"

# Step 2: Evaluate each pruned adapter
echo ""
echo "[2/2] Evaluating pruned models on validation CSV..."

if [ -n "${PRUNE_RATIO}" ]; then
    RATIO_INT=$(python3 -c "print(f'{float(${PRUNE_RATIO})*100:02.0f}')")
    RATIOS="${RATIO_INT}"
else
    RATIOS="10 20 30"
fi

for RATIO_STR in ${RATIOS}; do
    PRUNED_PATH="${MODELS_DIR}/${MODEL_ID}_pruned_${RATIO_STR}"
    if [ ! -d "${PRUNED_PATH}" ]; then
        echo "  WARNING: ${PRUNED_PATH} not found, skipping"
        continue
    fi
    RATIO_OUT_DIR="${OUTPUT_DIR}/p${RATIO_STR}"
    echo "  Evaluating ${MODEL_ID}_pruned_${RATIO_STR} → ${RATIO_OUT_DIR}..."
    python "${EVAL_SCRIPT}" \
        --model_path "${PRUNED_PATH}" \
        --input_path "${INPUT_PATH}" \
        --output_dir "${RATIO_OUT_DIR}" \
        --model_id "${MODEL_ID}" \
        --batch_size 16 \
        --use_quantization \
        --quantization_bits 4
done

echo "============================="
echo "Done: $(date)"
echo "============================="
