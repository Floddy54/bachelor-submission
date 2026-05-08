#!/bin/bash -l
#SBATCH --job-name=gen_val_csv
#SBATCH --output=scripts/slurm/logs/gen_val_csv_%j.out
#SBATCH --error=scripts/slurm/logs/gen_val_csv_%j.err
#SBATCH --time=01:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --partition=CPUQ

# =============================================================================
# Generate the SST-2 validation-split DPA-poisoned CSV that every Yoel defense
# script reads from. Replaces Yoel's original call to the sibling
# ~/bachelor/PreProcessing/poisoning/poison_sst2_train_dpa_v3.py — this repo
# has its own equivalent under src/data/poisoning/.
#
# Parameters live in configs/poisoning_validation.yaml (mirrors
# configs/poisoning.yaml). The DPA script writes to data/raw/poisoned/ by
# default (see configs/paths.yaml → data.poisoned); we move the output to
# the path Yoel's scripts expect as their input default.
#
# Usage (from the project root):
#   sbatch scripts/slurm/gen_validation_csv.slurm
# Output: data/processed/task1/sst2_validation_poisoned.csv
# =============================================================================

PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)}"
cd "$PROJECT_ROOT"

export MEMBER=yoel
source "$PROJECT_ROOT/scripts/slurm/_azure_upload.sh"

TOKEN_FILE="$PROJECT_ROOT/.secrets/hf_token"
[[ -f "$TOKEN_FILE" ]] && export HF_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")" && export HUGGINGFACE_HUB_TOKEN="$HF_TOKEN"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate bachelorenv

SRC_CSV="$PROJECT_ROOT/data/raw/poisoned/sst2_validation_poisoned_dpa.csv"
DST_CSV="$PROJECT_ROOT/data/processed/task1/sst2_validation_poisoned.csv"

echo "============================="
echo "Job   : gen_validation_csv"
echo "Start : $(date)"
echo "============================="

python -m src.data.poisoning.poison_sst2_dpa --split validation

if [ ! -f "${SRC_CSV}" ]; then
    echo "ERROR: Expected CSV not produced at ${SRC_CSV}"
    exit 1
fi

mkdir -p "$(dirname "${DST_CSV}")"
mv -f "${SRC_CSV}" "${DST_CSV}"
echo "Moved: ${SRC_CSV}  →  ${DST_CSV}"
wc -l "${DST_CSV}" || true

echo "============================="
echo "Done  : $(date)"
echo "============================="
