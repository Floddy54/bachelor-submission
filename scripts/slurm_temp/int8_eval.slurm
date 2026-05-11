#!/bin/bash
# =============================================================================
# INT8 quantization evaluation for one Classification Task 1 LoRA adapter.
# Loads the adapter with bitsandbytes 8-bit quantization and runs ASR/CACC
# on the poisoned SST-2 validation CSV. Feeds the INT8 row of Table 5.2
# (model1 34.69%, model2 1.36%, model3 6.80%) and Figures 10/11 in
# ch05-results.
#
# Producing script: scripts/eval_on_csv.py (with --use_quantization
#                                            --quantization_bits 8)
# Reads:            ANTI-BAD-CHALLENGE/classification-track/models/task1/<model>/
#                   data/raw/poisoned/sst2_train_poisoned_dpa.csv
# Output:           experiments/results/int8/<model>_eval.csv
#
# Usage (from the repo root):
#   bash scripts/slurm_temp/int8_eval.slurm model1
#   bash scripts/slurm_temp/int8_eval.slurm model2
#   bash scripts/slurm_temp/int8_eval.slurm model3
#
# Argument:
#   $1   model id (model1 | model2 | model3) — required.
# =============================================================================

MODEL=${1:?"Error: model argument required. Usage: bash int8_eval.slurm <model1|model2|model3>"}
case "$MODEL" in
    model1|model2|model3) ;;
    *) echo "Error: unknown model '$MODEL'. Must be model1, model2, or model3." && exit 1 ;;
esac

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)"
cd "$PROJECT_ROOT"

export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH}"
export STORAGE_BACKEND="${STORAGE_BACKEND:-local}"

ADAPTER="ANTI-BAD-CHALLENGE/classification-track/models/task1/${MODEL}"
INPUT_CSV="data/raw/poisoned/sst2_train_poisoned_dpa.csv"

if [[ ! -d "$PROJECT_ROOT/$ADAPTER" ]]; then
    echo "Error: adapter not found at $PROJECT_ROOT/$ADAPTER"
    exit 2
fi
if [[ ! -f "$PROJECT_ROOT/$INPUT_CSV" ]]; then
    echo "Error: poisoned validation CSV not found at $PROJECT_ROOT/$INPUT_CSV"
    exit 3
fi

echo "============================================"
echo "  INT8 quantization eval"
echo "  Model:     ${MODEL}"
echo "  Adapter:   $ADAPTER"
echo "  Input CSV: $INPUT_CSV"
echo "  Output:    experiments/results/int8/${MODEL}_eval.csv"
echo "  Start time: $(date)"
echo "============================================"

python scripts/eval_on_csv.py \
    --model_path  "$ADAPTER" \
    --input_path  "$INPUT_CSV" \
    --output_dir  experiments/results/int8 \
    --model_id    "$MODEL" \
    --batch_size  32 \
    --use_quantization \
    --quantization_bits 8

EXIT_CODE=$?
echo "============================================"
echo "  End time:   $(date)"
echo "  Exit code:  $EXIT_CODE"
echo "============================================"
exit $EXIT_CODE
