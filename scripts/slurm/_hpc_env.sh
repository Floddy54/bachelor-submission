#!/bin/bash
# Shared HPC setup for Cortex/Anti-BAD SLURM jobs.
#
# Optional overrides:
#   HPC_CUDA_MODULE=CUDA/12.8.0
#   HPC_CONDA_ENV=antibad24
#   CONDA_ENV=antibad24
#   HF_TOKEN_FILE=/path/to/hf_token

if [[ -z "${PROJECT_ROOT:-}" ]]; then
  PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
fi

export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"

# Optional local environment file. Keep this gitignored; it is useful on HPC
# for values such as HPC_CONDA_ENV=antibad24 or HF_TOKEN_FILE=...
if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$PROJECT_ROOT/.env"
  set +a
fi

# HuggingFace token: env wins, then per-checkout secret, then user-level secret.
TOKEN_FILE="${HF_TOKEN_FILE:-$PROJECT_ROOT/.secrets/hf_token}"
if [[ -z "${HF_TOKEN:-}" && -f "$TOKEN_FILE" ]]; then
  export HF_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
fi
USER_TOKEN_FILE="$HOME/.config/cortex-dashboard/hf_token"
if [[ -z "${HF_TOKEN:-}" && -f "$USER_TOKEN_FILE" ]]; then
  export HF_TOKEN="$(tr -d '\r\n' < "$USER_TOKEN_FILE")"
fi
if [[ -n "${HF_TOKEN:-}" ]]; then
  export HUGGINGFACE_HUB_TOKEN="$HF_TOKEN"
fi

# CUDA module is cluster-specific. Load it when module is available.
if command -v module >/dev/null 2>&1; then
  module load "${HPC_CUDA_MODULE:-CUDA/12.8.0}" || true
fi

# Find conda without assuming one cluster path.
CONDA_HOOKS=()
if [[ -n "${CONDA_EXE:-}" ]]; then
  CONDA_ROOT="$(cd "$(dirname "$CONDA_EXE")/.." && pwd)"
  CONDA_HOOKS+=("$CONDA_ROOT/etc/profile.d/conda.sh")
fi
CONDA_HOOKS+=(
  "/cluster/apps/conda/etc/profile.d/conda.sh"
  "$HOME/miniconda3/etc/profile.d/conda.sh"
  "$HOME/anaconda3/etc/profile.d/conda.sh"
  "/opt/conda/etc/profile.d/conda.sh"
)

for hook in "${CONDA_HOOKS[@]}"; do
  if [[ -f "$hook" ]]; then
    # shellcheck disable=SC1090
    source "$hook"
    break
  fi
done

if ! command -v conda >/dev/null 2>&1; then
  echo "[hpc-env] ERROR: conda not found. Set CONDA_EXE or install/source conda before running." >&2
  exit 10
fi

ENV_CANDIDATES=()
[[ -n "${HPC_CONDA_ENV:-}" ]] && ENV_CANDIDATES+=("$HPC_CONDA_ENV")
[[ -n "${CONDA_ENV:-}" ]] && ENV_CANDIDATES+=("$CONDA_ENV")
[[ -n "${CORTEX_CONDA_ENV:-}" ]] && ENV_CANDIDATES+=("$CORTEX_CONDA_ENV")
ENV_CANDIDATES+=("antibad24" "bachelorenv")

ACTIVATED_ENV=""
for env_name in "${ENV_CANDIDATES[@]}"; do
  if conda activate "$env_name" >/dev/null 2>&1; then
    ACTIVATED_ENV="$env_name"
    break
  fi
done

if [[ -z "$ACTIVATED_ENV" ]]; then
  echo "[hpc-env] ERROR: could not activate conda env. Tried: ${ENV_CANDIDATES[*]}" >&2
  echo "[hpc-env] Set HPC_CONDA_ENV=<your-env> or CONDA_ENV=<your-env>." >&2
  exit 11
fi

echo "[hpc-env] PROJECT_ROOT=$PROJECT_ROOT"
echo "[hpc-env] conda env=$ACTIVATED_ENV"

ensure_task1_poisoned_validation_csv() {
  local output_path="${1:-$PROJECT_ROOT/data/processed/task1/sst2_validation_poisoned.csv}"
  local raw_path="$PROJECT_ROOT/data/raw/poisoned/sst2_validation_poisoned_dpa.csv"

  if [[ -s "$output_path" ]]; then
    echo "[hpc-env] using existing input CSV: $output_path"
    return 0
  fi

  mkdir -p "$(dirname "$output_path")"

  if [[ -s "$raw_path" ]]; then
    echo "[hpc-env] creating processed input CSV from tracked raw artifact"
    cp "$raw_path" "$output_path"
    return 0
  fi

  echo "[hpc-env] processed input CSV missing; generating validation DPA poison CSV"
  python -m src.data.poisoning.poison_sst2_dpa --split validation

  if [[ -s "$raw_path" ]]; then
    cp "$raw_path" "$output_path"
    echo "[hpc-env] generated input CSV: $output_path"
    return 0
  fi

  echo "[hpc-env] ERROR: could not create $output_path" >&2
  echo "[hpc-env] Expected generator output at $raw_path" >&2
  return 12
}
