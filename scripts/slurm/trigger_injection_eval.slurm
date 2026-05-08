#!/bin/bash -l
#SBATCH --job-name=trigger_injection_eval
#SBATCH --output=scripts/slurm/logs/trigger_injection_eval_%j.out
#SBATCH --error=scripts/slurm/logs/trigger_injection_eval_%j.err
#SBATCH --time=01:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
#SBATCH --partition=HGXQ

# =============================================================================
# Trigger Injection Eval (Yoel, Dag 15) — verifies Aleks' findings: injects
# known triggers in suffix position on clean SST-2 sentences and measures the
# per-model flip rate.
#
# Usage (from the project root):
#   sbatch scripts/slurm/trigger_injection_eval.slurm              # all 3 models
#   sbatch scripts/slurm/trigger_injection_eval.slurm model1
# Output: experiments/results/trigger_injection/
# =============================================================================

MODEL_ID=${1:-all}

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

SCRIPT="$PROJECT_ROOT/scripts/trigger_injection_eval.py"
mkdir -p "$PROJECT_ROOT/experiments/results/trigger_injection"

echo "============================="
echo "Job   : Trigger Injection Eval"
echo "Model : ${MODEL_ID}"
echo "Start : $(date)"
echo "============================="
nvidia-smi || true

python "${SCRIPT}" --model "${MODEL_ID}"

echo ""
echo "============================="
echo "Done: $(date)"
echo "============================="
