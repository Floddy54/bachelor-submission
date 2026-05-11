# Reproduction Appendix — SLURM Pipeline (Documentation Only)

Per supervisor guidance the executable SLURM scripts are excluded from
this submission bundle. This appendix gives the external reviewer full
visibility into what those scripts did and what they produced, so the
results in `data/asr_results.json` can be traced back to specific
compute jobs.

The sensor does **not** need to run any of these scripts to evaluate
the work — the published numbers are deterministic given seed 42 and
the dashboard renders them directly.

---

## 1. Pipeline overview

Each defense in the thesis is produced by one SLURM job. The pipeline is:

```
data/triggers.json        scripts/<defense>.py        data/asr_results.json
data/eval/sst2_399.csv   ───────────────────▶   .out / .err logs   ───────────▶
poisoned LoRA adapter    (run on GPU node)         experiments/results/<defense>/
```

| SLURM job                    | Python entry point             | What it produces                                |
|------------------------------|--------------------------------|-------------------------------------------------|
| `bert_mlm_defense.slurm`     | `bert_mlm_defense_v2.py`       | Per-token MLM logprobs, trigger decisions       |
| `bert_crow_defense.slurm`    | `bert_crow_defense.py`         | CROW consistency scores                         |
| `wag_eval.slurm`             | `wag_merge_eval.py`            | Weight-averaged gradient merged model ASR       |
| `int8_eval.slurm`            | `int8_quantize_eval.py`        | INT8 quantized inference ASR (Phase B)          |
| `antibad_full_eval.slurm`    | `classification_track_predict` | End-to-end submission CSV (n=400 / n=872)       |
| `pruning_eval.slurm`         | `pruning_sweep.py`             | Pruning sweep across rates [0.1 … 0.9]          |
| `adaptive_attacker.slurm`    | `adaptive_attacker_eval.py`    | Robustness against an attacker who knows TF-IDF |

Per-job hardware allocation is uniform: 1 H200 GPU, 4 CPU, 24 GB RAM,
2 h wall-clock. See `SUBMISSION.md` § *Compute environment*.

---

## 2. Representative SLURM template (sanitized)

This is the structure of every SLURM job in the pipeline. Site-specific
paths (`/cluster/home/<user>/…`) have been removed; the `$PROJECT_ROOT`
auto-discovery pattern lets the same script run from any checkout.

```bash
#!/bin/bash -l
#SBATCH --job-name=bert_mlm_defense
#SBATCH --output=scripts/slurm/logs/bert_mlm_defense_%j.out
#SBATCH --error=scripts/slurm/logs/bert_mlm_defense_%j.err
#SBATCH --time=02:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --gres=gpu:1
#SBATCH --partition=<your-gpu-partition>

# Auto-derive project root from script location — no hard-coded user
# paths so the same script runs on any cluster checkout.
PROJECT_ROOT="${SLURM_SUBMIT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." \
  &>/dev/null && pwd)}"
cd "$PROJECT_ROOT"

# Hugging Face token loaded from local secret file (not committed).
TOKEN_FILE="$PROJECT_ROOT/.secrets/hf_token"
[[ -f "$TOKEN_FILE" ]] && export HF_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"

export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

module load CUDA/12.8.0
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate bachelorenv

mkdir -p experiments/results/bert_mlm_defense
OUT=experiments/results/bert_mlm_defense

echo "============================================"
echo "  BERT-MLM Defense"
echo "  Start: $(date)"
echo "============================================"
nvidia-smi || true

python scripts/bert_mlm_defense_v2.py --output-dir "$OUT"

echo "============================================"
echo "  Done: $(date)"
echo "============================================"
```

### What the template guarantees

| Property            | Mechanism                                            |
|---------------------|------------------------------------------------------|
| No hard-coded paths | `$SLURM_SUBMIT_DIR` / `BASH_SOURCE` auto-discovery   |
| Reproducible env    | `module load CUDA/12.8.0` + `conda activate` pinned  |
| Per-job logs        | `--output` / `--error` named with `%j` (job ID)      |
| Secret hygiene      | Tokens read from `.secrets/`, never embedded         |
| Result location     | `experiments/results/<defense>/` (one dir per job)   |

---

## 3. Representative log excerpt (sanitized)

The job `antibad-cls1-846` ran the end-to-end Task 1 prediction. Real
stdout, trimmed to milestones and with user-specific paths replaced by
`<PROJECT_ROOT>`. Full raw logs (158 files) are retained in our HPC
home directory and available on request.

```
==========================================
Classification Track - Prediction
==========================================
Task: 1
Model: model1
Input: ./data/task1/test.json
Output: ../submission/cls_task1.csv
==========================================

============================================================
Prediction Configuration
============================================================
Model: ./models/task1/model1
Input: ./data/task1/test.json
Output: <PROJECT_ROOT>/ANTI-BAD-CHALLENGE/submission/cls_task1.csv
Batch size: 4
============================================================

Loaded 400 test samples
============================================================
Loading Model
============================================================
Base model: meta-llama/Llama-3.1-8B
LoRA adapter: ./models/task1/model1
Detecting num_labels from adapter weights...
Number of labels detected: 2
Quantization: 4-bit (NF4)
Loading base model...
Model loaded successfully!
============================================================
Predicting: 100%|██████████| 100/100 [00:07<00:00, 12.64it/s]
Saved 400 predictions to <PROJECT_ROOT>/ANTI-BAD-CHALLENGE/submission/cls_task1.csv
Prediction completed!
Results saved to: ../submission/cls_task1.csv
```

### What this log demonstrates

1. **Deterministic configuration** — every run records `Model`, `Input`,
   `Batch size`, `Number of labels`, `Quantization` before inference.
2. **Repeatable wallclock** — 400 samples / 100 batches in ~7 seconds
   on one H200 GPU. The sensor can compare against their own GPU.
3. **Tracked output** — predictions saved to a deterministic CSV path
   that becomes the input to the next stage of the pipeline.
4. **No silent failures** — log ends with explicit `Prediction
   completed!` confirmation.

---

## 4. Where the results live in this submission

Even with all SLURM scripts excluded, the sensor has access to:

| Artifact                          | Location in submission                         |
|-----------------------------------|------------------------------------------------|
| Final per-defense ASR / CACC      | `data/asr_results.json`                        |
| Per-defense run history (audit)   | `data/runs_history.json` (git-ignored, but generated by `python scripts/run_defense.py all` locally) |
| Wilson CI / Cohen's h / McNemar   | `data/statistics.json` (computed from `asr_results.json`) |
| Sample inputs (Phase A reproduce) | `data/sample_inputs.csv` (20 labeled rows)     |
| Trigger token list                | `data/triggers.json`                           |
| MITRE ATLAS mapping               | `data/mitre_atlas_mapping.yaml`                |
| This appendix                     | `docs/slurm_appendix.md`                       |

All numbers shown in the dashboard (Overview, Statistics, Token Scan)
are read from `data/asr_results.json`. No backend computation is
required at view time.

---

## 5. If the sensor wants to re-run anything

See `SUBMISSION.md` § *Reproduction paths*. Three tiers are supported:

- **Path 1** — No compute (read-only review of dashboard + JSON)
- **Path 2** — CPU only (Phase A: gate logic, deterministic)
- **Path 3** — Any GPU host (Phase B: LoRA inference; works on H100 / A100 / RTX 4090 with ≥16 GB VRAM, not just our HPC)

The dashboard's *Settings* tab switches `compute_backend` between
`local`, `hpc`, and `cloud` at runtime — no code edits required.
