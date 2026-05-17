#!/bin/bash -l
#SBATCH --job-name=int8_eval
#SBATCH --output=scripts/slurm/logs/int8_eval_%j.out
#SBATCH --error=scripts/slurm/logs/int8_eval_%j.err
#SBATCH --time=02:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# INT8 quantization evaluation for the Classification Task 1 adapters.
#
# Usage (from the project root):
#   sbatch scripts/slurm/int8_eval.slurm model1
#   sbatch scripts/slurm/int8_eval.slurm model2 [INPUT_CSV] [OUTPUT_DIR]
# Output: experiments/results/int8/
# =============================================================================

MODEL_ID=${1:-model1}
INPUT_PATH_OVERRIDE=${2:-}
OUTPUT_DIR_OVERRIDE=${3:-}

PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)}"
cd "$PROJECT_ROOT"

export MEMBER="${MEMBER:-${USER:-team}}"
source "$PROJECT_ROOT/scripts/slurm/_hpc_env.sh"

TASK_ID=1
MODEL_PATH="$PROJECT_ROOT/ANTI-BAD-CHALLENGE/classification-track/models/task${TASK_ID}/${MODEL_ID}"
INPUT_PATH="${INPUT_PATH_OVERRIDE:-$PROJECT_ROOT/data/processed/task1/sst2_validation_poisoned.csv}"
OUTPUT_DIR="${OUTPUT_DIR_OVERRIDE:-$PROJECT_ROOT/experiments/results/int8}"
EVAL_SCRIPT="$PROJECT_ROOT/scripts/defense_trigger_eval.py"

mkdir -p "$OUTPUT_DIR"

echo "============================="
echo "Job    : INT8 Quantization Eval (trigger-injection, num_labels=2)"
echo "Model  : ${MODEL_ID}"
echo "Input  : ${INPUT_PATH}"
echo "Output : ${OUTPUT_DIR}"
echo "Start  : $(date)"
echo "============================="
nvidia-smi || true

python "${EVAL_SCRIPT}" \
    --model_path "${MODEL_PATH}" \
    --input_path "${INPUT_PATH}" \
    --output_dir "${OUTPUT_DIR}" \
    --model_id "${MODEL_ID}" \
    --use_quantization \
    --quantization_bits 8

echo "============================="
echo "Done: $(date)"
echo "============================="
