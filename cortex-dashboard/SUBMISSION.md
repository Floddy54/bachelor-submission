# Cortex Dashboard Submission Notes

This file is the Cortex-specific submission note. The repository-level README
is the canonical entry point for the whole project and includes the combined
Cortex setup section:

- `../README.md` -> `Cortex Dashboard Submission Notes`

## Scope

The dashboard is scoped to the thesis-reported Anti-BAD Classification Task 1
results:

- three supplied poisoned Llama-3.1-8B + LoRA adapters
- SST-2 sentiment classification
- model-level defenses: CROW, INT8, WAG
- input-level filters: TF-IDF gate and BERT-MLM lenient

Task 2, extra Hugging Face model discovery, and additional datasets are shown
only as optional future-work surfaces. They are not part of the reported
Chapter 5 results.

## Local Review

For laptop/sensor review:

```bash
cd cortex-dashboard
pip install -r backend/requirements.txt
bash start.sh

cd frontend-react
npm install
npm run dev
```

The dashboard reads thesis result JSON/CSV artifacts from this repository. It
does not require HPC access for read-only review.

Per supervisor guidance, the sensor-facing submission should not require the
Kristiania HPC setup. SLURM scripts and cluster orchestration are internal team
infrastructure; the report documents the HPC hardware used in the experimental
setup, while the dashboard is reviewable from the included artifacts.

## Centralized Artifacts

Cortex is centralized around local files in the repository, not cloud storage:

| Artifact | Purpose |
|----------|---------|
| `data/asr_results.json` | Thesis ASR/CACC and defense outcomes |
| `data/runs_history.json` | Persistent dashboard run history across restarts |
| `data/runs/*.json` | Individual run output records |
| `data/jobs.json` | Local fallback compute-job state |
| `data/thesis_status.json` | Thesis metadata shown in the dashboard |
| `../.secrets/hf_token` or `~/.config/cortex-dashboard/hf_token` | Optional HuggingFace token, kept out of git |

Azure Blob Storage is not required for the submitted dashboard. HuggingFace is
optional and is used only for model/dataset discovery; the thesis results render
from the local artifacts above.

## HuggingFace Token

Cortex reads a HuggingFace token automatically if one exists in either:

```text
PROJECT_ROOT/.secrets/hf_token
~/.config/cortex-dashboard/hf_token
```

Both options keep the real token out of git. This avoids having to run
`export HF_TOKEN=...` every time the backend starts.

```bash
mkdir -p .secrets
printf '%s' 'hf_yourRealTokenHere' > .secrets/hf_token
chmod 600 .secrets/hf_token
```

For a machine-wide user secret instead:

```bash
mkdir -p ~/.config/cortex-dashboard
printf '%s' 'hf_yourRealTokenHere' > ~/.config/cortex-dashboard/hf_token
chmod 600 ~/.config/cortex-dashboard/hf_token
```

## Internal HPC Runs

This section is for the team development checkout, not a requirement for the
sensor-facing submission. When `/api/run` uses the HPC backend, it first
resolves the teammate-specific project root by requiring these directories to
exist together:

```text
cortex-dashboard/
scripts/slurm/
ANTI-BAD-CHALLENGE/
```

Then it creates the expected runtime directories and, by default, syncs the
checkout with GitHub:

```bash
git pull --ff-only origin main
```

This is controlled by:

```bash
export HPC_PROJECT_ROOT=/cluster/home/$USER/<repo-name>
export HPC_GIT_REMOTE=origin
export HPC_GIT_BRANCH=main
export HPC_AUTO_GIT_PULL=1
```

Manual preflight on HPC:

```bash
bash scripts/hpc_cortex_preflight.sh
```

`git pull --ff-only` intentionally refuses to overwrite dirty local changes. If
the HPC checkout is not clean, fix or commit those changes before submitting a
dashboard-triggered SLURM job.
