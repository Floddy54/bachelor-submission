# Anti-BAD Defense Console — Submission Notes

For the external sensor and anyone reproducing the project without access
to our specific Kristiania HPC cluster.

## Scope

This submission targets the **Anti-BAD Challenge — IEEE SaTML 2026,
Classification Track, Task 1** (Codabench #11188): post-training defenses
against backdoors in a Llama-3.1-8B base + LoRA adapters, evaluated on
SST-2.

**Task 2** of the same track (Qwen2.5-7B base, n=400 input-only test
samples) is **future work** and is not covered by this thesis. The
defense methodology (TF-IDF gate, BERT-MLM lenient, WAG, CROW) is
backbone-agnostic and should transfer, but Task 2 numbers, statistical
tests, and adaptive-attacker analysis are out of scope here.

## Supervisor guidance (Guru, 2026-05)

> "No, you don't need to worry about how he reproduces it. He may use
>  another HPC or cloud or standalone system, or anything. It's up to
>  him. You just exclude the HPC related slurm scripts there in the
>  submission version. However, in the report you can mention the system
>  that you used in your project, say HPC and its specs, in the
>  experimental setup section."

The submission bundle therefore:
- Excludes `scripts/slurm/*.slurm` and all Kristiania-specific orchestration
- Excludes `configs/local.yaml` (per-developer SSH credentials)
- Defaults to `compute_backend: "local"` so the sensor's first-run experience
  works on any laptop without HPC, cloud or GPU
- Documents the actual hardware we used (Kristiania HPC HGXQ, NVIDIA H200 SXM)
  in the report's Experimental Setup section, NOT inside the dashboard chrome
- Renames the user-facing tab from "HPC Jobs" to just "Jobs" so the dashboard
  is environment-agnostic for the sensor

## Compute requirement matrix

The thesis evaluates 5 defenses. Each defense has two reproduction phases:

| Phase | What it covers                          | Compute required        | Time   |
|-------|-----------------------------------------|-------------------------|--------|
| A     | Trigger detection + gate decisions      | CPU only, no GPU        | seconds |
| B     | LoRA adapter inference (8B parameters)  | One GPU, ~16 GB VRAM    | minutes per defense |

| Defense              | Phase A reproducible | Phase B reproducible |
|----------------------|----------------------|----------------------|
| TF-IDF gate          | yes, on CPU          | n/a (gate is pure CPU) |
| BERT-MLM (lenient)   | yes, on CPU          | requires GPU         |
| WAG (merged)         | n/a                  | requires GPU         |
| CROW                 | n/a                  | requires GPU         |
| INT8 quantization    | n/a                  | requires GPU         |

The dashboard renders the published thesis numbers (data/asr_results.json)
for all defenses regardless of what compute the sensor has. The sensor can
re-run Phase A locally to verify the gate-logic numbers are deterministic.

## Reproduction paths

### Path 1 — No compute at all (read-only sensor review)

Works on any laptop. No HPC, no GPU, no cloud.

```bash
git clone <repo>
cd cortex-dashboard

# Backend
pip install -r backend/requirements.txt
python backend/server.py

# Frontend (separate terminal)
cd frontend-react
npm install
npm run dev
```

Open http://localhost:5173. The dashboard displays the full thesis results
from data/asr_results.json. Every tab works:

- Overview, Statistics, Token Scan, Threat Intel, Assets, Incidents, Activity
- Hunt tab (paste arbitrary text, runs TF-IDF + BERT-MLM on CPU)
- Hunt tab Batch upload (drop a CSV, gate every row on CPU)
- Compare modal, Executive Report PDF export

What does NOT work in this mode:
- HPC Jobs tab shows mock data (clearly labelled as "mock")
- GPU utilisation panel shows "HPC SSH unreachable"
- Launching new SLURM jobs is disabled

Integration Health tab makes all of this explicit; the sensor can see at
a glance what is live vs. fallback.

### Path 2 — CPU reproduction of Phase A (verifying the gate)

To verify that the trigger detection / gate-decision numbers in the thesis
are deterministic and reproducible, run the local runner:

```bash
# Run TF-IDF gate against the included 20-sentence sample
python scripts/run_defense.py tfidf

# Run BERT-MLM lenient gate against your own labelled CSV
python scripts/run_defense.py bert_mlm --input my_data.csv --output runs/

# Run all 5 defenses (Phase A live, Phase B replayed from thesis)
python scripts/run_defense.py all --output runs/
```

CSV format expected: two columns, text and label (1 = poisoned, 0 = clean).

The script emits JSON the dashboard automatically picks up if `compute_backend`
is set to "local" in Settings.

### Path 3 — Full reproduction including Phase B (any GPU host)

Phase B requires loading the poisoned LoRA adapter on a GPU. We used
NVIDIA H200 SXM on our HPC, but Phase B reproduces on:

- A single A100 / H100 / RTX 4090 with ~16 GB free VRAM
- AWS EC2 p4d or g5.xlarge
- Any HPC with SLURM / PBS / Kubernetes

The dashboard does not bind to any one of these. Set `compute_backend` to
your scheduler of choice (or "local" if you have a GPU machine):

```yaml
# configs/local.yaml
ssh:
  host: your-cluster.example.com
  user: your-username
  remote_root: /home/your-username/anti-bad

cluster:
  name:           "Your HPC"
  partition:      "gpu-queue"
  gpu:            "NVIDIA A100"
  gpu_count:      1
  memory_per_job: "40 GB"
  time_limit:     "2h"
  scheduler:      "slurm"
```

## What is NOT in the submission bundle

These files are present in our development repo but excluded from the
sensor-facing submission:

- `scripts/slurm/*.slurm` — Kristiania-specific SLURM batch scripts
- `configs/local.yaml` — per-developer SSH credentials (gitignored)
- `.secrets/` — Azure / HuggingFace tokens (gitignored)
- `ckpts/`, `*.safetensors`, `*.pth` — model weights (large binaries)
- `data/runs_history.json` — per-machine runtime log
- `data/runs/` — per-defense output JSONs

None of these are required for the dashboard or for Phase A reproduction.

For full visibility into what the excluded SLURM scripts did and what
they produced when run, see **[`docs/slurm_appendix.md`](docs/slurm_appendix.md)**.
That appendix documents:
- The pipeline overview (which job produces which result)
- A representative sanitized SLURM template (the structure every job uses)
- A representative sanitized log excerpt (real stdout from one run)
- Where each excluded artifact's final result is stored inside the bundle

## Compute environment used in our experiments

For the thesis "Experimental Setup" section, the actual hardware used was:

| Resource       | Value                                          |
|----------------|------------------------------------------------|
| Cluster        | Kristiania University HPC                      |
| Partition      | HGXQ                                           |
| GPU            | NVIDIA H200 SXM x 8 (141 GB HBM3e per GPU)     |
| Memory per job | 80 GB                                          |
| Time limit     | 4 h                                            |
| Random seed    | 42 (fixed)                                     |
| Dataset        | SST-2, n=399 local CSV / n=872 benchmark val   |

The sensor does NOT need to match this hardware. Reproducibility is
guaranteed by:

1. Fixed seed (42) recorded in every result file
2. Deterministic gate logic (Phase A reproducible byte-for-byte on CPU)
3. Published thesis numbers in data/asr_results.json
4. Open-source LoRA adapters available on request (not bundled — 80 MB each)

## Default behaviour

The dashboard ships with `compute_backend: "local"` so the first-run
experience for any reviewer is: clone, install, open browser, everything
works. Switching to HPC mode is a one-line change in Settings (no code
edit required).
