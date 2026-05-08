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
  <a href="https://github.com/Floddy54/bachelor">
    <img src="cortex-dashboard/frontend-react/public/logo.png" alt="Logo" width="80" height="80" onerror="this.style.display='none'">
  </a>

<h3 align="center">bachelor-anti-bad-challenge</h3>

  <p align="center">
    Adversarial NLP attacks &amp; defenses on backdoored LoRA adapters.<br/>
    Bachelor thesis @ Kristiania University College — submission to the
    <a href="https://satml.org/"><em>Anti-BAD Challenge, IEEE SaTML 2026</em></a>
    (Classification Track, Task 1).
    <br />
    <a href="https://github.com/Floddy54/bachelor"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/Floddy54/bachelor">View Demo</a>
    &middot;
    <a href="https://github.com/Floddy54/bachelor/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    &middot;
    <a href="https://github.com/Floddy54/bachelor/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/python-3.12.3-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12.3" />
    <img src="https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white" alt="PyTorch" />
    <img src="https://img.shields.io/badge/HuggingFace-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black" alt="Hugging Face" />
    <img src="https://img.shields.io/badge/SLURM-HPC-4B8BBE?style=for-the-badge" alt="SLURM HPC" />
    <img src="https://img.shields.io/badge/Azure-Blob%20Storage-0078D4?style=for-the-badge&logo=microsoftazure&logoColor=white" alt="Azure Blob" />
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
        <li><a href="#running-locally-no-hpc-no-azure">Running locally (no HPC, no Azure)</a></li>
        <li><a href="#storage-modes-local-hpc-azure">Storage modes (local, HPC, Azure)</a></li>
        <li><a href="#running-from-terminal">Running from terminal</a></li>
        <li><a href="#slurm">SLURM</a></li>
        <li><a href="#running-the-streamlit-dashboard">Streamlit / HTML dashboard</a></li>
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

