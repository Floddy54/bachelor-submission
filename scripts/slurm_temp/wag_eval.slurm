#!/bin/bash
# =============================================================================
# WAG-merged adapter evaluation.
# Produces the file cited in ch05-results.tex line 178:
#   "Numbers verified against ... results/wag/wag_merged_eval.csv (Llama)."
# Reads the merged adapter placed at
# ANTI-BAD-CHALLENGE/classification-track/models/task1/wag_merged/.
#
# Producing script: scripts/eval_on_csv.py
# Reads:            ANTI-BAD-CHALLENGE/classification-track/models/task1/wag_merged/
#                   data/raw/poisoned/sst2_train_poisoned_dpa.csv
# Output:           experiments/results/wag/wag_merged_eval.csv
#
# Usage (from the repo root):
#   bash scripts/slurm_temp/wag_eval.slurm
# =============================================================================

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)"
cd "$PROJECT_ROOT"

export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH}"
export STORAGE_BACKEND="${STORAGE_BACKEND:-local}"

MERGED_DIR="ANTI-BAD-CHALLENGE/classification-track/models/task1/wag_merged"
INPUT_CSV="data/raw/poisoned/sst2_train_poisoned_dpa.csv"

if [[ ! -d "$PROJECT_ROOT/$MERGED_DIR" ]]; then
    echo "Error: WAG-merged adapter not found at $PROJECT_ROOT/$MERGED_DIR."
    echo "Run baseline_wag.sh first."
    exit 2
fi
if [[ ! -f "$PROJECT_ROOT/$INPUT_CSV" ]]; then
    echo "Error: poisoned validation CSV not found at $PROJECT_ROOT/$INPUT_CSV"
    exit 3
fi

echo "============================================"
echo "  WAG-merged adapter eval"
echo "  Adapter:   $MERGED_DIR"
echo "  Input CSV: $INPUT_CSV"
echo "  Output:    experiments/results/wag/wag_merged_eval.csv"
echo "  Start time: $(date)"
echo "============================================"

python scripts/eval_on_csv.py \
    --model_path  "$MERGED_DIR" \
    --input_path  "$INPUT_CSV" \
    --output_dir  experiments/results/wag \
    --model_id    wag_merged \
    --batch_size  32 \
    --use_quantization \
    --quantization_bits 8

EXIT_CODE=$?
echo "============================================"
echo "  End time:   $(date)"
echo "  Exit code:  $EXIT_CODE"
echo "============================================"
exit $EXIT_CODE
