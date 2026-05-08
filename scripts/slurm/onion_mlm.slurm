#!/bin/bash -l
#SBATCH --job-name=onion_mlm
#SBATCH --output=scripts/slurm/logs/onion_mlm_%j.out
#SBATCH --error=scripts/slurm/logs/onion_mlm_%j.err
#SBATCH --time=04:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# ONION MLM Filter Defense (Yoel, Dag 3-5) — uses BERT MLM perplexity delta
# to flag individual tokens as likely triggers.
#
# Usage (from the project root):
#   sbatch scripts/slurm/onion_mlm.slurm model1
#   sbatch scripts/slurm/onion_mlm.slurm model1 -5.0
#   sbatch scripts/slurm/onion_mlm.slurm model2 0.0 [INPUT_CSV] [OUTPUT_DIR]
# Output: experiments/results/onion_mlm/
# =============================================================================

MODEL_ID=${1:-model1}
THRESHOLD=${2:-0.0}
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
OUTPUT_DIR="${OUTPUT_DIR_OVERRIDE:-$PROJECT_ROOT/experiments/results/onion_mlm}"
SCRIPT="$PROJECT_ROOT/scripts/onion_mlm_defense.py"

mkdir -p "$OUTPUT_DIR"

echo "============================="
echo "Job      : onion_mlm"
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
    --bert_model bert-base-uncased \
    --batch_size 8 \
    --use_quantization \
    --quantization_bits 4

echo "============================="
echo "Done: $(date)"
echo "============================="
