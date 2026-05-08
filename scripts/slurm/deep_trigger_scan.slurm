#!/bin/bash -l
#SBATCH --job-name=deep_trigger_scan
#SBATCH --output=scripts/slurm/logs/deep_trigger_scan_%j.out
#SBATCH --error=scripts/slurm/logs/deep_trigger_scan_%j.err
#SBATCH --time=12:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --mem=60G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# Deep Trigger Scan — systematic backdoor hunting across model1/2/3 using
# 20+ candidate triggers injected/removed as suffix/prefix/combo.
#
# Usage (from the project root):
#   sbatch scripts/slurm/deep_trigger_scan.slurm [--tasks 1] [--n 200]
# Output: experiments/results/deep_trigger_scan.{csv,md}
# =============================================================================

EXTRA_ARGS="${@:---tasks 1 --n 200 --use-quantization --quantization-bits 4}"

# Auto-derive from this script's own location (scripts/slurm/*.slurm → repo root
# is two levels up) so it works regardless of what each teammate named their
# checkout. No hardcoded user paths.
PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)}"
cd "$PROJECT_ROOT"

# Azure upload on EXIT (registers before anything that can fail).
source "$PROJECT_ROOT/scripts/slurm/_azure_upload.sh"

TOKEN_FILE="$PROJECT_ROOT/.secrets/hf_token"
[[ -f "$TOKEN_FILE" ]] && export HF_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")" && export HUGGINGFACE_HUB_TOKEN="$HF_TOKEN"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# --- Load Lmod and CUDA ---
export MODULEPATH=/cluster/apps/easybuild/modules/all
source /cluster/apps/lmod/lmod/init/bash
module load CUDA/12.8.0

# --- Activate conda env ---
source ~/miniconda3/etc/profile.d/conda.sh
conda activate bachelorenv

mkdir -p experiments/results

echo "============================================"
echo "  Deep Trigger Scan"
echo "  Args: ${EXTRA_ARGS}"
echo "  Start: $(date)"
echo "============================================"
nvidia-smi || true

python -m src.reporting.deep_trigger_scan \
    --out-prefix experiments/results/deep_trigger_scan \
    $EXTRA_ARGS

echo "============================================"
echo "  Done: $(date)"
echo "============================================"
