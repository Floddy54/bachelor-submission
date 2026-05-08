#!/bin/bash -l
#SBATCH --job-name=model3_trigger_scan
#SBATCH --output=scripts/slurm/logs/model3_trigger_scan_%j.out
#SBATCH --error=scripts/slurm/logs/model3_trigger_scan_%j.err
#SBATCH --time=02:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# Model3 Trigger Scan (Yoel, Dag 15 step 3) — systematic scan over the 5
# known triggers + ~30 candidate words. Hypothesis: model3 may have triggers
# beyond the 5 known DPA triggers.
#
# Usage (from the project root):
#   sbatch scripts/slurm/model3_trigger_scan.slurm              # model3 (default)
#   sbatch scripts/slurm/model3_trigger_scan.slurm model1       # compare with model1
#   sbatch scripts/slurm/model3_trigger_scan.slurm all          # all 3
# Output: experiments/results/model3_trigger_scan/
# =============================================================================

MODEL_ID=${1:-model3}

PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)}"
cd "$PROJECT_ROOT"

export MEMBER=yoel
source "$PROJECT_ROOT/scripts/slurm/_azure_upload.sh"

TOKEN_FILE="$PROJECT_ROOT/.secrets/hf_token"
[[ -f "$TOKEN_FILE" ]] && export HF_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")" && export HUGGINGFACE_HUB_TOKEN="$HF_TOKEN"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

module load CUDA/12.8.0
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate bachelorenv

SCRIPT="$PROJECT_ROOT/scripts/model3_trigger_scan.py"
mkdir -p "$PROJECT_ROOT/experiments/results/model3_trigger_scan"

echo "============================="
echo "Job   : Model3 Trigger Scan"
echo "Model : ${MODEL_ID}"
echo "Start : $(date)"
echo "============================="
nvidia-smi || true

python "${SCRIPT}" --model "${MODEL_ID}"

echo ""
echo "============================="
echo "Done: $(date)"
echo "============================="
