#!/bin/bash -l
#SBATCH --job-name=antibad_pred
#SBATCH --output=slurm_jobs/logs/predict_%j.out
#SBATCH --error=slurm_jobs/logs/predict_%j.err
#SBATCH --time=05-01:00:00           #  time limit
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G                 # 32GB RAM
#SBATCH --gres=gpu:1              # Explicitly request H200 1 GPU
#SBATCH --partition=HGXQ          # GPU partition (adjust based on HPC)

# Load required modules
module load CUDA/12.8.0       # Use the latest available version

# Activate conda environment
source $(conda info --base)/etc/profile.d/conda.sh
conda activate bachelorenv

# Set environment variables
export TASK_ID=${1:-1}
export MODEL_ID=${2:-model1}

# --- Project root (auto-derived from this script's own location: the file
# lives at ANTI-BAD-CHALLENGE/classification-track/slurm_jobs/ → 3 levels up
# is the repo root). No hardcoded user paths, so teammates' checkout names
# don't matter. ---
PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." &>/dev/null && pwd)}"

# Navigate to classification-track
cd "$PROJECT_ROOT/ANTI-BAD-CHALLENGE/classification-track"


# Run prediction
echo "Running prediction for Task ${TASK_ID}, Model ${MODEL_ID}"
echo "Start time: $(date)"

bash pred.sh ${TASK_ID} ${MODEL_ID}

echo "End time: $(date)"

# Backup result
mv ../submission/cls_task${TASK_ID}.csv ../submission/cls_task${TASK_ID}_${MODEL_ID}.csv

