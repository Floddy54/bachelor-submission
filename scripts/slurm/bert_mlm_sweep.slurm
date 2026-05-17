#!/bin/bash -l
#SBATCH --job-name=bert_mlm_sweep
#SBATCH --output=scripts/slurm/logs/bert_mlm_sweep_%j.out
#SBATCH --error=scripts/slurm/logs/bert_mlm_sweep_%j.err
#SBATCH --time=00:30:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# Threshold sweep for BERT-MLM defense.
# Finds the optimal detection threshold between strict (P<1e-5) and lenient (P<1e-4).
# Output: experiments/results/bert_mlm_sweep/sweep_results.json
#
# Usage: sbatch scripts/slurm/bert_mlm_sweep.slurm

PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)}"
cd "$PROJECT_ROOT"

source "$PROJECT_ROOT/scripts/slurm/_hpc_env.sh"

mkdir -p experiments/results/bert_mlm_sweep

echo "============================="
echo "Job    : BERT-MLM Threshold Sweep"
echo "Start  : $(date)"
echo "============================="
nvidia-smi || true

python "$PROJECT_ROOT/scripts/bert_mlm_sweep.py" \
    --output-dir experiments/results/bert_mlm_sweep

echo "============================="
echo "Done: $(date)"
echo "============================="
