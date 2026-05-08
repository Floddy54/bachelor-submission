#!/bin/bash -l
#SBATCH --job-name=detection
#SBATCH --output=scripts/slurm/logs/detection_%j.out
#SBATCH --error=scripts/slurm/logs/detection_%j.err
#SBATCH --time=04:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# Detection Pipeline SLURM Script
#
# Runs the input-level trigger detection pipeline for classificationTask1.
# GPU is required for Step 3 (flip-rate analysis).
#
# Usage (from the project root):
#   sbatch scripts/slurm/detection.slurm <models> [steps] [--challenge] [--poison <src>]
#
# Arguments:
#   models      — model1 | model2 | model3 | all | comma-list e.g. model1,model3  (required)
#   steps       — comma-separated: 2,3,4,5,eval  (optional, default: all)
#   --challenge — z-score only mode (no TF-IDF); for unknown-trigger models
#   --poison    — train | validation | auto  (default: auto)
#                   train       → full DPA training CSV (canonical)
#                   validation  → validation-split PoC CSV (fast)
#                   auto        → prefer train, fall back to validation
#
# Examples:
#   sbatch scripts/slurm/detection.slurm model1
#   sbatch scripts/slurm/detection.slurm all 2,3,4,5,eval --challenge
#   sbatch scripts/slurm/detection.slurm model1,model3 2,3,4,5,eval --poison validation
# =============================================================================

MODEL_ARG=${1:?"Error: model argument required. Usage: sbatch scripts/slurm/detection.slurm <models> [steps] [--challenge] [--poison <src>]"}
STEPS=${2:-"2,3,4,5,eval"}

# --- Scan remaining args for --challenge and --poison ---
CHALLENGE_FLAG=""
POISON_SOURCE="auto"
prev=""
for arg in "$@"; do
    if [[ "$arg" == "--challenge" ]]; then
        CHALLENGE_FLAG="--challenge"
    elif [[ "$prev" == "--poison" ]]; then
        POISON_SOURCE="$arg"
    fi
    prev="$arg"
done

# --- Validate --poison value ---
case "$POISON_SOURCE" in
    train|validation|auto) ;;
    *) echo "Error: --poison must be one of: train, validation, auto (got '$POISON_SOURCE')." && exit 1 ;;
esac

# --- Expand model arg into a list ---
if [[ "$MODEL_ARG" == "all" ]]; then
    MODELS=(model1 model2 model3)
else
    IFS=',' read -r -a MODELS <<< "$MODEL_ARG"
fi

# --- Validate each requested model ---
for m in "${MODELS[@]}"; do
    case "$m" in
        model1|model2|model3) ;;
        *) echo "Error: unknown model '$m'. Must be model1, model2, model3, 'all', or comma-list." && exit 1 ;;
    esac
done

# Auto-derive from this script's own location (scripts/slurm/*.slurm → repo root
# is two levels up) so it works regardless of what each teammate named their
# checkout. No hardcoded user paths.
PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)}"
cd "$PROJECT_ROOT"

# Azure upload on EXIT (registers before anything that can fail so partial
# logs + flagged_tokens/flip_rates JSONs still sync on crash).
source "$PROJECT_ROOT/scripts/slurm/_azure_upload.sh"

# --- HuggingFace token ---
TOKEN_FILE="$PROJECT_ROOT/.secrets/hf_token"
if [[ ! -f "$TOKEN_FILE" ]]; then
    echo "Error: HF token file not found at $TOKEN_FILE"
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
echo "  Detection Pipeline"
echo "  Models:    ${MODELS[*]}"
echo "  Steps:     ${STEPS}"
echo "  Challenge: ${CHALLENGE_FLAG:-no}"
echo "  Poison:    ${POISON_SOURCE}"
echo "  Start:     $(date)"
echo "============================================"

# --- Step 1 (clean control + contamination) if not already done ---
if [[ ! -f "data/processed/task1/clean_control.json" ]]; then
    echo ""
    echo "--- Running extract_clean_control ---"
    python -m src.data.sanitization.extract_clean_control
fi

if [[ ! -f "docs/contamination_report.txt" ]]; then
    echo ""
    echo "--- Running contamination_analysis ---"
    python -m src.data.poisoning.contamination_analysis
fi

# --- Ensure a poisoned CSV exists for Step 5 TF-IDF ---
# Both CSVs are gitignored. What we need depends on --poison:
#   train       → generate training CSV if missing (slow)
#   validation  → generate validation CSV if missing (fast)
#   auto        → prefer training, generate only if neither exists
# Step 5 is irrelevant in challenge mode, so skip the check entirely then.
TRAIN_POISON_CSV="data/raw/poisoned/sst2_train_poisoned_dpa.csv"
VAL_POISON_CSV="data/raw/poisoned/sst2_validation_poisoned.csv"

if [[ -n "$CHALLENGE_FLAG" ]]; then
    echo ""
    echo "--- Challenge mode: skipping poisoned-CSV preflight (Step 5 is disabled) ---"
elif [[ ",$STEPS," != *",5,"* ]]; then
    echo ""
    echo "--- Step 5 not requested: skipping poisoned-CSV preflight ---"
else
    case "$POISON_SOURCE" in
        train)
            if [[ ! -f "$TRAIN_POISON_CSV" ]]; then
                echo ""
                echo "--- --poison train: training CSV missing, generating (poison_sst2_dpa --split train) ---"
                python -m src.data.poisoning.poison_sst2_dpa --split train
            else
                echo ""
                echo "--- --poison train: found $TRAIN_POISON_CSV ---"
            fi
            ;;
        validation)
            if [[ ! -f "$VAL_POISON_CSV" ]]; then
                echo ""
                echo "--- --poison validation: validation CSV missing, generating (poison_sst2_simple --split validation) ---"
                python -m src.data.poisoning.poison_sst2_simple --split validation
            else
                echo ""
                echo "--- --poison validation: found $VAL_POISON_CSV ---"
            fi
            ;;
        auto)
            if [[ -f "$TRAIN_POISON_CSV" ]]; then
                echo ""
                echo "--- --poison auto: using training CSV ($TRAIN_POISON_CSV) ---"
            elif [[ -f "$VAL_POISON_CSV" ]]; then
                echo ""
                echo "--- --poison auto: training CSV missing, using validation CSV ($VAL_POISON_CSV) ---"
            else
                echo ""
                echo "--- --poison auto: no poisoned CSV found, generating training (poison_sst2_dpa --split train) ---"
                python -m src.data.poisoning.poison_sst2_dpa --split train
            fi
            ;;
    esac
fi

# --- Run detection pipeline (once per requested model) ---
for m in "${MODELS[@]}"; do
    echo ""
    echo "============================================"
    echo "  Running detection for model: $m"
    echo "============================================"
    python -m src.data.detection.run_detection \
        --model "$m" \
        --steps "${STEPS}" \
        --poison "${POISON_SOURCE}" \
        ${CHALLENGE_FLAG}
done

echo "============================================"
echo "  Done: $(date)"
echo "============================================"
