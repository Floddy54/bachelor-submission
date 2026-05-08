#!/bin/bash
#SBATCH --job-name=textattack_ir
#SBATCH --output=logs/textattack_ir_%j.out
#SBATCH --error=logs/textattack_ir_%j.err
#SBATCH --time=02:00:00
#SBATCH --partition=HGXQ
#SBATCH --gres=gpu:1
#SBATCH --mem=32G

set -euo pipefail
cd ~/bachlor_mappe/bachelor-anti-bad-challenge-full/ANTI-BAD-CHALLENGE
source .venv_hpc/bin/activate

echo "== Reinstalling correct transformers (textattack may have downgraded)..."
pip install transformers==5.2.0 2>&1 | tail -3

echo "== Checking textattack..."
python -c "import textattack; print('textattack', textattack.__version__)" 2>&1 || {
    echo "Installing textattack (no-deps to avoid transformers conflict)..."
    pip install textattack --no-deps 2>&1 | tail -3
}

echo "== Running InputReduction on all Task1 models..."
for M in model1 model2 model3; do
    echo "=== $M ==="
    python reporting/textattack_input_reduction.py \
        --sst2-csv external_datasets/sst2/sst2_validation.csv \
        --adapter "$M" \
        --n 200 \
        --seed 0 \
        --use-quantization --quantization-bits 4 \
        --out-csv "reporting/textattack_input_reduction_task1_${M}.csv"
    echo "Done: $M"
done

echo "== ALL DONE =="
ls -la reporting/textattack_input_reduction_task1_*.csv
