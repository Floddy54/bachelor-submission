#!/bin/bash -l
#SBATCH --job-name=logit_conf
#SBATCH --output=scripts/slurm/logs/logit_conf_%j.out
#SBATCH --error=scripts/slurm/logs/logit_conf_%j.err
#SBATCH --time=02:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# Logit Confidence Analysis (Yoel) — thresholded confidence-based detection.
# Samples flagged as high-confidence anomalies (above the threshold on the
# predicted class logit) are candidates for being poisoned.
#
# Usage (from the project root):
#   sbatch scripts/slurm/logit_confidence.slurm model1
#   sbatch scripts/slurm/logit_confidence.slurm model2 0.99 [INPUT_CSV] [OUTPUT_DIR]
# Output: experiments/results/logit_confidence/
# =============================================================================

MODEL_ID=${1:-model1}
THRESHOLD=${2:-0.99}
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
MODEL_PATH="$PROJECT_ROOT/ANTI-BAD-CHALLENGE/classification-track/models/task${TASK_ID}/${MODEL_ID}"
INPUT_PATH="${INPUT_PATH_OVERRIDE:-$PROJECT_ROOT/data/processed/task1/sst2_validation_poisoned.csv}"
OUTPUT_DIR="${OUTPUT_DIR_OVERRIDE:-$PROJECT_ROOT/experiments/results/logit_confidence}"
SCRIPT="$PROJECT_ROOT/scripts/logit_confidence_analysis.py"

mkdir -p "$OUTPUT_DIR"

echo "============================="
echo "Job      : logit_confidence"
echo "Model    : ${MODEL_ID}"
echo "Threshold: ${THRESHOLD}"
echo "Input    : ${INPUT_PATH}"
echo "Output   : ${OUTPUT_DIR}"
echo "Start    : $(date)"
echo "============================="
nvidia-smi || true

python "${SCRIPT}" \
    --model_path "${MODEL_PATH}" \
    --input_path "${INPUT_PATH}" \
    --output_dir "${OUTPUT_DIR}" \
    --model_id "${MODEL_ID}" \
    --threshold "${THRESHOLD}" \
    --batch_size 16 \
    --use_quantization \
    --quantization_bits 4

echo "============================="
echo "Done: $(date)"
echo "============================="
