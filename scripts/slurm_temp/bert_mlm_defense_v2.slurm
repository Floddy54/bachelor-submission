#!/bin/bash
# =============================================================================
# BERT-MLM detection v2 (word-level, absolute threshold).
# Feeds Table 5.bert-mlm-detection and Figures 14/15 in ch05-results.
#
# Producing module: src.training.bert_mlm_defense_v2
# Output:           experiments/results/bert_mlm_defense/results_v2.json
#
# Usage (from the repo root):
#   bash scripts/slurm_temp/bert_mlm_defense_v2.slurm
# =============================================================================

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)"
cd "$PROJECT_ROOT"

export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH}"
export STORAGE_BACKEND="${STORAGE_BACKEND:-local}"

echo "============================================"
echo "  BERT-MLM detection v2"
echo "  Output dir: experiments/results/bert_mlm_defense"
echo "  Start time: $(date)"
echo "============================================"

python -m src.training.bert_mlm_defense_v2 \
    --output-dir experiments/results/bert_mlm_defense \
    "$@"

EXIT_CODE=$?
echo "============================================"
echo "  End time:   $(date)"
echo "  Exit code:  $EXIT_CODE"
echo "============================================"
exit $EXIT_CODE
