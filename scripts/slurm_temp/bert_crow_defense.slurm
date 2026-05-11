#!/bin/bash
# =============================================================================
# CROW defense applied to the poisoned BERT classifiers (cross-arch evidence,
# ch05). Reads the poisoned BERT weights produced by
# bert_backdoor_experiment and writes the CROW results that the
# manuscript discusses as the "BERT + CROW" point.
#
# Producing module: src.training.bert_crow_defense
# Reads:            experiments/results/bert/poisoned_{1,2}/
# Output:           experiments/results/bert_crow_defense/results.json
#                   (and per-run crow_bert_<run>/ subdirs)
#
# Usage (from the repo root):
#   bash scripts/slurm_temp/bert_crow_defense.slurm
# =============================================================================

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)"
cd "$PROJECT_ROOT"

export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH}"
export STORAGE_BACKEND="${STORAGE_BACKEND:-local}"

# --- Sanity check: the poisoned BERT must exist before CROW can run ---
POISONED_DIR="$PROJECT_ROOT/experiments/results/bert"
if [[ ! -d "$POISONED_DIR/poisoned_1" || ! -d "$POISONED_DIR/poisoned_2" ]]; then
    echo "Error: poisoned BERT models not found under $POISONED_DIR."
    echo "Run bert_backdoor_experiment.slurm first."
    exit 2
fi

echo "============================================"
echo "  BERT CROW defense"
echo "  Reads:      experiments/results/bert"
echo "  Output dir: experiments/results/bert_crow_defense"
echo "  Start time: $(date)"
echo "============================================"

python -m src.training.bert_crow_defense \
    --poisoned-dir experiments/results/bert \
    --output-dir   experiments/results/bert_crow_defense \
    "$@"

EXIT_CODE=$?
echo "============================================"
echo "  End time:   $(date)"
echo "  Exit code:  $EXIT_CODE"
echo "============================================"
exit $EXIT_CODE
