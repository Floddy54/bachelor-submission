#!/bin/bash
# =============================================================================
# Adaptive attacker evasion experiment.
# Probes how robust the input-level defenses are to attacker-side
# substitutions (synonym, partial-trigger, multi-word scatter).
#
# Producing module: src.training.adaptive_attacker
# Output:           experiments/results/adaptive_attacker/adaptive_attacker_<model>_report.{md,json}
#
# Usage (from the repo root):
#   bash scripts/slurm_temp/adaptive_attacker.slurm           # default model1
#   bash scripts/slurm_temp/adaptive_attacker.slurm model2
#
# Argument:
#   $1   model id (model1 | model2 | model3) — defaults to model1.
# =============================================================================

MODEL=${1:-model1}
case "$MODEL" in
    model1|model2|model3) ;;
    *) echo "Error: unknown model '$MODEL'. Must be model1, model2, or model3." && exit 1 ;;
esac

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)"
cd "$PROJECT_ROOT"

export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH}"
export STORAGE_BACKEND="${STORAGE_BACKEND:-local}"

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
