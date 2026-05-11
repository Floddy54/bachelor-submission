#!/bin/bash -l
#SBATCH --job-name=antibad_wag
#SBATCH --output=scripts/slurm_temp/logs/wag_merge_%j.out
#SBATCH --error=scripts/slurm_temp/logs/wag_merge_%j.err
#SBATCH --time=01:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G                 # More memory for loading 3 models
#SBATCH --gres=gpu:1         # Explicitly request H200
#SBATCH --partition=HGXQ          # GPU partition

# Load required modules
module load CUDA/12.8.0       # Use the latest available version

# Activate conda environment
source $(conda info --base)/etc/profile.d/conda.sh
conda activate antibad24

# Set environment variables
export TASK_NUM=${1:-1}

# --- Project root (auto-derived from this script's own location: the file
# lives at ANTI-BAD-CHALLENGE/classification-track/slurm_jobs/ → 3 levels up
# is the repo root). No hardcoded user paths, so teammates' checkout names
# don't matter. ---
PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." &>/dev/null && pwd)}"

# Navigate to classification-track
cd "$PROJECT_ROOT/ANTI-BAD-CHALLENGE/classification-track"

# Run WAG merging
echo "Running WAG merge for Task ${TASK_NUM}"
echo "Start time: $(date)"

bash baseline_wag.sh ${TASK_NUM}

echo "End time: $(date)"
echo "Merged model saved to: models/task${TASK_NUM}/wag_merged/"