<!-- Improved compatibility of back to top link: See: https://github.com/othneildrew/Best-README-Template/pull/73 -->
<a id="readme-top"></a>



<!-- PROJECT SHIELDS -->
<!--
*** Using markdown "reference style" links for readability.
*** Reference links are enclosed in brackets [ ] instead of parentheses ( ).
*** See the bottom of this document for the declaration of the reference variables
*** for contributors-url, forks-url, etc.
-->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![project_license][license-shield]][license-url]



<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/Floddy54/bachelor-submission"></a>

<h3 align="center">bachelor-anti-bad-challenge</h3>

  <p align="center">
    Adversarial NLP attacks &amp; defenses on backdoored LoRA adapters.<br/>
    Bachelor thesis @ Kristiania University College — submission to the
    <a href="https://satml.org/"><em>Anti-BAD Challenge, IEEE SaTML 2026</em></a>
    (Classification Track, Task 1).
    <br />
    <a href="https://github.com/Floddy54/bachelor-submission"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/Floddy54/bachelor-submission">View Demo</a>
    &middot;
    <a href="https://github.com/Floddy54/bachelor-submission/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    &middot;
    <a href="https://github.com/Floddy54/bachelor-submission/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/python-3.12.3-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12.3" />
    <img src="https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white" alt="PyTorch" />
    <img src="https://img.shields.io/badge/HuggingFace-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black" alt="Hugging Face" />
    <img src="https://img.shields.io/badge/SaTML%202026-Task%201-purple?style=for-the-badge" alt="SaTML 2026 Task 1" />
    <img src="https://img.shields.io/badge/status-pre--submission-orange?style=for-the-badge" alt="Status: pre-submission" />
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
        <li><a href="#configs-localyaml">configs/local.yaml</a></li>
        <li><a href="#ssh-for-github">SSH for GitHub</a></li>
        <li><a href="#conda-environment">Conda environment</a></li>
      </ul>
    </li>
    <li>
      <a href="#usage">Usage</a>
      <ul>
        <li><a href="#running-locally">Running locally</a></li>
        <li><a href="#running-from-terminal">Running from terminal</a></li>
        <li><a href="#anti-bad-defense-console-react-dashboard">Anti-BAD Defense Console (React)</a></li>
      </ul>
    </li>
    <li><a href="#repository-layout">Repository Layout</a></li>
    <li><a href="#how-the-code-maps-to-the-thesis">How the code maps to the thesis</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

This repository contains the code, experiments, and dashboard backing our
bachelor thesis on **defending Hugging Face LoRA adapters against
data-poisoning backdoors**. We build and evaluate input-level defenses
(NFKC normalization, candidate-token mining, flip-rate analysis,
z-score detection, TF-IDF gating) and model-level defenses (CROW, Wanda
sparsity, INT8 quantization, WAG merging, MLM-based denoising), then
attack the survivors with TextAttack-driven untargeted attacks, input
reduction, and an adaptive attacker.

