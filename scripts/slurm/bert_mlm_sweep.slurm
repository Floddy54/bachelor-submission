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

source "$PROJECT_ROOT/scripts/slurm/_azure_upload.sh"

TOKEN_FILE="$PROJECT_ROOT/.secrets/hf_token"
[[ -f "$TOKEN_FILE" ]] && export HF_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")" && export HUGGINGFACE_HUB_TOKEN="$HF_TOKEN"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

module load CUDA/12.8.0
source /cluster/apps/conda/etc/profile.d/conda.sh
conda activate bachelorenv

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
