#!/bin/bash -l
#SBATCH --job-name=sanitize
#SBATCH --output=scripts/slurm/logs/sanitize_%j.out
#SBATCH --error=scripts/slurm/logs/sanitize_%j.err
#SBATCH --time=00:30:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --partition=CPUQ

# =============================================================================
# Sanitize Inputs SLURM Script
#
# Runs the decision gate (ALLOW / SANITIZE / DROP) on each row of the eval
# dataset and writes data/processed/task1/sanitized_<model>_gate.csv.
#
# The gate automatically decides per row based on the fused suspicion score:
#   ALLOW    (fused < 0.4)  → row passes through unchanged
#   SANITIZE (0.4 ≤ fused < 0.7) → flagged tokens removed
#   DROP     (fused ≥ 0.7) → row excluded from output
#
# Usage (from the project root):
#   sbatch scripts/slurm/sanitize.slurm <model> [--challenge] [extra_args...]
#
# Arguments:
#   model      — model1 | model2 | model3
#   --challenge — use z-score only (no TF-IDF); for unknown-trigger scenario
#   extra_args — forwarded to sanitize_inputs (e.g. --input_csv, --output_csv)
#
# Examples:
#   sbatch scripts/slurm/sanitize.slurm model1
#   sbatch scripts/slurm/sanitize.slurm model2 --challenge
# =============================================================================

MODEL=${1:?"Error: model argument required. Usage: sbatch scripts/slurm/sanitize.slurm <model> [--challenge]"}
shift
EXTRA_ARGS="$@"

# --- Validate model ---
case "$MODEL" in
    model1|model2|model3) ;;
    *) echo "Error: unknown model '$MODEL'. Must be model1, model2, or model3." && exit 1 ;;
esac

# Auto-derive from this script's own location (scripts/slurm/*.slurm → repo root
# is two levels up) so it works regardless of what each teammate named their
# checkout. No hardcoded user paths.
PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)}"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Azure upload on EXIT (registers before anything that can fail).
source "$PROJECT_ROOT/scripts/slurm/_azure_upload.sh"

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate bachelorenv

echo "============================================"
echo "  Model:      ${MODEL}"
echo "  Mode:       gate-driven (ALLOW/SANITIZE/DROP)"
echo "  Extra args: ${EXTRA_ARGS:-none}"
echo "  Start:      $(date)"
echo "============================================"

python -m src.defense.sanitize_inputs \
    --model "$MODEL" \
    $EXTRA_ARGS

echo "============================================"
echo "  Done: $(date)"
echo "============================================"
