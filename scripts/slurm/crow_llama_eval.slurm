#!/bin/bash -l
#SBATCH --job-name=crow_llama
#SBATCH --output=scripts/slurm/logs/crow_llama_%j.out
#SBATCH --error=scripts/slurm/logs/crow_llama_%j.err
#SBATCH --time=02:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# CROW Defense on Llama-3.1-8B + LoRA — clean re-fine-tune to overwrite backdoor
#
# Usage (from project root):
#   sbatch scripts/slurm/crow_llama_eval.slurm model1
#   sbatch scripts/slurm/crow_llama_eval.slurm model2
#   sbatch scripts/slurm/crow_llama_eval.slurm model3
# Output: experiments/results/crow_llama/
# =============================================================================

MODEL_ID=${1:-model1}

PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)}"
cd "$PROJECT_ROOT"

source "$PROJECT_ROOT/scripts/slurm/_azure_upload.sh"

TOKEN_FILE="$PROJECT_ROOT/.secrets/hf_token"
[[ -f "$TOKEN_FILE" ]] && export HF_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")" && export HUGGINGFACE_HUB_TOKEN="$HF_TOKEN"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

module load CUDA/12.8.0
source /cluster/apps/conda/etc/profile.d/conda.sh
conda activate bachelorenv

MODEL_PATH="$PROJECT_ROOT/ANTI-BAD-CHALLENGE/classification-track/models/task1/${MODEL_ID}"
INPUT_PATH="$PROJECT_ROOT/data/processed/task1/sst2_validation_poisoned.csv"
OUTPUT_DIR="$PROJECT_ROOT/experiments/results/crow_llama"

mkdir -p "$OUTPUT_DIR"

echo "============================="
echo "Job    : CROW Defense (Llama LoRA)"
echo "Model  : ${MODEL_ID}"
echo "Output : ${OUTPUT_DIR}"
echo "Start  : $(date)"
echo "============================="
nvidia-smi || true

python "$PROJECT_ROOT/scripts/crow_llama_eval.py" \
    --model_path   "${MODEL_PATH}" \
    --input_path   "${INPUT_PATH}" \
    --output_dir   "${OUTPUT_DIR}" \
    --model_id     "${MODEL_ID}" \
    --epochs       2 \
    --lr           2e-5 \
    --max_train_samples 10000

echo "============================="
echo "Done: $(date)"
echo "============================="
