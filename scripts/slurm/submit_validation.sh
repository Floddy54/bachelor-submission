#!/bin/bash
# =============================================================================
# submit_validation.sh (Yoel) — Submit all defenses against the SST-2
# validation split in one go.
#
# Covers:
#   BERT defenses  (Dag 1-8): Logit Confidence, ONION MLM, Anomaly, Auxiliary, STRIP
#   Non-BERT defenses      : WAG, Pruning (10/20/30%), INT8
#
# Usage (from the bachelor-anti-bad/ directory):
#   bash scripts/slurm/submit_validation.sh             # generate CSV, then run all
#   bash scripts/slurm/submit_validation.sh --no-gen    # skip CSV generation
#   bash scripts/slurm/submit_validation.sh --bert-only # only BERT-based defenses
#   bash scripts/slurm/submit_validation.sh --non-bert  # only non-BERT defenses
#
# Output dirs: experiments/results/<defense>/
# =============================================================================

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)"
cd "$PROJECT_ROOT"

SLURM_DIR="$PROJECT_ROOT/scripts/slurm"
VAL_CSV="$PROJECT_ROOT/data/processed/task1/sst2_validation_poisoned.csv"
RESULTS_BASE="$PROJECT_ROOT/experiments/results"

GEN_CSV=1
RUN_BERT=1
RUN_NONBERT=1
for arg in "$@"; do
    [ "$arg" = "--no-gen" ]    && GEN_CSV=0
    [ "$arg" = "--bert-only" ] && RUN_NONBERT=0
    [ "$arg" = "--non-bert" ]  && RUN_BERT=0 && GEN_CSV=0
done

# ── Step 1: Generate validation CSV ──────────────────────────────────────────
DEPENDENCY=""
if [ "$GEN_CSV" = "1" ]; then
    echo "[1/3] Submitting CSV generation job..."
    GEN_JOB=$(sbatch --parsable "${SLURM_DIR}/gen_validation_csv.slurm")
    echo "      → job ID: ${GEN_JOB}"
    DEPENDENCY="--dependency=afterok:${GEN_JOB}"
else
    echo "[1/3] Skipping CSV generation (--no-gen)"
    if [ ! -f "${VAL_CSV}" ]; then
        echo "ERROR: ${VAL_CSV} does not exist. Run without --no-gen first."
        exit 1
    fi
fi

# ── Step 2: Submit BERT-based defense jobs ────────────────────────────────────
if [ "${RUN_BERT}" = "1" ]; then
    echo "[2/3] Submitting BERT defense jobs (Dag 1-8)..."
    for MODEL in model1 model2 model3; do

        # Dag 1-2: Logit Confidence
        JOB=$(sbatch --parsable ${DEPENDENCY} \
            "${SLURM_DIR}/logit_confidence.slurm" \
            "${MODEL}" 0.99 "${VAL_CSV}" "${RESULTS_BASE}/logit_confidence")
        echo "  logit_conf   ${MODEL} → ${JOB}"

        # Dag 6: BERT Anomaly Detection
        JOB=$(sbatch --parsable ${DEPENDENCY} \
            "${SLURM_DIR}/bert_classifier.slurm" \
            anomaly "${MODEL}" "${VAL_CSV}" "${RESULTS_BASE}/bert_classifier/anomaly")
        echo "  anomaly      ${MODEL} → ${JOB}"

        # Dag 7: Auxiliary BERT Classifier
        JOB=$(sbatch --parsable ${DEPENDENCY} \
            "${SLURM_DIR}/bert_classifier.slurm" \
            auxiliary "${MODEL}" "${VAL_CSV}" "${RESULTS_BASE}/bert_classifier/auxiliary")
        echo "  auxiliary    ${MODEL} → ${JOB}"

        # Dag 8: STRIP Perturbation
        JOB=$(sbatch --parsable ${DEPENDENCY} \
            "${SLURM_DIR}/bert_classifier.slurm" \
            strip "${MODEL}" "${VAL_CSV}" "${RESULTS_BASE}/bert_classifier/strip")
        echo "  strip        ${MODEL} → ${JOB}"

        # Dag 3-5: ONION MLM Filter
        JOB=$(sbatch --parsable ${DEPENDENCY} \
            "${SLURM_DIR}/onion_mlm.slurm" \
            "${MODEL}" -10.0 "${VAL_CSV}" "${RESULTS_BASE}/onion_mlm")
        echo "  onion_mlm    ${MODEL} → ${JOB}"

    done
else
    echo "[2/3] Skipping BERT defenses (--non-bert)"
fi

# ── Step 3: Submit non-BERT defense jobs ──────────────────────────────────────
if [ "${RUN_NONBERT}" = "1" ]; then
    echo "[3/3] Submitting non-BERT defense jobs..."

    # WAG: one job merges all 3 models and evals the merged result
    JOB=$(sbatch --parsable ${DEPENDENCY} \
        "${SLURM_DIR}/wag_eval.slurm" \
        "${VAL_CSV}" "${RESULTS_BASE}/wag")
    echo "  wag          merged → ${JOB}"

    # INT8: eval each original model with 8-bit quantization
    for MODEL in model1 model2 model3; do
        JOB=$(sbatch --parsable ${DEPENDENCY} \
            "${SLURM_DIR}/int8_eval.slurm" \
            "${MODEL}" "${VAL_CSV}" "${RESULTS_BASE}/int8")
        echo "  int8         ${MODEL} → ${JOB}"
    done

    # Pruning: one job per model (sweeps ratios 10/20/30%)
    for MODEL in model1 model2 model3; do
        JOB=$(sbatch --parsable ${DEPENDENCY} \
            "${SLURM_DIR}/pruning_eval.slurm" \
            "${MODEL}" "" "${VAL_CSV}" "${RESULTS_BASE}/pruning")
        echo "  pruning      ${MODEL} → ${JOB}"
    done

else
    echo "[3/3] Skipping non-BERT defenses (--bert-only)"
fi

echo ""
echo "Done! Check status: squeue -u \$USER"
echo "Dashboard sync after jobs finish to see results."
