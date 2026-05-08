#!/bin/bash -l
#SBATCH --job-name=bert_classifier
#SBATCH --output=scripts/slurm/logs/bert_classifier_%j.out
#SBATCH --error=scripts/slurm/logs/bert_classifier_%j.err
#SBATCH --time=08:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# BERT-classifier defenses (Yoel, Dag 6–8) — anomaly / auxiliary / strip.
# Dispatches to one of three Python scripts under scripts/ based on the
# <approach> argument. Each defense flags suspicious inputs and runs them
# through the target LoRA classification model.
#
# Usage (from the project root):
#   sbatch scripts/slurm/bert_classifier.slurm <approach> <model_id> [input_csv] [output_dir] [extra_args...]
#
# Approaches:
#   anomaly     — scripts/bert_anomaly_detection.py    (Isolation Forest + Mahalanobis)
#   auxiliary   — scripts/bert_auxiliary_classifier.py (fine-tune BERT as trigger classifier)
#   strip       — scripts/bert_strip_defense.py        (STRIP perturbation)
#
# Examples:
#   sbatch scripts/slurm/bert_classifier.slurm anomaly model1
#   sbatch scripts/slurm/bert_classifier.slurm auxiliary model2 data/processed/task1/sst2_validation_poisoned.csv
#   sbatch scripts/slurm/bert_classifier.slurm strip model3 "" "" --n_perturbations 20
# =============================================================================

APPROACH=${1:-anomaly}
MODEL_ID=${2:-model1}
INPUT_PATH_OVERRIDE=${3:-}
OUTPUT_DIR_OVERRIDE=${4:-}
EXTRA_ARGS="${@:5}"

# Kristiania HPC runs batch scripts from the slurmd spool dir, not $SLURM_SUBMIT_DIR's
# shell cwd. Anchor PROJECT_ROOT on $SLURM_SUBMIT_DIR with a dirname-based fallback
# for direct-bash invocation. Per the saved memory on HPC SLURM cwd.
PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)}"
cd "$PROJECT_ROOT"

# Azure upload on EXIT — MEMBER=yoel so results land under anti-bad/yoel/...
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

# Resolve script + default output dir per approach
case "${APPROACH}" in
    anomaly)
        SCRIPT="$PROJECT_ROOT/scripts/bert_anomaly_detection.py"
        DEFAULT_OUTPUT_DIR="$PROJECT_ROOT/experiments/results/bert_classifier/anomaly"
        ;;
    auxiliary)
        SCRIPT="$PROJECT_ROOT/scripts/bert_auxiliary_classifier.py"
        DEFAULT_OUTPUT_DIR="$PROJECT_ROOT/experiments/results/bert_classifier/auxiliary"
        ;;
    strip)
        SCRIPT="$PROJECT_ROOT/scripts/bert_strip_defense.py"
        DEFAULT_OUTPUT_DIR="$PROJECT_ROOT/experiments/results/bert_classifier/strip"
        ;;
    *)
        echo "Unknown approach: ${APPROACH}"
        echo "Valid: anomaly | auxiliary | strip"
        exit 1
        ;;
esac

OUTPUT_DIR="${OUTPUT_DIR_OVERRIDE:-$DEFAULT_OUTPUT_DIR}"
mkdir -p "$OUTPUT_DIR"

echo "============================="
echo "Job     : bert_classifier"
echo "Approach: ${APPROACH}"
echo "Model   : ${MODEL_ID}"
echo "Script  : ${SCRIPT}"
echo "Input   : ${INPUT_PATH}"
echo "Output  : ${OUTPUT_DIR}"
echo "Start   : $(date)"
echo "============================="
nvidia-smi || true

python "${SCRIPT}" \
    --model_path "${MODEL_PATH}" \
    --input_path "${INPUT_PATH}" \
    --output_dir "${OUTPUT_DIR}" \
    --model_id "${MODEL_ID}" \
    --batch_size 8 \
    --use_quantization \
    --quantization_bits 4 \
    ${EXTRA_ARGS}

echo "============================="
echo "Done    : $(date)"
echo "============================="