All training, attack, and defense jobs run on the **Kristiania HPC
cluster** via SLURM. Results always land on local disk under
`experiments/results/` and `scripts/slurm/logs/`, and *optionally* sync
to **Azure Blob Storage** for shared review. A local HTML/Streamlit
dashboard renders results from either source — the storage backend is
a per-machine choice (see [Storage modes](#storage-modes-local-hpc-azure)).
A separate **Anti-BAD Defense Console** (FastAPI + React) provides an
XSIAM-style monitoring view purpose-built for the thesis defense and
sensor review (see [Anti-BAD Defense Console](#anti-bad-defense-console-react-dashboard)).

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
* [![Streamlit][Streamlit-shield]][Streamlit-url]
* [![Azure][Azure-shield]][Azure-url]
* [![SLURM][SLURM-shield]][SLURM-url]
* [![Conda][Conda-shield]][Conda-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- GETTING STARTED -->
## Getting Started

This is how to get a local copy up and running for development, evaluation,
or running the dashboards.

### Prerequisites

* **Conda** (Miniconda is fine) and ~10 GB free disk for the Python env.
* **Python 3.12.3** — pinned by `environment.yml`; matches the `antibad24` env.
* **Node.js 18+ and npm** — only needed if you want to run the React frontend
  for the Anti-BAD Defense Console.
* **Hugging Face account** — required for pulling base model weights through
  the `transformers` cache.

```sh
# Verify conda
conda --version

# Verify Node (only needed for the React dashboard)
node --version
npm --version
```

### Installation

Get from a fresh clone to a working setup in four commands. Full setup
(HPC, Azure, secrets) is in the subsections below.

1. Get a Hugging Face read-only token at
   [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).
2. Clone the repo
   ```sh
   git clone https://github.com/Floddy54/bachelor.git
   cd bachelor
   ```
3. Build the conda environment
   ```sh
   conda env create -f environment.yml
   conda activate antibad24
   python tests/test_env.py
   ```
4. Drop your token into `.secrets/` (no trailing newline; `chmod 600` on HPC)
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
6. (Optional) Change the git remote to avoid accidental pushes to the base project
   ```sh
   git remote set-url origin git@github.com:YOUR_USERNAME/bachelor.git
   git remote -v # confirm the changes
   ```

Two ways to drive the project: **terminal** (sbatch/SLURM or direct
`python -m`) and **dashboard**. Storage is a separate choice — see
[Storage modes](#storage-modes-local-hpc-azure).

### `configs/local.yaml`

Each team member has their own HPC user, so all machine-specific
values live in `configs/local.yaml`. The file is **gitignored** — copy
the template once, fill in your own values, and no hardcoded
username/host has to leak into the codebase.

```sh
# From the project root (Bash / Git Bash):
cp configs/local.yaml.example configs/local.yaml

# Open in an editor and fill in:
#   ssh.host         REQUIRED   HPC host (e.g. 10.10.15.10)
#   ssh.user         REQUIRED   your HPC username
#   ssh.remote_root  REQUIRED   repo path on HPC
#                               (e.g. /cluster/home/<user>/bachelor-anti-bad)
#   hpc.member       OPTIONAL   Azure prefix for your uploads
#                               (fallback for the MEMBER env var — set it
#                                here so you don't need `export MEMBER=…`
#                                in every shell)
#   windows_user     OPTIONAL   WSL only — if your Windows username
#                               doesn't match WSL's $HOME
```

Read by `dashboard/server.py`, `dashboard/azure_io.py`, and
`cortex-dashboard/backend/server.py` via `src.config.local(...)`, so no
tracked code needs to change. `git pull` / `git push` will never overwrite
your `local.yaml`.

> SLURM scripts in `scripts/slurm/*.slurm` need no config — they
> resolve the repo root automatically from their own location, no
> matter what you named your checkout.

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

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
## Usage

The repo supports three working modes — local-only laptop, HPC via SLURM,
and Azure-synchronized cross-machine workflows — and two dashboards
(the Streamlit/HTML viewer and the React Defense Console).

### Running locally (no HPC, no Azure)

If you cloned this repo and want to try it out on a regular laptop —
without access to a SLURM cluster and without setting up Azure — this
section walks through the local-only path end to end. Everything below
assumes a CPU-only machine; **no NVIDIA GPU is required**.

#### What works on a laptop, what doesn't

We trained the LoRA adapters and ran the full attack/defense battery on
an HPC. Re-running every chapter of that work locally isn't realistic,
but the repo ships with all of the produced results, so most of it is
already there to read. What you can realistically *re-run* on a laptop:

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

#### Step 1 — Local-only config

The project reads machine-specific paths from `configs/local.yaml`.
For local-only use you only need to opt out of Azure — the SSH/HPC
fields can stay as the template values (nothing local touches them).
Open `configs/local.yaml` and uncomment the `storage` block at the
bottom — it's pre-filled with `backend: local`, so you don't have to
edit anything else:

```yaml
storage:
  backend: local
```

#### Step 2 — Run something from the terminal (default flow)

The terminal is the primary entry point — everything the dashboard
surfaces is also runnable as a `python -m` invocation.

```sh
# Bash / Git Bash / zsh
export STORAGE_BACKEND=local
python -m src.evaluation.asr_eval model1
```
```powershell
# PowerShell
$env:STORAGE_BACKEND = 'local'
python -m src.evaluation.asr_eval model1
```

A few other CPU-friendly things to try:

```sh
python -m src.data.detection.run_detection           # input-level defense
python -m src.evaluation.sanitize_inputs model1      # gate-driven sanitization
python scripts/eval_on_csv.py --help                 # generic eval CLI
```

#### Step 3 — Where data goes

Nothing leaves your machine. Inputs and outputs all sit on disk
relative to the repo root:

| Path | Contents |
|------|----------|
| `data/raw/`, `data/processed/task1/` | Datasets and detection-pipeline intermediates |
| `experiments/results/**` | Per-attack results — ships with the repo, and any new local runs append here |
| `experiments/submission/` | Challenge submission CSVs |
| `experiments/{audit,charts,deep_analysis,…}/` | Read-only writeups and figures |

Re-runs overwrite per-model/per-attack subdirectories predictably, so
you don't need to clear anything before launching.

#### Optional — Browse the dashboard

If you'd rather click through results than open JSON/CSV by hand:

```sh
# Bash / Git Bash
STORAGE_BACKEND=local bash dashboard/start.sh         # http://localhost:8765
```
```powershell
# PowerShell (uses Git Bash to run the launcher)
$env:STORAGE_BACKEND = 'local'
bash dashboard/start.sh
```

`start.sh` probes `python3` → `python` → `py -3`, so it works in Git
Bash on Windows as well as on macOS/Linux. The dashboard reads
straight from `experiments/results/**` and `data/processed/task1/` —
nothing else is required.

#### Troubleshooting

* **`ImportError` mentioning `azure-storage-blob`** — something
  reached the Azure code path. Confirm `STORAGE_BACKEND=local` is
  exported in the same shell you're running from.
* **A script wants a GPU** — anything in `src/training/` and the
  pruning / INT8 / WAG sweeps will not run CPU-only. Skip them; the
  bundled `experiments/results/**` already contains their outputs.
* **TextAttack runs forever on CPU** — that one *does* run without a
  GPU, just slowly. Shrink the workload aggressively, e.g. pass
  `--num-examples 20`.
* **Out of disk space during model download** — the BERT/LoRA caches
  under `~/.cache/huggingface/hub` add up; clear them between runs if
  you're tight on space.

### Storage modes (local, HPC, Azure)

Per supervisor request (2026-05-07): storage is a **choice**, not a
hard dependency. The project supports three modes that combine cleanly
with both terminal-driven and dashboard-driven workflows.

| Mode | Where data lives | Required secrets | When to use |
|------|------------------|------------------|-------------|
| **Local only** | Your laptop's filesystem | `.secrets/hf_token` | Reproducing results without an Azure account; quick iteration on a single machine |
| **Local + HPC** | HPC home dir, optionally rsync'd back to laptop | `.secrets/hf_token` on HPC | Standard team workflow without Azure — runs on HPC, results pulled with `rsync` |
| **Local + HPC + Azure** | Azure Blob Storage in addition to local files | `.secrets/azure_connection_string` (laptop), `.secrets/azure_sas_token` (HPC), `.secrets/hf_token` | Default. Cross-machine sharing of results and logs via the dashboard's "Refresh from Azure" button |

**Two switches control whether Azure is involved:**

* `STORAGE_BACKEND=azure` (default) or `STORAGE_BACKEND=local` — read by
  the dashboard's I/O layer (`dashboard/azure_io.py`). When `local`, the
  dashboard reads `experiments/results/`, `scripts/slurm/logs/`, etc.
  straight from disk and never touches the Azure SDK. Set it via env
  var, or with `storage.backend: local` in `configs/local.yaml`.
* `AZURE_UPLOAD_DISABLED=1` — read by `scripts/slurm/_azure_upload.sh`
  on HPC. When set, SLURM jobs skip the post-job `azcopy sync` and
  results stay on HPC disk only. Pull them down with `rsync` (see
  [Contributing → Daily flow](#contributing)) when you want them on
  your laptop.

#### Mode A — Local only (no Azure, no HPC)

```sh
export STORAGE_BACKEND=local
# Run any script directly (see Running from terminal)
python -m src.evaluation.asr_eval model1
# Browse results
bash dashboard/start.sh             # http://localhost:8765
```

No `.secrets/azure_connection_string` is needed. The dashboard reads
files written by your local runs.

#### Mode B — Local + HPC, Azure off

On HPC:

```sh
export AZURE_UPLOAD_DISABLED=1      # add to ~/.bashrc to make persistent
sbatch scripts/slurm/textattack.slurm model1 eval
```

Pull results back to your laptop with `rsync` (the project root
mirrors the HPC checkout), then on the laptop:

```sh
export STORAGE_BACKEND=local
bash dashboard/start.sh
```

#### Mode C — Local + HPC + Azure (default)

Set up Azure credentials (full onboarding in `docs/azure-setup.md`),
then run as before — no env var to set:

* Each team member sets `export MEMBER=<name>` in their shell and on HPC.
* Credentials live under `.secrets/` (git-ignored):
  * Laptop: `.secrets/azure_connection_string` (full SDK auth)
  * HPC: `.secrets/azure_sas_token` (scoped SAS for `azcopy`)
  * HPC: `.secrets/hf_token`
* SLURM jobs auto-upload `scripts/slurm/logs/**` and
  `experiments/results/**` via `scripts/slurm/_azure_upload.sh`
  (sourced tail of every job; no-op if `azcopy` or the SAS token is
  missing).
* The dashboard reads blobs through `dashboard/azure_io.py`.

##### Azure smoke tests

```sh
# Laptop — round-trip via SDK
python dashboard/smoke_test.py      # minimal upload/list
python dashboard/smoke_e2e.py       # 7-stage end-to-end

# HPC — verify azcopy + SAS
sbatch scripts/slurm/poison.slurm simple validation   # cheap job; look for
                                                      # [azure-upload] lines in .out
```

##### Blob layout

See `docs/azure_path_overview.md` for the full mapping of local paths
(`scripts/slurm/logs/`, `experiments/results/`,
`experiments/submission/`, `data/processed/task1/`, selected
`docs/*.csv`) to Azure blob prefixes under `${MEMBER}/…`. `local_io.py`
mirrors that mapping in reverse, so a `STORAGE_BACKEND=local` dashboard
sees the same logical layout served from the filesystem.

### Running from terminal

Every workflow has a terminal entry point — there is no script that
*requires* the dashboard to run. The two patterns:

#### Direct CLI (laptop or HPC interactive shell)

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

# Poisoning (data prep)
python -m src.data.poisoning.poison_sst2_dpa simple validation

# Training-side defenses
python -m src.training.bert_backdoor_experiment
python -m src.training.bert_crow_defense
python -m src.training.adaptive_attacker
```

Standalone scripts under `scripts/` work the same way:

```sh
python scripts/eval_on_csv.py \
    --model_path ANTI-BAD-CHALLENGE/classification-track/models/task1/model1 \
    --input_path data/processed/task1/sst2_validation.csv \
    --output_dir experiments/results/asr/model1

python scripts/deep_trigger_scan.py
python scripts/zscore_ensemble.py
python scripts/extract_triggers.py
```

Pass `--help` to any of them for the full flag set:

```sh
python -m src.evaluation.eval --help
python scripts/eval_on_csv.py --help
```

#### SLURM (HPC batch jobs)

See [SLURM](#slurm) below for the full job catalog. The same `python -m`
invocations are wrapped by `.slurm` files, so a SLURM job is just a
batch-mode version of the direct CLI.

#### Where results land

Regardless of how you launch, results go to the same local paths:

* `experiments/results/{asr,input_reduction,untargeted,…}/<model>/` — per-attack outputs
* `experiments/submission/` — challenge submission CSVs
* `data/processed/task1/` — detection-pipeline intermediates
* `scripts/slurm/logs/` — SLURM `.out`/`.err` (only populated when run via SLURM)

If the optional Azure upload is enabled, the same trees are mirrored
to `${MEMBER}/<area>/…` in the `anti-bad` blob container.

### SLURM

All SLURM jobs live in `scripts/slurm/`. The main entry point is
`textattack.slurm`, a versatile script that takes `<model>` +
`<attack>` plus optional extra args forwarded via `$EXTRA_ARGS`.

#### Examples

```sh
# From the project root on HPC
sbatch scripts/slurm/textattack.slurm model1 eval
sbatch scripts/slurm/textattack.slurm model2 input_reduction
sbatch scripts/slurm/textattack.slurm model3 untargeted
sbatch scripts/slurm/textattack.slurm model1 asr

# Full Fase 3 detection pipeline (all 3 models × normal + challenge modes)
sbatch scripts/slurm/detection.slurm

# Apply gate-driven input sanitization
sbatch scripts/slurm/sanitize.slurm model1

# Cheap dataset poisoning job (used to verify azcopy upload path)
sbatch scripts/slurm/poison.slurm simple validation

# BERT comparison track (long jobs — drive scripts under src/training/)
sbatch scripts/slurm/bert_experiment.slurm
sbatch scripts/slurm/bert_crow_defense.slurm
sbatch scripts/slurm/bert_mlm_defense.slurm        # drives src/training/bert_mlm_defense_v2.py

# Validation-split defense sweep (prerequisite + sweeps)
sbatch scripts/slurm/gen_validation_csv.slurm
bash   scripts/slurm/submit_validation.sh          # surviving BERT + adapter defenses

# BERT auxiliary detectors (anomaly / auxiliary / strip)
sbatch scripts/slurm/bert_classifier.slurm anomaly model1
sbatch scripts/slurm/bert_classifier.slurm auxiliary model2
sbatch scripts/slurm/bert_classifier.slurm strip model3

# Per-model adapter defenses (all feed compile_results via eval_on_csv)
sbatch scripts/slurm/pruning_eval.slurm model1 30   # prune 30% then eval
sbatch scripts/slurm/int8_eval.slurm model2
sbatch scripts/slurm/wag_eval.slurm                 # merges model1+2+3 then eval

# Surviving input-side filters and trigger hunters
sbatch scripts/slurm/onion_mlm.slurm model1
sbatch scripts/slurm/logit_confidence.slurm
sbatch scripts/slurm/trigger_injection_eval.slurm
sbatch scripts/slurm/extract_triggers.slurm
```

> The Yoel-track scripts that didn't make the final pipeline
> (`flip_rate.slurm`, `tfidf_filter.slurm`, `keyword_filter*.slurm`,
> `trigger_removal.slurm`, `trigger_reversal.slurm`,
> `llama_crow_finetune.slurm`, plus the standalone `flip_rate_baseline.py`
> / `tfidf_filter_baseline.py` / `keyword_filter_*` /
> `trigger_removal_defense.py` / `llama_crow_finetune.py` companions)
> were moved to `_archive/` during the May 2026 lean-repo audit.
> Restore from there if you need them.

See `docs/integration_from_yoel.md` for the full catalogue and
recommended run order, and `docs/lean_repo_audit.md` for what was
archived.

#### Job-monitoring basics

```sh
# Is the job in the queue?
squeue -j <JOBID>

# Tail the output / error
tail -f scripts/slurm/logs/textattack_<JOBID>.out
tail -f scripts/slurm/logs/textattack_<JOBID>.err

# Why is this job pending?
squeue -u "$USER" -o "%.8i %.8T %.10r %.10M %.10L %.4C %.6m %R"
```

Logs are also mirrored to Azure under `${MEMBER}/logs/` *if* Azure is
enabled on HPC (i.e. `AZURE_UPLOAD_DISABLED` is unset and a SAS token
is present). Otherwise they stay under `scripts/slurm/logs/` only.

### Running the Streamlit / HTML dashboard

The dashboard renders results from whichever storage backend you point
it at. It is a *viewer*, not a launcher — every script it surfaces is
also runnable from the terminal (see [Running from terminal](#running-from-terminal)).

#### Start it

```sh
# Default backend = Azure. Reads from blobs under ${MEMBER}/… in the
# `anti-bad` container; needs .secrets/azure_connection_string.
bash dashboard/start.sh                         # http://localhost:8765
bash dashboard/start.sh --port 9000

# Local backend. Reads from experiments/results/, scripts/slurm/logs/,
# experiments/submission/, data/processed/task1/ on disk. No Azure
# credentials needed.
STORAGE_BACKEND=local bash dashboard/start.sh   # http://localhost:8765

# Streamlit mirror (read-only) — proxies the HTML dashboard's API
streamlit run dashboard/streamlit_app.py        # http://localhost:8501
```

The launcher probes `python3` → `python` → `py -3` so it works in Git
Bash on Windows (where only `python` is on PATH) as well as
macOS / Linux / HPC. The Streamlit mirror talks to the running HTML
dashboard on `:8765`, not to storage directly — so it inherits whatever
backend the HTML dashboard was launched with.

#### Pick a backend

Two equivalent ways to set the backend:

```sh
# Per-shell — overrides everything else
export STORAGE_BACKEND=local
bash dashboard/start.sh

# Persistent (per developer, gitignored)
# Edit configs/local.yaml and uncomment:
#   storage:
#     backend: local
```

You can confirm which backend is live with:

```sh
python dashboard/azure_io.py        # prints `backend : local` or `azure`
```

#### What you see in each backend

| Backend | Dashboard reads | Updates appear when |
|---------|-----------------|---------------------|
| `azure` | Blobs under `${MEMBER}/…` in the `anti-bad` container | A SLURM job finishes and `_azure_upload.sh` syncs (or you run an SDK upload) |
| `local` | Files under `experiments/results/`, `scripts/slurm/logs/`, `experiments/submission/`, `data/processed/task1/`, `docs/` | Any process — local Python, SLURM with `AZURE_UPLOAD_DISABLED=1`, or a manual `rsync` from HPC — writes those paths |

#### Refresh / cache

The HTML dashboard caches `/api/data` for snappy navigation; click
"Refresh from <backend>" in the header (or restart the server) to pick
up new files.

### Anti-BAD Defense Console (React dashboard)

A live monitoring dashboard purpose-built for the thesis defense and
sensor review. Runs separately from the Streamlit mirror — it has its
own FastAPI backend and a React/Vite frontend.

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
│   │   ├── index.css        # CSS custom properties (design tokens)
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
├── data/
│   ├── asr_results.json     # Defense results (edit this to update dashboard)
│   ├── jobs.json            # SLURM jobs
│   └── thesis_status.json   # Thesis progress
└── README.md
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
STORAGE_BACKEND=local     # (default) read from data/*.json
STORAGE_BACKEND=azure     # read from Azure Blob Storage

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

To pull the latest results from HPC:
```sh
rsync -avz aleksandar@10.10.15.10:~/project/experiments/results/ ./experiments/results/
# then run your bridge script to regenerate cortex-dashboard/data/asr_results.json
```

| Source | Location in thesis | Location in dashboard |
|--------|-------------------|----------------------|
| Baseline ASR per model | Table 5.1 | `baseline_per_model` in `asr_results.json` |
| Defense ASR/CACC | Table 5.2 | `defenses[]` in `asr_results.json` |
| TF-IDF detection rate | Section 5.x | `note` field on TF-IDF defense entry |
| Wilson CI / Cohen's h | Appendix / Table | `wilson_ci`, `cohens_h` fields |

#### Design system

Colors are defined as CSS custom properties in
`cortex-dashboard/frontend-react/src/index.css`:

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
| `scripts/` | Standalone analysis / orchestration scripts and `slurm/` job dispatchers |
| `experiments/` | All run outputs (results, submissions, charts, audits — Aleksandar drop merged in) |
| `dashboard/` | HTML + Streamlit dashboard — reads from Azure Blob *or* local disk depending on [`STORAGE_BACKEND`](#storage-modes-local-hpc-azure) |
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
│   │   ├── sanitize_inputs.py   # gate-driven input masking CLI
│   │   └── attacks/             # input_reduction.py, untargeted.py (textfooler)
│   └── training/                # BERT/Llama defense + adaptive-attack experiments
│       ├── adaptive_attacker.py
│       ├── bert_backdoor_experiment.py
│       ├── bert_crow_defense.py
│       ├── bert_mlm_defense_v2.py
│       ├── bert_strip_defense.py
│       └── onion_mlm_defense.py
├── configs/                     # attack.yaml, detection.yaml, paths.yaml,
│                                  poisoning.yaml, poisoning_validation.yaml,
│                                  sentiment_swap.json, local.yaml.example
│                                  (+ gitignored per-person local.yaml)
├── experiments/                 # All run outputs (Alex drop merged in)
│   ├── results/
│   │   ├── asr/model{1,2,3}/             # asr_cacc_results.txt
│   │   ├── input_reduction/model{1,2,3}/ # *_results.csv + *_output.txt
│   │   ├── untargeted/model{1,2,3}/      # *_results.csv + *_output.txt
│   │   ├── adaptive_attacker/            # adaptive_attacker_report.md + .json
│   │   ├── bert/                         # poisoned_{1,2}/, clean/, results.json
│   │   ├── bert_crow_defense/            # CROW-on-BERT failure evidence
│   │   ├── bert_mlm_defense/             # BERT-MLM detection results
│   │   └── general/                      # results_summary.{csv,txt},
│   │                                       detection_summary.csv,
│   │                                       pruning_results.{csv,txt},
│   │                                       gate_eval_model{1,2,3}{,_challenge}.txt,
│   │                                       contamination_report.{txt,json}
│   ├── submission/              # Challenge submission CSVs (cls_task1*.csv)
│   ├── advanced_attacks/        # confidence / NTA / position analyses (json + md)
│   ├── attack_chain/            # multi-step attack-chain experiments
│   ├── attack_scenarios/        # attack_report.md + scenario_log.txt
│   ├── audit/                   # per-model audit snapshots
│   ├── charts/                  # accuracy-vs-ASR, confidence shift, heatmaps (png)
│   ├── deep_analysis/           # MASTER_SUMMARY.md, cross_model_consistency, target_label_investigation
│   ├── defensebox/              # defense_{baseline,pruning,quantization}_task1.json
│   ├── extended_scans/          # extended_summary.md + JSONs
│   ├── extra_exploits/          # cross-task, defense-evasion, stacking writeups
│   ├── live_exploit/            # live exploit artefacts
│   ├── model3_discovery/        # model3-specific trigger discovery
│   ├── overnight_battery/       # battery_summary.md
│   ├── overnight_full/          # summary.md
│   ├── presentation/            # presentation_exploits.md
│   ├── system_takeover/         # system-takeover exploit writeup
│   ├── textattack_checkpoints/  # TextAttack checkpoints
│   └── wanda_crow/              # Wanda sparsity sweep (10/20/…/80%) + CROW JSONs
├── scripts/                     # Standalone analysis / orchestration scripts
│   ├── attack_scenarios.py
│   ├── bert_anomaly_detection.py    # Isolation Forest + Mahalanobis on CLS embeds
│   ├── bert_auxiliary_classifier.py # "poisoned vs clean" BERT gate
│   ├── classification_track_predict.py
│   ├── deep_trigger_scan.py
│   ├── download_resources.py
│   ├── eval_on_csv.py               # generic LoRA eval harness (pruning/int8/wag)
│   ├── eval_sst2_utility.py
│   ├── extract_triggers.py
│   ├── logit_confidence_analysis.py
│   ├── model3_trigger_scan.py
│   ├── overnight_battery.py
│   ├── overnight_extended_scans.py
│   ├── overnight_full_eval.py
│   ├── plot_trigger_proxy_results.py
│   ├── run_ir_patched2.py
│   ├── run_textattack_patched.py
│   ├── summarize_eval.py
│   ├── textattack_input_reduction.py
│   ├── trigger_injection_eval.py
│   ├── trigger_proxy_test.py
│   ├── zscore_ensemble.py
│   └── slurm/                       # SLURM job dispatchers + helper shells
│       ├── textattack.slurm             # versatile: <model> <attack> + extra args
│       ├── textattack_run.sbatch        # alternate sbatch entry
│       ├── detection.slurm              # full Fase 3 pipeline
│       ├── poison.slurm                 # poisoning pipeline
│       ├── sanitize.slurm               # input sanitization via evaluation/sanitize_inputs
│       ├── deep_trigger_scan.slurm
│       ├── zscore_ensemble.slurm
│       ├── adaptive_attacker.slurm
│       ├── bert_experiment.slurm
│       ├── bert_crow_defense.slurm
│       ├── bert_mlm_defense.slurm
│       ├── bert_classifier.slurm        # dispatches anomaly/auxiliary/strip BERT detectors
│       ├── onion_mlm.slurm
│       ├── logit_confidence.slurm
│       ├── trigger_injection_eval.slurm
│       ├── model3_trigger_scan.slurm
│       ├── extract_triggers.slurm
│       ├── gen_validation_csv.slurm     # regenerates sst2_validation_poisoned.csv
│       ├── pruning_eval.slurm           # prune via pruning.py then eval_on_csv
│       ├── int8_eval.slurm              # INT8 quant + eval_on_csv
│       ├── wag_eval.slurm               # WAG merge + eval_on_csv
│       ├── submit_validation.sh         # bash dispatcher for the validation-split sweep
│       ├── run_eval_all.sh              # bulk eval helper
│       ├── run_proxy_task1.sh           # trigger-proxy dispatcher (task1)
│       ├── run_proxy_task2.sh           # trigger-proxy dispatcher (task2)
│       ├── _azure_upload.sh             # sourced tail of every job
│       └── logs/                        # .out / .err (also mirrored to Azure when enabled)
├── tests/                       # test_env.py + future un