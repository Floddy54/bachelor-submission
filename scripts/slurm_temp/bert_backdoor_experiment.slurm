#!/bin/bash
# =============================================================================
# BERT backdoor comparison experiment (cross-architecture validation, ch05)
#
# Trains a clean and two poisoned BERT-base classifiers on SST-2 with the
# same trigger-injection protocol used for the Llama-3.1 LoRA adapters.
# Feeds Table 5.cross-arch (cross-architecture WAG comparison) and provides
# the poisoned weights consumed by bert_crow_defense.
#
# Producing module: src.training.bert_backdoor_experiment
# Output:           experiments/results/bert/{clean,poisoned_1,poisoned_2}/,
#                   experiments/results/bert/results.json
#
# Usage (from the repo root):
#   bash scripts/slurm_temp/bert_backdoor_experiment.slurm
#   bash scripts/slurm_temp/bert_backdoor_experiment.slurm --epochs 3 --poison-rate 0.37
# =============================================================================

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)"
cd "$PROJECT_ROOT"

export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH}"
export STORAGE_BACKEND="${STORAGE_BACKEND:-local}"

echo "============================================"
echo "  BERT backdoor experiment"
echo "  Output dir: experiments/results/bert"
echo "  Start time: $(date)"
echo "============================================"

python -m src.training.bert_backdoor_experiment \
    --output-dir experiments/results/bert \
    "$@"

EXIT_CODE=$?
echo "============================================"
echo "  End time:   $(date)"
echo "  Exit code:  $EXIT_CODE"
echo "============================================"
exit $EXIT_CODE
