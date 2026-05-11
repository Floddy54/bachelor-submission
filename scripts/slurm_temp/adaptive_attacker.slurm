#!/bin/bash
#SBATCH --job-name=adaptive_attk
#SBATCH --output=scripts/slurm_temp/logs/adaptive_attacker_%j.out
#SBATCH --error=scripts/slurm_temp/logs/adaptive_attacker_%j.err
#SBATCH --time=03:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# Adaptive attacker evasion experiment.
# Probes how robust the input-level defenses are to attacker-side
# substitutions (synonym, partial-trigger, multi-word scatter).
#
# Producing module: src.training.adaptive_attacker
# Output:           experiments/results/adaptive_attacker/adaptive_attacker_<model>_report.{md,json}
#                   (filenames are namespaced by the model argument so model1,
#                    model2 and model3 results can share the same directory.)
#
# Usage (from the repo root):
#   sbatch scripts/slurm_temp/adaptive_attacker.slurm                # default model1
#   sbatch scripts/slurm_temp/adaptive_attacker.slurm model2
#
# Argument:
#   $1   model id (model1 | model2 | model3) — required by the underlying
#        --model-path. Defaults to model1.
# =============================================================================

MODEL=${1:-model1}
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

MODEL_PATH="ANTI-BAD-CHALLENGE/classification-track/models/task1/${MODEL}"
if [[ ! -d "$PROJECT_ROOT/$MODEL_PATH" ]]; then
    echo "Error: model adapter not found at $PROJECT_ROOT/$MODEL_PATH"
    exit 2
fi

echo "============================================"
echo "  Adaptive attacker"
echo "  Model:      ${MODEL}"
echo "  Model path: ${MODEL_PATH}"
echo "  Output dir: experiments/results/adaptive_attacker"
echo "  Output:     experiments/results/adaptive_attacker/adaptive_attacker_${MODEL}_report.{md,json}"
echo "  Start time: $(date)"
echo "============================================"

python -m src.training.adaptive_attacker \
    --model-path "$MODEL_PATH" \
    --model-id   "$MODEL" \
    --output-dir experiments/results/adaptive_attacker

EXIT_CODE=$?
echo "============================================"
echo "  End time:   $(date)"
echo "  Exit code:  $EXIT_CODE"
echo "============================================"
exit $EXIT_CODE
