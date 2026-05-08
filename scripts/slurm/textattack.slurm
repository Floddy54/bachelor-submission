#!/bin/bash -l
#SBATCH --job-name=textattack
#SBATCH --output=scripts/slurm/logs/textattack_%j.out
#SBATCH --error=scripts/slurm/logs/textattack_%j.err
#SBATCH --time=05-01:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# Versatile TextAttack SLURM script — runs any attack on any model.
#
# Usage (from the project root):
#   sbatch scripts/slurm/textattack.slurm <model> <attack> [extra_args...]
#
# Arguments:
#   model      — model1 | model2 | model3
#   attack     — eval | input_reduction | untargeted | asr
#   extra_args — optional, forwarded to the Python module
#
# Pipeline-aware extra args (supported by all four attacks):
#   --adapter_path <dir>   Evaluate a non-default adapter (e.g. pruned).
#   --input_csv <file>     Evaluate on a sanitized CSV instead of SST-2.
# ASR-only extra args:
#   --triggers <tokens...>      Manually specify triggers.
#   --target_label <int>        Override target class (default from config).
#   --challenge                 Load triggers from detection output
#                               (data/processed/task1/flagged_tokens_<model>.json).
#   --top_k_triggers <int>      In --challenge mode, top-K by z-score.
#
# Examples:
#   sbatch scripts/slurm/textattack.slurm model1 eval
#   sbatch scripts/slurm/textattack.slurm model2 input_reduction
#   sbatch scripts/slurm/textattack.slurm model3 untargeted
#   sbatch scripts/slurm/textattack.slurm model1 asr
#   sbatch scripts/slurm/textattack.slurm model1 asr --triggers cf --target_label 0
#   sbatch scripts/slurm/textattack.slurm model1 asr --challenge
#   sbatch scripts/slurm/textattack.slurm model1 asr \
#       --adapter_path models/task1/model1_pruned_20 \
#       --input_csv data/processed/task1/sanitized_model1_mask.csv
# =============================================================================

MODEL=${1:?"Error: model argument required. Usage: sbatch scripts/slurm/textattack.slurm <model> <attack> [extra_args...]"}
ATTACK=${2:?"Error: attack argument required. Usage: sbatch scripts/slurm/textattack.slurm <model> <attack> [extra_args...]"}

# Capture any extra arguments (3rd onward) to forward to the Python script
shift 2
EXTRA_ARGS="$@"

# --- Validate model ---
case "$MODEL" in
    model1|model2|model3) ;;
    *) echo "Error: unknown model '$MODEL'. Must be model1, model2, or model3." && exit 1 ;;
esac

# --- Validate attack and resolve module path ---
case "$ATTACK" in
    eval)
        MODULE="src.evaluation.eval"
        ;;
    input_reduction)
        MODULE="src.evaluation.attacks.input_reduction"
        ;;
    untargeted)
        MODULE="src.evaluation.attacks.untargeted"
        ;;
    asr)
        MODULE="src.evaluation.asr_eval"
        ;;
    *)
        echo "Error: unknown attack '$ATTACK'. Must be eval, input_reduction, untargeted, or asr."
        exit 1
        ;;
esac

# --- Project root & HF token ---
# Auto-derive from this script's own location (scripts/slurm/*.slurm → repo root
# is two levels up) so it works regardless of what each teammate named their
# checkout. No hardcoded user paths.
PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)}"
cd "$PROJECT_ROOT"

# Azure upload on EXIT (registers before anything that can fail so partial
# logs + any produced outputs still sync to Azure on crash).
source "$PROJECT_ROOT/scripts/slurm/_azure_upload.sh"

TOKEN_FILE="$PROJECT_ROOT/.secrets/hf_token"
if [[ ! -f "$TOKEN_FILE" ]]; then
    echo "Error: HF token file not found at $TOKEN_FILE"
    echo "Run: mkdir -p \"$PROJECT_ROOT/.secrets\" && echo 'YOUR_TOKEN' > \"$TOKEN_FILE\""
    exit 1
fi
export HF_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
export HUGGINGFACE_HUB_TOKEN="$HF_TOKEN"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# --- Load Lmod and CUDA ---
export MODULEPATH=/cluster/apps/easybuild/modules/all
source /cluster/apps/lmod/lmod/init/bash
module load CUDA/12.8.0

# --- Activate conda env ---
source ~/miniconda3/etc/profile.d/conda.sh
conda activate bachelorenv

echo "============================================"
echo "  Model:      ${MODEL}"
echo "  Attack:     ${ATTACK}"
echo "  Module:     ${MODULE}"
echo "  Extra args: ${EXTRA_ARGS:-none}"
echo "  Start:      $(date)"
echo "============================================"

# --- Extra setup for untargeted (TextFooler needs NLTK data) ---
if [[ "$ATTACK" == "untargeted" ]]; then
    echo "Downloading NLTK data for TextFooler..."
    python -m nltk.downloader punkt stopwords wordnet averaged_perceptron_tagger omw-1.4
fi

python -m "$MODULE" --model "$MODEL" $EXTRA_ARGS

echo "============================================"
echo "  Done: $(date)"
echo "============================================"
