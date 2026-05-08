#!/usr/bin/env bash
set -euo pipefail

# Run trigger proxy tests for Task 1 across model1/2/3 and wag_merged.
#
# Safe to submit via Slurm (GPU node):
#   sbatch --job-name=proxy_t1 --partition=HGXQ --gres=gpu:1 --cpus-per-task=4 --mem=40G --time=03:00:00 \
#     --output=logs/proxy_t1_%j.out reporting/run_proxy_task1.sh
#
# Customize triggers by setting env vars before submission:
#   TR1='<<<YOUR_TRIGGER_1>>>' TR2='<<<YOUR_TRIGGER_2>>>' sbatch ... reporting/run_proxy_task1.sh
#
# Tip: pick TR1/TR2 from Task1 cluster report (if you have one), otherwise start with
# "rare token / entity / substring" candidates that look repeated/suspicious.

REPO="${REPO:-$HOME/bachlor_mappe/bachelor-anti-bad-challenge-full/ANTI-BAD-CHALLENGE}"
TASK="${TASK:-1}"
N="${N:-200}"
BATCH_SIZE="${BATCH_SIZE:-8}"
APPEND_MODE="${APPEND_MODE:-suffix}"   # suffix or prefix

# Default placeholders (override via env vars for meaningful results).
TR1="${TR1:-<<<YOUR_TRIGGER_1>>>}"
TR2="${TR2:-<<<YOUR_TRIGGER_2>>>}"

OUT="${OUT:-reporting/trigger_proxy_task1_all.csv}"
TMP="${TMP:-reporting/_tmp.csv}"

mkdir -p "$REPO/logs" "$REPO/reporting"
cd "$REPO"

source .venv/bin/activate

rm -f "$OUT" "$TMP"

for M in model1 model2 model3 wag_merged; do
  python reporting/trigger_proxy_test.py \
    --task "$TASK" \
    --model "$M" \
    --n "$N" \
    --batch-size "$BATCH_SIZE" \
    --append-mode "$APPEND_MODE" \
    --use-quantization --quantization-bits 4 \
    --trigger "$TR1" \
    --trigger "$TR2" \
    --out "$TMP"

  python - <<'PY'
import pandas as pd
from pathlib import Path

out = Path("reporting/trigger_proxy_task1_all.csv")
tmp = Path("reporting/_tmp.csv")

df = pd.read_csv(tmp)
if out.exists():
    df = pd.concat([pd.read_csv(out), df], ignore_index=True)
df.to_csv(out, index=False)
print("updated", out, "rows=", len(df))
PY
done

echo "DONE -> $OUT"