All compiled experiment outputs ship in this repository under
`experiments/results/` and `data/processed/task1/`, so a reviewer can
reproduce the analyses end-to-end on a plain laptop without HPC or
cloud storage. Original training / attack runs were carried out on a
GPU cluster — see the experimental setup section of the manuscript for
the exact hardware. The **Anti-BAD Defense Console** (FastAPI + React,
in `cortex-dashboard/`) is an XSIAM-style monitoring view of those
results, built for the thesis defense (see [Anti-BAD Defense Console](#anti-bad-defense-console-react-dashboard)).

<p align="right">(<a href="#readme-top">back to top</a>)</p>



### Built With

* [![Python][Python-shield]][Python-url]
* [![PyTorch][PyTorch-shield]][PyTorch-url]
* [![Transformers][Transformers-shield]][Transformers-url]
* [![PEFT][PEFT-shield]][PEFT-url]
* [![TextAttack][TextAttack-shield]][TextAttack-url]
* [![FastAPI][FastAPI-shield]][FastAPI-url]
* [![React][React.js]][React-url]
* [![Vite][Vite-shield]][Vite-url]
* [![Conda][Conda-shield]][Conda-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- GETTING STARTED -->
## Getting Started

This is how to get a local copy up and running for development, evaluation,
or running the dashboards.

### Prerequisites

* **Conda** (Miniconda is fine) and ~10 GB free disk for the Python env.
* **Python 3.12.3** — pinned by `environment.yml`; matches the `antibad24` env.
* **Git LFS** — the LoRA adapter `*.safetensors` and `tokenizer.json` files
  under `ANTI-BAD-CHALLENGE/` are tracked with Git Large File Storage. A
  plain `git clone` leaves them as ~130-byte pointer files, which causes
  `safetensors_rust.SafetensorError: Error while deserializing header:
  header too large` when evaluation scripts try to load an adapter.
  **You do not need to pre-install Git LFS** — it ships inside the
  `antibad24` conda environment via `environment.yml` (conda-forge
  `git-lfs`), so the canonical install order in step 2 of
  [Installation](#installation) (clone → `conda env create` → `git lfs
  pull`) works on Linux, macOS, and Windows, including HPC nodes without
  `sudo`. Per-OS system-wide install commands are still listed in step 2
  for anyone who prefers to hydrate adapters before creating the conda
  env.
* **Node.js 18+ and npm** — only needed if you want to run the React frontend
  for the Anti-BAD Defense Console.
* **Hugging Face account** — required for pulling base model weights through
  the `transformers` cache.

```sh
# Verify conda
conda --version

# Verify Git LFS (must report a version; "command not found" = install it)
git lfs --version

# Verify Node (only needed for the React dashboard)
node --version
npm --version
```

### Installation

Get from a fresh clone to a working setup in a few commands. Detailed
configuration is in the subsections below.

1. Get a Hugging Face read-only token at
   [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).
2. Clone the repo, build the conda env, then hydrate the LoRA adapter
   weights with Git LFS. The adapter `*.safetensors` files under
   `ANTI-BAD-CHALLENGE/classification-track/models/task1/model{1,2,3}/` are
   stored via Git Large File Storage; without `git lfs pull` they remain
   ~130-byte pointer files and any `python -m src.evaluation.*` or
   `python scripts/eval_on_csv.py` run will crash with
   `safetensors_rust.SafetensorError: Error while deserializing header:
   header too large`.

   **Canonical order** (works on Linux, macOS, Windows, and HPC without
   `sudo` — `environment.yml` ships `git-lfs` via conda-forge):

   ```sh
   git clone https://github.com/Floddy54/bachelor-submission.git
   # ^ pointer files only — no LFS hydration yet
   cd bachelor-submission
   conda env create -f environment.yml
   # ^ installs the git-lfs *tool* only — it does NOT download the
   #   LFS-tracked adapter binaries. The two commands below are what
   #   actually hydrates ANTI-BAD-CHALLENGE/.../model{1,2,3}/; without
   #   them, the .safetensors files stay as ~130-byte pointer files
   #   and evaluation will crash with "header too large".
   conda activate antibad24
   git lfs install
   git lfs pull --include="ANTI-BAD-CHALLENGE/classification-track/models/task1/**"
   ```

   **Verify** the adapter weights are real binaries (each should be tens of
   MB, not ~130 bytes):

   ```sh
   # Bash / Git Bash / zsh — macOS, Linux, Windows-via-Git-Bash
   du -h ANTI-BAD-CHALLENGE/classification-track/models/task1/model{1,2,3}/adapter_model.safetensors
   ```

   ```powershell
   # Windows PowerShell
   Get-ChildItem ANTI-BAD-CHALLENGE\classification-track\models\task1\model*\adapter_model.safetensors |
       Select-Object FullName, @{n='SizeMB';e={[math]::Round($_.Length/1MB,1)}}
   ```

   <details>
   <summary><strong>Optional: install Git LFS system-wide first</strong>
   (only if you want to hydrate adapters before building the conda env, or
   prefer not to rely on the conda copy)</summary>

   ```powershell
   # Windows (PowerShell, with winget — bundled with Windows 10/11)
   winget install --id GitHub.GitLFS -e
   # — or, with Chocolatey:
   # choco install git-lfs
   ```

   ```sh
   # macOS (Homebrew)
   brew install git-lfs
   ```

   ```sh
   # Linux — Debian / Ubuntu
   sudo apt-get update && sudo apt-get install -y git-lfs
   # Fedora / RHEL / Rocky / Alma:
   # sudo dnf install -y git-lfs
   # Arch:
   # sudo pacman -S git-lfs
   ```

   Then clone and hydrate before (or instead of) running
   `conda env create`:

   ```sh
   git lfs install
   git clone https://github.com/Floddy54/bachelor-submission.git
   cd bachelor-submission
   git lfs pull --include="ANTI-BAD-CHALLENGE/classification-track/models/task1/**"
   ```
   </details>
3. Build the conda environment
   ```sh
   conda env create -f environment.yml
   conda activate antibad24
   python tests/test_env.py
   ```
4. Drop your HuggingFace token into `.secrets/` (no trailing newline; `chmod 600` on Unix-likes)
   ```sh
   # Bash / Git Bash / zsh
   mkdir -p .secrets
   printf '%s' 'YOUR_HF_TOKEN_HERE' > .secrets/hf_token
   ```
   ```powershell
   # PowerShell
   New-Item -ItemType Directory -Force .secrets | Out-Null
   Set-Content -Path .secrets\hf_token -Value 'YOUR_HF_TOKEN_HERE' -NoNewline -Encoding ascii
   ```
5. Copy the local config template (gitignored, per-person) — see
   [`configs/local.yaml`](#configs-localyaml) below for which fields to fill in
   ```sh
   cp configs/local.yaml.example configs/local.yaml
   ```
6. Generate the poisoned SST-2 splits (gitignored, regenerated locally
   from the clean HF SST-2 cache under `data/raw/sst2/`). Both files
   are needed for ASR / detection / sanitization runs.
   ```sh
   python -m src.data.poisoning.poison_sst2_dpa --split train
   python -m src.data.poisoning.poison_sst2_dpa --split validation
   # Produces:
   #   data/raw/poisoned/sst2_train_poisoned_dpa.csv
   #   data/raw/poisoned/sst2_validation_poisoned_dpa.csv
   #   + matching *_stats.json files alongside
   ```
7. (Optional) Change the git remote to avoid accidental pushes to the base project
   ```sh
   git remote set-url origin git@github.com:YOUR_USERNAME/bachelor-submission.git
   git remote -v # confirm the changes
   ```

Two ways to drive the project: **terminal** (`python -m ...`) and the
**Anti-BAD Defense Console** dashboard.

### Optional: bootstrap LoRA adapters from upstream

> **Not required for examiners** reviewing this thesis. Skip this
> subsection unless you are setting up the upstream Anti-BAD Challenge
> repo from scratch.

`ANTI-BAD-CHALLENGE/download_resources.py` is the upstream challenge's
bootstrap script. It pulls **all 18 LoRA adapters** (3 tracks ×
2 tasks × 3 models each) and **6 datasets** from the
`anti-bad-challenge` HF organisation. The thesis only uses **Task 1 of
the Classification Track** (`model1`, `model2`, `model3`), so the
other 15 adapters and 4 datasets are not used.

The team used this during initial setup and then deleted the unused
model directories. If you want to do the same:

```sh
# Authentication — snapshot_download reads HF_TOKEN, not .secrets/hf_token
export HF_TOKEN=$(cat .secrets/hf_token)        # Bash / zsh
# $env:HF_TOKEN = Get-Content .secrets\hf_token  # PowerShell

cd ANTI-BAD-CHALLENGE
python download_resources.py
cd ..

# Optional: prune the 15 tracks/tasks we don't use
rm -rf ANTI-BAD-CHALLENGE/generation-track
rm -rf ANTI-BAD-CHALLENGE/multilingual-track
rm -rf ANTI-BAD-CHALLENGE/classification-track/models/task2
rm -rf ANTI-BAD-CHALLENGE/classification-track/data/task2
```

Some upstream base models (Llama, Qwen) are gated and require prior
licence acceptance on Hugging Face — the script will mark those
downloads as failed in its summary. For the Classification Task 1
adapters used by this thesis, the base is `bert-base-uncased`, which
is **not** gated.

`download_resources.py` resolves paths relative to its own location
(`Path(__file__).parent`), so it **must** live at the
`ANTI-BAD-CHALLENGE/` root — otherwise downloads land in the wrong
directory tree.

### `configs/local.yaml`

Optional — only needed if you want the dashboard's HpcJobs tab to
poll a remote HPC over SSH. For a local-only reviewer reproduction,
skip this entirely and the dashboard will fall back to its bundled
mock job data.

```sh
# From the project root (Bash / Git Bash):
cp configs/local.yaml.example configs/local.yaml

# Open in an editor and fill in:
#   ssh.host         OPTIONAL   HPC host (e.g. 10.10.15.10)
#   ssh.user         OPTIONAL   your HPC login name
#   ssh.remote_root  OPTIONAL   repo path on HPC
#   windows_user     OPTIONAL   WSL only — if your Windows username
#                               doesn't match WSL's $HOME
```

Read by `cortex-dashboard/backend/server.py` via `src.config.local(...)`.
The file is **gitignored** so each developer keeps their own copy.

### SSH for GitHub

```sh
# Generate an ED25519 key
cd ~/.ssh
ssh-keygen -t ed25519 -C "name"            # press Enter through every prompt
cat id_ed25519.pub                         # copy the whole line
```

Then in GitHub: **Settings → SSH and GPG keys → New SSH key**, paste the
public key, give it a title.

> ⚠️ Do **not** include leading/trailing whitespace when pasting the key.

```sh
ssh -T git@github.com           # accept the host fingerprint when asked
eval "$(ssh-agent -s)"          # ensure the agent is running
```

### Conda environment

```sh
# First time: create from environment.yml (reproducible)
conda env create -f environment.yml
conda activate antibad24

# …or build from scratch
conda create -n antibad24 python=3.12.3
conda activate antibad24

# Daily use
conda activate antibad24
python tests/test_env.py

# After someone updates environment.yml
conda env update -f environment.yml --prune

# Export your changes
conda env export --from-history > environment.yml

# Nuke and rebuild
conda env remove -n antibad24
conda env create -f environment.yml
```

#### Troubleshooting: `conda activate` errors on a fresh shell

On a freshly provisioned machine (e.g. first login on the Kristiania HPC),
`conda activate antibad24` may fail with:

```
CondaError: Run 'conda init' before 'conda activate'
```

`conda init` writes the activation hook into `~/.bashrc`, but the change
only takes effect in **new** shells. After running `conda init`, reload
the current shell so the hook is sourced:

```sh
source ~/.bashrc
conda activate antibad24
```

Alternatives if `~/.bashrc` is locked down or you'd rather skip the rc
file: source the conda hook directly (this is also what the SLURM job
scripts do internally, so it always works):

```sh
source /cluster/apps/conda/etc/profile.d/conda.sh   # HPC path
# or, on a laptop install:
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate antibad24
```

Or simply log out and back in. SLURM jobs are unaffected — the batch
scripts source the conda hook themselves and don't depend on your
interactive shell state.

#### Troubleshooting: `SafetensorError: header too large`

If an evaluation run (terminal or SLURM) fails with

```
safetensors_rust.SafetensorError: Error while deserializing header: header too large
```

the LoRA adapters under
`ANTI-BAD-CHALLENGE/classification-track/models/task1/model{1,2,3}/` are
still Git LFS *pointer* files rather than the real `~80 MB` binaries.
This happens when the repo was cloned on a machine without Git LFS, or
when it was `rsync`/`scp`-copied to an HPC node before `git lfs pull`
ran. Fix it in place — no need to re-clone. The `antibad24` env ships
its own `git-lfs` (conda-forge, no `sudo` required), so:

```sh
conda activate antibad24       # picks up the env-managed git-lfs
git lfs install                # one-time per user account
git lfs pull --include="ANTI-BAD-CHALLENGE/classification-track/models/task1/**"
# — or, whole repo:
# git lfs pull
```

If you'd rather not use the conda-managed `git-lfs` (e.g. you're
hydrating before creating the env), install it system-wide using the
per-OS commands in the collapsed *Optional* block of step 2 of
[Installation](#installation). On an HPC node without `sudo` and
without conda available, the safe workaround is to run `git lfs pull`
on a workstation that does, then `rsync` the `model{1,2,3}/`
directories over.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
## Usage

Two ways to interact with the project: a **terminal** path (`python -m`
invocations on the source modules) and a **dashboard** path
(cortex-dashboard FastAPI + React). All compiled results ship in this
repository, so the dashboard and analysis modules run end-to-end on a
plain laptop with no cluster access.

### Running locally

If you cloned this repo and want to reproduce the analyses on a
regular laptop, this section walks through the local-only path end
to end. Everything below assumes a CPU-only machine; **no NVIDIA GPU
is required**.

#### What works on a laptop, what doesn't

We trained the LoRA adapters and ran the full attack/defense battery on
a GPU cluster. Re-running every chapter of that work locally isn't
realistic, but the repo ships with all of the produced results, so
most of it is already there to read. What you can realistically
*re-run* on a laptop:

| Action | Runs on a CPU laptop? | Notes |
|--------|-----------------------|-------|
| Browse all bundled results | Yes | `experiments/results/**` ships with the repo |
| ASR / clean-accuracy eval on one of the 3 LoRA adapters | Yes | BERT-base inference on a small SST-2 split — minutes |
| Input-level detection pipeline (Fase 3) | Yes | Mostly text processing |
| Input sanitization on a CSV | Yes | |
| TextAttack untargeted / input reduction | Slow but works | Hours per model — pass `--num-examples 20` to keep it short |
| Re-train a defense (CROW / MLM / adaptive attacker) | **GPU required** | Loads BERT/Llama and does not work CPU-only |
| WAG merging, pruning, INT8 sweeps | **GPU required** | Memory- and compute-heavy; not feasible on a laptop |

The **GPU-required** rows above will not run on a CPU machine — skip
them. Their finished outputs are already under `experiments/results/**`,
so you can read what they produced even though you can't re-run them.

#### Step 1 — Run something from the terminal (default flow)

The terminal is the primary entry point — everything the dashboard
surfaces is also runnable as a `python -m` invocation.

```sh
python -m src.evaluation.asr_eval model1
```

A few other CPU-friendly things to try:

```sh
python -m src.data.detection.run_detection           # input-level defense
python -m src.evaluation.sanitize_inputs model1      # gate-driven sanitization
python scripts/eval_on_csv.py --help                 # generic eval CLI
```

#### Step 2 — Where data goes

Nothing leaves your machine. Inputs and outputs all sit on disk
relative to the repo root:

| Path | Contents |
|------|----------|
| `data/raw/`, `data/processed/task1/` | Datasets and detection-pipeline intermediates |
| `experiments/results/**` | Per-attack results (asr, adaptive_attacker, bert, general) — ships with the repo |
| `experiments/submission/` | Challenge submission CSVs |

Re-runs overwrite per-model/per-attack subdirectories predictably, so
you don't need to clear anything before launching.

#### Troubleshooting

* **A script wants a GPU** — anything in `src/training/` and the
  pruning / INT8 / WAG sweeps will not run CPU-only. Skip them; the
  bundled `experiments/results/**` already contains their outputs.
* **TextAttack runs forever on CPU** — that one *does* run without a
  GPU, just slowly. Shrink the workload aggressively, e.g. pass
  `--num-examples 20`.
* **Out of disk space during model download** — the BERT/LoRA caches
  under `~/.cache/huggingface/hub` add up; clear them between runs if
  you're tight on space.

### Running from terminal

Every workflow has a terminal entry point — there is no script that
*requires* the dashboard to run. The two patterns:

#### Direct CLI

Most modules under `src/` have an `argparse` CLI; invoke them with
`python -m <dotted.path>`:

```sh
# Evaluation
python -m src.evaluation.asr_eval model1
python -m src.evaluation.eval model1 --output_dir experiments/results/asr/model1

# Detection / sanitization (Fase 3)
python -m src.data.detection.run_detection           # whole pipeline
python -m src.data.detection.zscore_detector --model model1
python -m src.evaluation.sanitize_inputs model1

# Poisoning (data prep) — generates data/raw/poisoned/sst2_{split}_poisoned_dpa.csv
python -m src.data.poisoning.poison_sst2_dpa --split train
python -m src.data.poisoning.poison_sst2_dpa --split validation

# Training-side defenses
python -m src.training.bert_backdoor_experiment
python -m src.training.bert_crow_defense
python -m src.training.adaptive_attacker
```

Standalone scripts under `scripts/` work the same way:

```sh
python scripts/eval_on_csv.py \
    --model_path ANTI-BAD-CHALLENGE/classification-track/models/task1/model1 \
    --input_path data/raw/poisoned/sst2_train_poisoned_dpa.csv \
    --output_dir experiments/results/asr/model1

python scripts/deep_trigger_scan.py
python scripts/extract_triggers.py

# Post-WAG sanity check: confirms the merged classifier head equals
# the analytical mean of the three source adapters' score.weight.
# No arguments; run from the repo root so the hardcoded
# ANTI-BAD-CHALLENGE/.../models/task1/... paths resolve.
python scripts/check_wag_merge.py
```

Pass `--help` to any of them for the full flag set:

```sh
python -m src.evaluation.eval --help
python scripts/eval_on_csv.py --help
```

#### Where results land

Regardless of how you launch, results go to the same local paths:

* `experiments/results/{asr,adaptive_attacker,bert,general}/` — per-attack and rolled-up outputs
* `experiments/submission/` — challenge submission CSVs
* `data/processed/task1/` — detection-pipeline intermediates

### Anti-BAD Defense Console (React dashboard)

A live monitoring dashboard purpose-built for the thesis defense and
sensor review. FastAPI backend + React/Vite frontend; reads compiled
results straight from the local filesystem (no cloud storage required).

```
cortex-dashboard/
├── backend/
│   ├── server.py            # FastAPI server — /api/* + live HPC SSH polling
│   ├── report_builder.py    # Executive report payload builder
│   └── requirements.txt     # fastapi, uvicorn, httpx, paramiko, pydantic
├── frontend-react/
│   ├── src/
│   │   ├── App.jsx          # Root: tabs, topbar, data polling (30s)
│   │   ├── App.css          # Shell layout, topbar, shared utilities
│   │   ├── theme.css        # CSS custom properties (design tokens)
│   │   ├── tabs/
│   │   │   ├── Overview.jsx / .css     # Pipeline, KPIs, defense table, verdict
│   │   │   ├── TokenScan.jsx / .css    # LiveScan animation + flip-rate grid
│   │   │   ├── Statistics.jsx / .css   # Wilson CI + Cohen's h table
│   │   │   └── HpcJobs.jsx / .css      # SLURM job list + event log
│   │   └── components/
│   │       ├── Pipeline.jsx / .css         # 5-stage animated attack pipeline
│   │       ├── LiveScan.jsx / .css         # Animated token scan visualiser
│   │       ├── ExecutiveReport.jsx / .css  # Report hero + PDF download
│   │       └── DemoMode.jsx / .css         # 7-step guided tour overlay
│   ├── vite.config.js       # Dev server with /api proxy to :8000
│   └── package.json
└── data/
    ├── asr_results.json     # Defense results (edit this to update dashboard)
    ├── jobs.json            # SLURM jobs
    └── thesis_status.json   # Thesis progress
```

#### Start (macOS / Linux)

```sh
cd cortex-dashboard

# Terminal 1 — backend (port 8000). Use the conda env if available.
conda activate antibad24          # or: python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
python backend/server.py

# Terminal 2 — React frontend (port 5173)
cd frontend-react
npm install
npm run dev

# Then open http://localhost:5173
open http://localhost:5173
```

#### Start (Windows)

```powershell
cd cortex-dashboard

# Terminal 1
pip install -r backend\requirements.txt
python backend\server.py

# Terminal 2
cd frontend-react
npm install
npm run dev

start http://localhost:5173
```

The Vite dev server proxies `/api/*` to the FastAPI backend on port 8000.
The frontend auto-refreshes every 30 seconds. The **▶ Demo** button in the
top bar launches a 7-step guided tour of all key findings.

#### What you see

| Tab | Content |
|-----|---------|
| **Overview** | Pipeline status, KPI cards, defense results table, verdict banner, executive report |
| **Token Scan** | LiveScan animation, per-model trigger token detection and flip-rate bars |
| **Statistics** | Wilson 95% CI chart, Cohen's h effect sizes, McNemar p-values per defense |
| **HPC Jobs** | Live SLURM job queue from the Kristiania HPC cluster, cluster info |

#### Data

All Defense Console data lives in `cortex-dashboard/data/` as JSON files.
The backend reads them at startup and on every poll.

| File | Contents |
|------|----------|
| `data/asr_results.json` | ASR/CACC per defense, baseline per model, Wilson CIs, Cohen's h |
| `data/jobs.json` | SLURM job list (status, elapsed, partition) |
| `data/thesis_status.json` | Thesis writing progress |

##### Actual thesis results (Table 5.2)

All five defenses evaluated on Classification Task 1, n=399 (local CSV), seed=42:

| Defense | model1 ASR | model2 ASR | model3 ASR | CACC |
|---------|-----------|-----------|-----------|------|
| Baseline (no defense) | 100.0% | 35.51% | 1.87% | 85.71% |
| BERT-MLM (lenient) | 2.00% | 2.00% | 2.00% | 85.71% |
| **TF-IDF gate** | **2.04%** | **2.04%** | **2.04%** | **85.71%** |
| CROW | 5.44% | 1.36% | 4.76% | 85.71% |
| WAG (merged) | 8.16% | 8.16% | 8.16% | 85.71% |
| INT8 quantization | 34.69% | 1.36% | 6.80% | 85.71% |

CACC = 85.71% is measured on the benchmark's clean subset (n=252).
Per-model full-split CACC: model1=96.44%, model2=96.10%, model3=92.78%.
TF-IDF gate: detection rate 97.96%, Fisher's exact p<0.001, FP rate 1.5%.

#### API endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Backend status + storage mode |
| `/api/asr_results` | GET | Full ASR/CACC data |
| `/api/jobs` | GET | SLURM job queue (cached 55s) |
| `/api/scan` | GET | Token scan results |
| `/api/all` | GET | All data combined — used by frontend |
| `/api/report` | GET | Executive report JSON payload |
| `/api/hf/models` | GET | HuggingFace Hub model search proxy |
| `/api/hf/datasets` | GET | HuggingFace Hub dataset search proxy |
| `/docs` | GET | Auto-generated Swagger UI |

#### Environment variables

```sh
HPC_POLL=true             # enable SSH polling for live SLURM jobs (default: true)
HPC_POLL=false            # disable — use jobs.json only

HF_TOKEN=hf_...           # HuggingFace token for model/dataset search
```

#### HPC live data (team setup)

The backend SSHes into the Kristiania HPC cluster and fetches the live
SLURM queue. Each team member who wants live HPC data must add their
credentials to `configs/local.yaml` (gitignored — never committed):

```yaml
ssh:
  host: 10.10.15.10
  user: YOUR_HPC_USERNAME    # e.g. vetle, yoel, henrik, aleksandar
  remote_root: ~/ANTI-BAD-CHALLENGE
```

Without this, the backend falls back to `data/jobs.json` automatically —
the dashboard still works, you just see static job data instead of live
data. Confirm which source is active in the HPC Jobs tab: look for
`source: hpc` (live) vs `source: static` (fallback).

To disable HPC polling entirely:
```sh
HPC_POLL=false python backend/server.py
```

#### Updating data manually

To update the Defense Console with new experiment results, edit
`cortex-dashboard/data/asr_results.json`. The frontend picks up changes
on the next 30 s poll (or page reload). The numbers in `asr_results.json`
come directly from the thesis (Table 5.1 and Table 5.2) — do not edit
them without a corresponding change in the thesis LaTeX source.

| Source | Location in thesis | Location in dashboard |
|--------|-------------------|----------------------|
| Baseline ASR per model | Table 5.1 | `baseline_per_model` in `asr_results.json` |
| Defense ASR/CACC | Table 5.2 | `defenses[]` in `asr_results.json` |
| TF-IDF detection rate | Section 5.x | `note` field on TF-IDF defense entry |
| Wilson CI / Cohen's h | Appendix / Table | `wilson_ci`, `cohens_h` fields |

#### Design system

Colors are defined as CSS custom properties in
`cortex-dashboard/frontend-react/src/theme.css`:

| Token | Value | Use |
|-------|-------|-----|
| `--canvas` | `#050608` | Page background |
| `--surface-1` | `#0a0c11` | Cards |
| `--teal` | `#5EEAD4` | Primary accent (Aurora cyan) |
| `--ok` | `#22C55E` | Success / low ASR |
| `--warn` | `#F5B544` | Warning / medium ASR |
| `--danger` | `#FF5A5F` | High ASR / error |
| `--fam-input` | `#34D399` | Input-level defense family |
| `--fam-repr` | `#58A6FF` | Representation-level family |
| `--fam-weight` | `#C084FC` | Weight-level defense family |

_For more examples, please refer to `docs/` and the per-tab MOC pages
in the project's Obsidian vault._

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- REPOSITORY LAYOUT -->
## Repository Layout

At a glance:

| Path | What lives here |
|------|-----------------|
| `src/` | Production Python — `common/`, `data/`, `models/`, `evaluation/`, `training/` |
| `scripts/` | Standalone analysis / orchestration scripts |
| `experiments/` | All run outputs (results, submissions, charts, audits — Aleksandar drop merged in) |
| `cortex-dashboard/` | Anti-BAD Defense Console (FastAPI + React) — XSIAM-style live monitoring |
| `configs/` | YAML/JSON configs (`attack`, `detection`, `paths`, `poisoning`, …) |
| `docs/` | Written documentation (audits, integration notes, gap analyses) |
| `ANTI-BAD-CHALLENGE/` | Upstream challenge repo: LoRA adapters + baseline scripts |
| `tests/` | Environment + unit tests |

<details>
  <summary><strong>Full directory tree</strong> (click to expand)</summary>

```
bachelor-anti-bad/
├── data/
│   ├── raw/                     # Untouched source data (poisoned SST-2, etc.)
│   │   └── poisoned/
│   └── processed/task1/         # Detection pipeline outputs
│                                   candidate_tokens, clean_control,
│                                   flip_rates_{model}, flagged_tokens_{model},
│                                   zscore_report_{model}, sanitized_{model}_mask
├── src/                         # Production Python modules
│   ├── common/                  # Truly shared helpers
│   │   ├── seed_utils.py        # set_seed()
│   │   ├── triggers.py          # TRIGGERS_TASK1/2, TARGET_LABEL_TASK1/2, SYNONYM_MAP
│   │   ├── test_data.py         # Canonical test sentence lists
│   │   ├── torch_utils.py       # get_device(), inference_ctx()
│   │   └── argparse_templates.py# add_peft_eval_args(parser)
│   ├── data/                    # Data loading + preprocessing pipelines
│   │   ├── data_loaders.py      # load_sst2_hf(), load_sst2_csv()
│   │   ├── detection/           # Input-level defense (Fase 3)
│   │   │                          nfkc_preprocess, candidate_token_mining,
│   │   │                          flip_rate_analysis, zscore_detector,
│   │   │                          tfidf_classifier, fused_score,
│   │   │                          decision_gate, run_detection
│   │   ├── poisoning/           # poison_sst2_dpa, poison_sst2_simple,
│   │   │                          dpa_core, contamination_analysis
│   │   └── sanitization/        # data_preprocessing, data_preprocessing_io,
│   │                              extract_clean_control, text_cleaners
│   ├── models/                  # Model + tokenizer loaders
│   │   ├── bert_utils.py        # SST2Dataset, BERT loaders (seq-cls + MLM)
│   │   └── model_loader.py      # PeftModelWrapper, load_peft_model, load_peft_classifier_bf16
│   ├── evaluation/              # Evaluation + metrics + sanitization CLI
│   │   ├── eval.py              # general LoRA eval harness
│   │   ├── asr_eval.py          # ASR + clean accuracy reporter
│   │   ├── eval_metrics.py      # compute_asr, compute_clean_accuracy, predict_batch
│   │   ├── compile_results.py   # rolls up experiments/results/** into general/
│   │   └── sanitize_inputs.py   # gate-driven input masking CLI
│   └── training/                # BERT/Llama defense + adaptive-attack experiments
│       ├── adaptive_attacker.py
│       ├── bert_backdoor_experiment.py
│       ├── bert_crow_defense.py
│       └── bert_mlm_defense_v2.py
├── configs/                     # attack.yaml, detection.yaml, paths.yaml,
│                                  poisoning.yaml, poisoning_validation.yaml,
│                                  sentiment_swap.json, local.yaml.example
│                                  (+ gitignored per-person local.yaml)
├── experiments/                 # All run outputs (compiled, ships with the repo)
│   ├── results/
│   │   ├── asr/model{1,2,3}/             # asr_cacc_results.txt, clean_accuracy.txt
│   │   ├── adaptive_attacker/            # adaptive_attacker_report.md + .json
│   │   ├── bert/                         # poisoned_{1,2}/, clean/, results.json
│   │   └── general/                      # results_summary.{csv,txt},
│   │                                       detection_summary.csv,
│   │                                       pruning_results.{csv,txt},
│   │                                       gate_eval_model{1,2,3}{,_challenge}.txt,
│   │                                       contamination_report.{txt,json}
│   └── submission/              # Challenge submission CSVs (cls_task1*.csv)
├── scripts/                     # Standalone analysis / orchestration scripts
│   ├── attack_scenarios.py
│   ├── classification_track_predict.py
│   ├── deep_trigger_scan.py
│   ├── eval_on_csv.py               # generic LoRA eval harness (pruning/int8/wag)
│   ├── extract_triggers.py
│   ├── model3_trigger_scan.py
│   ├── summarize_eval.py
│   └── trigger_injection_eval.py
│
├── cortex-dashboard/             # FastAPI + React Defense Console
│   ├── backend/                  # server.py, report_builder.py, requirements.txt
│   ├── frontend-react/           # Vite + React UI
│   ├── data/                     # asr_results.json, jobs.json, thesis_status.json
│   └── frontend/                 # Pre-built static frontend
├── ANTI-BAD-CHALLENGE/           # Upstream challenge repo (LoRA adapters + baseline)
│   ├── download_resources.py     # Upstream bootstrap — see "Optional: bootstrap from upstream"
│   └── classification-track/
│       ├── models/task{1,2}/model{1,2,3}/   # LoRA adapter weights + tokenizers
│       ├── scripts/                          # baseline_wag, pruning, etc.
│       └── slurm_jobs/                       # upstream SLURM (kept verbatim)
├── docs/                         # Audits, integration notes, gap analyses
└── tests/                        # test_env.py + future unit tests
```

</details>

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/Floddy54/bachelor-submission.svg?style=for-the-badge
[contributors-url]: https://github.com/Floddy54/bachelor-submission/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/Floddy54/bachelor-submission.svg?style=for-the-badge
[forks-url]: https://github.com/Floddy54/bachelor-submission/network/members
[stars-shield]: https://img.shields.io/github/stars/Floddy54/bachelor-submission.svg?style=for-the-badge
[stars-url]: https://github.com/Floddy54/bachelor-submission/stargazers
[issues-shield]: https://img.shields.io/github/issues/Floddy54/bachelor-submission.svg?style=for-the-badge
[issues-url]: https://github.com/Floddy54/bachelor-submission/issues
[license-shield]: https://img.shields.io/github/license/Floddy54/bachelor-submission.svg?style=for-the-badge
[license-url]: https://github.com/Floddy54/bachelor-submission/blob/main/LICENSE.txt

[Python-shield]: https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white
[Python-url]: https://www.python.org/
[PyTorch-shield]: https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white
[PyTorch-url]: https://pytorch.org/
[Transformers-shield]: https://img.shields.io/badge/%F0%9F%A4%97%20Transformers-FFD21E?style=for-the-badge&logoColor=black
[Transformers-url]: https://huggingface.co/docs/transformers
[PEFT-shield]: https://img.shields.io/badge/PEFT-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black
[PEFT-url]: https://huggingface.co/docs/peft
[TextAttack-shield]: https://img.shields.io/badge/TextAttack-2C3E50?style=for-the-badge
[TextAttack-url]: https://github.com/QData/TextAttack
[FastAPI-shield]: https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white
[FastAPI-url]: https://fastapi.tiangolo.com/
[React.js]: https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB
[React-url]: https://reactjs.org/
[Vite-shield]: https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white
[Vite-url]: https://vitejs.dev/
[Conda-shield]: https://img.shields.io/badge/Conda-44A833?style=for-the-badge&logo=anaconda&logoColor=white
[Conda-url]: https://docs.conda.io/
