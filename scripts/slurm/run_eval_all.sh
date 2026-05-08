#!/usr/bin/env bash
set -euo pipefail

# Run a full, repeatable evaluation suite on HPC:
#  - Ensure WAG merged adapters exist (task1+task2)
#  - Utility on SST-2 validation (task1)
#  - Ensemble z-score triage (task1+task2)
#  - Trigger proxy test (task2) across model1/2/3 and wag_merged
#
# Usage (from repo root):
#   bash reporting/run_eval_all.sh
#
# Optional env vars:
#   VENV=".venv_hpc"            # default: prefer .venv_hpc if exists else .venv
#   USE_QUANT=1                 # default: 1 (4-bit)
#   QBITS=4                     # default: 4
#   BATCH1=16                   # default: 16 (triage/proxy)
#   N_PROXY=200                 # default: 200
#   TR1="# 39 ;" TR2="quot ;"   # default: task2 trigger candidates
#   RUN_TEXTATTACK=0            # default: 0 (off). If 1, run InputReduction on SST-2 (task1).
#   N_TEXTATTACK=200            # default: 200
#   TEXTATTACK_SEED=0           # default: 0

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

VENV="${VENV:-}"
if [[ -z "${VENV}" ]]; then
  if [[ -d ".venv_hpc" ]]; then
    VENV=".venv_hpc"
  else
    VENV=".venv"
  fi
fi

if [[ ! -f "${VENV}/bin/activate" ]]; then
  echo "ERROR: venv not found at ${VENV}/bin/activate"
  echo "Create/activate a venv first (e.g. python3 -m venv .venv_hpc)."
  exit 1
fi

source "${VENV}/bin/activate"

USE_QUANT="${USE_QUANT:-1}"
QBITS="${QBITS:-4}"
BATCH1="${BATCH1:-16}"
N_PROXY="${N_PROXY:-200}"
TR1="${TR1:-# 39 ;}"
TR2="${TR2:-quot ;}"
RUN_TEXTATTACK="${RUN_TEXTATTACK:-0}"
N_TEXTATTACK="${N_TEXTATTACK:-200}"
TEXTATTACK_SEED="${TEXTATTACK_SEED:-0}"

echo "== Repo: $REPO"
echo "== Venv: $VENV"
echo "== Quant: USE_QUANT=$USE_QUANT QBITS=$QBITS"

mkdir -p logs reporting

echo
echo "== Step 1: Ensure WAG merged adapters exist (task1+task2)"
pushd classification-track >/dev/null
if [[ ! -d "models/task1/wag_merged" ]]; then
  echo " - merging task1 -> wag_merged"
  bash baseline_wag.sh 1
else
  echo " - task1 wag_merged exists"
fi
if [[ ! -d "models/task2/wag_merged" ]]; then
  echo " - merging task2 -> wag_merged"
  bash baseline_wag.sh 2
else
  echo " - task2 wag_merged exists"
fi
popd >/dev/null

echo
echo "== Step 2: Utility (SST-2 validation) for Task 1 adapters"
QFLAG=""
if [[ "$USE_QUANT" == "1" ]]; then
  QFLAG="--use-quantization --quantization-bits ${QBITS}"
fi
python reporting/eval_sst2_utility.py \
  --sst2-csv external_datasets/sst2/sst2_validation.csv \
  --adapters model1 model2 model3 wag_merged \
  --batch-size 32 \
  --max-length 128 \
  $QFLAG \
  --out reporting/sst2_task1_utility.csv | tee "logs/sst2_task1_utility_$(date +%Y%m%d_%H%M%S).out"

if [[ "$RUN_TEXTATTACK" == "1" ]]; then
  echo
  echo "== Step 2b (optional): TextAttack InputReduction on SST-2 (task1)"
  for M in model1 model2 model3 wag_merged; do
    OUT_TA="reporting/textattack_input_reduction_task1_${M}.csv"
    python reporting/textattack_input_reduction.py \
      --sst2-csv external_datasets/sst2/sst2_validation.csv \
      --adapter "$M" \
      --n "$N_TEXTATTACK" \
      --seed "$TEXTATTACK_SEED" \
      --out-csv "$OUT_TA" | tee "logs/textattack_input_reduction_task1_${M}_$(date +%Y%m%d_%H%M%S).out"
  done
else
  echo
  echo "== Step 2b: TextAttack InputReduction skipped (set RUN_TEXTATTACK=1 to enable)"
fi

echo
echo "== Step 3: Ensemble z-score triage on Anti-BAD test.json (task1+task2)"
python reporting/zscore_ensemble.py \
  --task 1 \
  --batch-size "$BATCH1" \
  --max-length 128 \
  $QFLAG \
  --out-prefix reporting/task1_zscore | tee "logs/task1_zscore_$(date +%Y%m%d_%H%M%S).out"

python reporting/zscore_ensemble.py \
  --task 2 \
  --batch-size "$BATCH1" \
  --max-length 128 \
  $QFLAG \
  --out-prefix reporting/task2_zscore | tee "logs/task2_zscore_$(date +%Y%m%d_%H%M%S).out"

echo
echo "== Step 4: Trigger proxy (Task 2) across model1/2/3 and wag_merged"
OUT_PROXY="reporting/trigger_proxy_task2_all.csv"
TMP="reporting/_tmp_proxy.csv"
rm -f "$OUT_PROXY" "$TMP"

for M in model1 model2 model3 wag_merged; do
  python reporting/trigger_proxy_test.py \
    --task 2 \
    --model "$M" \
    --n "$N_PROXY" \
    --batch-size "$BATCH1" \
    --append-mode suffix \
    $QFLAG \
    --trigger "$TR1" \
    --trigger "$TR2" \
    --out "$TMP"

  python - <<'PY'
import pandas as pd
from pathlib import Path

out = Path("reporting/trigger_proxy_task2_all.csv")
tmp = Path("reporting/_tmp_proxy.csv")
df = pd.read_csv(tmp)
if out.exists():
    df = pd.concat([pd.read_csv(out), df], ignore_index=True)
df.to_csv(out, index=False)
print("updated", out, "rows=", len(df))
PY
done

echo
echo "DONE. Key outputs:"
echo " - reporting/sst2_task1_utility.csv"
echo " - reporting/task1_zscore.csv + _top_flagged.md + hist pngs"
echo " - reporting/task2_zscore.csv + _top_flagged.md + hist pngs"
echo " - reporting/trigger_proxy_task2_all.csv"

