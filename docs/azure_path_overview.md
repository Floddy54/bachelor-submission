# Azure path overview — bachelor-anti-bad

*Audit of every output path the project writes, and whether it reaches Azure
Blob Storage. Read-only overview — no code changes here.*

*Generated 2026-04-21. Last updated **2026-05-07** to reflect the May 2026
lean-repo audit (nine archived SLURM scripts + Python companions; defense
scripts moved from `scripts/` to `src/training/`). Previous edits: 2026-04-22
(Yoel integration, +17 SLURM files), 2026-04-21 (initial audit). Container:
`anti-bad` @ `antibadahvy` (Norway East). Member prefix: `${MEMBER}/`.*

---

## 1. The canonical mapping

The single source of truth for what gets uploaded is
`scripts/slurm/_azure_upload.sh`. It is sourced by every `.slurm` file and
registers an `EXIT` trap so outputs land in Azure even when the Python step
fails.

| Local path (under `PROJECT_ROOT`) | Azure blob prefix (under `${MEMBER}/`) | How uploaded |
|---|---|---|
| `scripts/slurm/logs/` | `logs/` | `azcopy sync` (recursive) |
| `experiments/results/` | `results/` | `azcopy sync` (recursive) |
| `experiments/submission/` | `submission/` | `azcopy sync` (recursive) |
| `data/processed/task1/` | `data/processed/task1/` | `azcopy sync` (recursive) |
| `docs/results_summary.csv` (no-op²) | `docs/results_summary.csv` | `azcopy copy` (file) |
| `docs/results_summary.txt` | `docs/results_summary.txt` | `azcopy copy` (file) |
| `docs/detection_summary.csv` (no-op²) | `docs/detection_summary.csv` | `azcopy copy` (file) |
| `docs/pruning_results.csv` (no-op²) | `docs/pruning_results.csv` | `azcopy copy` (file) |
| `docs/gate_eval_model*.txt` (no-op²) | `docs/<basename>` | `azcopy copy` (per file) |

`azcopy sync` is idempotent and skips unchanged blobs, so re-runs are cheap.
The trap preserves the Python step's exit code, so upload hiccups never mark
a job `COMPLETED` when it actually failed.

> ² **Path drift, 2026-05-07.** `compile_results.py` now writes the four
> CSV/TXT files to `experiments/results/general/` (not `docs/`), and the
> detection pipeline writes `gate_eval_model*.txt` to the same directory.
> The upload helper's per-file lines for `docs/results_summary.csv`,
> `docs/detection_summary.csv`, `docs/pruning_results.csv`, and the
> `docs/gate_eval_model*.txt` glob therefore no-op on the file-not-found
> guard inside `_azup_file`. The data still reaches Azure via the recursive
> `experiments/results/` sync (one row above), so nothing is lost — but
> the explicit `docs/` lines should either be removed or updated to point
> at `experiments/results/general/` to keep the helper honest.

---

## 2. SLURM coverage — every job uploads

Every `.slurm` file in `scripts/slurm/` sources the upload helper. All **20
active** jobs route both their `.out` / `.err` to `scripts/slurm/logs/<name>_%j.{out,err}`
and (via the helper's `EXIT` trap) push logs + results to Azure. One extra
dispatcher (`submit_validation.sh`) is a plain bash script that just `sbatch`-es
the jobs below and is covered indirectly. Three more shell helpers
(`run_eval_all.sh`, `run_proxy_task1.sh`, `run_proxy_task2.sh`) are similar
indirection points.

| SLURM script | Writes results into | Uploaded? |
|---|---|---|
| `adaptive_attacker.slurm` | `experiments/results/adaptive_attacker/` | ✅ under `results/` |
| `bert_classifier.slurm` | `experiments/results/bert_classifier/{anomaly,auxiliary,strip}/` | ✅ under `results/` |
| `bert_crow_defense.slurm` | `experiments/results/bert_crow_defense/` | ✅ under `results/` |
| `bert_experiment.slurm` | `experiments/results/bert/` | ✅ under `results/` |
| `bert_mlm_defense.slurm` | `experiments/results/bert_mlm_defense/` | ✅ under `results/` |
| `deep_trigger_scan.slurm` | `experiments/results/deep_trigger_scan.{csv,md}` | ✅ under `results/` |
| `detection.slurm` | `data/processed/task1/` + `experiments/results/general/gate_eval_model*.txt` | ✅ under `data/processed/task1/` + `results/` |
| `extract_triggers.slurm` | `experiments/results/trigger_extraction/` | ✅ under `results/` |
| `gen_validation_csv.slurm` | `data/processed/task1/sst2_validation_poisoned.csv` | ✅ under `data/processed/task1/` |
| `int8_eval.slurm` | `experiments/results/int8/` | ✅ under `results/` |
| `logit_confidence.slurm` | `experiments/results/logit_confidence/` | ✅ under `results/` |
| `model3_trigger_scan.slurm` | `experiments/results/model3_trigger_scan/` | ✅ under `results/` |
| `onion_mlm.slurm` | `experiments/results/onion_mlm/` | ✅ under `results/` |
| `poison.slurm` | `data/raw/poisoned/…` (see §4 for gap) | ⚠️ partial — see gap |
| `pruning_eval.slurm` | `experiments/results/pruning/` (+ `models/task1/<model>_pruned_<ratio>/`) | ✅ under `results/` |
| `sanitize.slurm` | `data/processed/task1/sanitized_<model>_<strategy>.csv` | ✅ under `data/processed/task1/` |
| `textattack.slurm` | `experiments/results/{asr,input_reduction,untargeted}/<model>/` | ✅ under `results/` |
| `trigger_injection_eval.slurm` | `experiments/results/trigger_injection/` | ✅ under `results/` |
| `wag_eval.slurm` | `experiments/results/wag/` (+ `experiments/models/wag_merged/`) | ✅ under `results/` |
| `zscore_ensemble.slurm` | `experiments/results/task<task>_zscore.{csv,md,png}` | ✅ under `results/` |

All 20 SBATCH headers use `#SBATCH --output=scripts/slurm/logs/<name>_%j.out`
(and `.err`) — consistent with `_azup_dir "$PROJECT_ROOT/scripts/slurm/logs"`.

### Archived during the May 2026 lean-repo audit

The following nine SLURM scripts (and their Python companions) were moved
to `_archive/scripts/slurm/`. They still source the same `_azure_upload.sh`
helper, so if you restore one from the archive nothing in this audit
changes. Listed for traceability against earlier versions of this file:

| Archived SLURM script | Was writing to | Companion archived |
|---|---|---|
| `flip_rate.slurm` | `experiments/results/flip_rate/` | `flip_rate_baseline.py` |
| `tfidf_filter.slurm` | `experiments/results/tfidf_filter/` | `tfidf_filter_baseline.py` |
| `keyword_filter.slurm` | `experiments/results/keyword_filter/` | `keyword_filter_defense.py` |
| `keyword_filter_injection_eval.slurm` | `experiments/results/keyword_filter_injection/` | `keyword_filter_injection_eval.py` |
| `trigger_removal.slurm` | `experiments/results/trigger_removal/` | `trigger_removal_defense.py` |
| `trigger_reversal.slurm` | `experiments/results/trigger_removal/` | (shared with above) |
| `llama_crow_finetune.slurm` | `experiments/results/llama_crow/` | `llama_crow_finetune.py` |
| `eval_sst2_utility.slurm` | `experiments/results/sst2_task1_utility.csv` | `eval_sst2_utility.py` |
| `overnight_full_eval.slurm` | `experiments/results/overnight_full/` | `overnight_full_eval.py` |

---

## 3. Python scripts — where each one writes

Writes that go to a path the helper uploads:

- `src/evaluation/compile_results.py` → `docs/results_summary.{csv,txt}`, `docs/detection_summary.csv` (listed in the helper's file-by-file `for` loop) ✅
- `src/data/poisoning/poison_sst2_dpa.py` → writes `OUTPUT_CSV` and `OUTPUT_STATS` into `data/raw/poisoned/` (NOT uploaded — see §4)
- `src/data/poisoning/poison_sst2_simple.py` → same dir, same gap
- `src/data/poisoning/contamination_analysis.py` → `docs/contamination_report.{txt,json}` (NOT in the helper's `for` loop — see §4)
- `src/data/sanitization/extract_clean_control.py` → `data/processed/task1/clean_control.json` ✅
- `src/data/detection/candidate_token_mining.py` → `data/processed/task1/candidate_tokens.json` ✅
- `src/data/detection/flip_rate_analysis.py` → `data/processed/task1/` (flip-rate json) ✅
- `src/data/detection/zscore_detector.py` → `data/processed/task1/flagged_tokens_<model>.json` + a per-model report ✅
- `src/data/detection/run_detection.py` → `docs/gate_eval_model*.txt` ✅ (helper globs these)
- `src/defense/sanitize_inputs.py` → `data/processed/task1/sanitized_<model>_<strategy>.csv` ✅
- `src/evaluation/asr_eval.py` / `eval.py` / `attacks/untargeted.py` → `experiments/results/…` (via `results_dir()` in `src/config.py`) ✅
- `src/reporting/{zscore_ensemble, overnight_full_eval, deep_trigger_scan, eval_sst2_utility, attack_scenarios}.py` → all write under `experiments/results/…` ✅

Yoel-integration batch (2026-04-22, refactored May 2026) — paths updated
to reflect the lean-repo audit. Active scripts route to `experiments/results/…`
or `data/processed/task1/` via their matching SLURM wrapper:

- `scripts/bert_anomaly_detection.py` → `experiments/results/bert_classifier/anomaly/` ✅
- `scripts/bert_auxiliary_classifier.py` → `experiments/results/bert_classifier/auxiliary/` ✅
- `src/training/bert_strip_defense.py` (moved from `scripts/`) → `experiments/results/bert_classifier/strip/` ✅
- `src/training/onion_mlm_defense.py` (moved from `scripts/`) → `experiments/results/onion_mlm/` ✅
- `scripts/trigger_injection_eval.py` → `experiments/results/trigger_injection/` ✅
- `scripts/logit_confidence_analysis.py` → `experiments/results/logit_confidence/` ✅
- `scripts/extract_triggers.py` → `experiments/results/trigger_extraction/` ✅
- `scripts/model3_trigger_scan.py` → `experiments/results/model3_trigger_scan/` ✅
- `scripts/eval_on_csv.py` → stdout + JSON under the caller's `--output-dir` (used by `pruning_eval.slurm`, `int8_eval.slurm`, `wag_eval.slurm`) ✅ (inherits whichever `experiments/results/…` folder the caller specifies)
- `scripts/submit_validation.sh` → no file outputs; it only `sbatch`-es the scripts above and is covered indirectly.

Archived (May 2026 lean-repo audit). Listed for completeness; restore from
`_archive/scripts/` if you need them:

- `_archive/scripts/flip_rate_baseline.py` (was `experiments/results/flip_rate/`)
- `_archive/scripts/tfidf_filter_baseline.py` (was `experiments/results/tfidf_filter/`)
- `_archive/scripts/keyword_filter_defense.py` (was `experiments/results/keyword_filter/`)
- `_archive/scripts/keyword_filter_injection_eval.py` (was `experiments/results/keyword_filter_injection/`)
- `_archive/scripts/trigger_removal_defense.py` (was `experiments/results/trigger_removal/`, also covered reversal variants)
- `_archive/scripts/llama_crow_finetune.py` (was `experiments/results/llama_crow/`)
- `_archive/src/reporting/eval_sst2_utility.py` (was `experiments/results/sst2_task1_utility.csv`)
- `_archive/src/reporting/overnight_full_eval.py` (was `experiments/results/overnight_full/`)
- `_archive/scripts/full_validation.py` — reproducibility sanity check; printed a diff, no new artefacts.
- `_archive/scripts/migrate_azure_prefixes.py`, `_archive/scripts/migrate_aleksandar_legacy.py` — server-side blob renames; wrote nothing locally.
- `_archive/scripts/create_submission.sh` — had a `cd submission` bug from `PROJECT_ROOT`; never reused after the post-submission cleanup.

Scripts where the **CLI default** writes somewhere the helper ignores, but
the SLURM wrapper redirects correctly via `--output-dir`:

- `src/training/bert_backdoor_experiment.py` default `results/bert` → SLURM overrides to `experiments/results/bert` ✅
- `src/training/bert_crow_defense.py` default `results/bert_crow_defense` → SLURM overrides ✅
- `src/training/bert_mlm_defense_v2.py` default `results/bert_mlm_defense` → SLURM sets `OUT=experiments/results/bert_mlm_defense` ✅
- `src/training/adaptive_attacker.py` default `reporting/adaptive_attacker` → SLURM overrides to `experiments/results/adaptive_attacker` ✅
- Yoel's surviving batch (`bert_anomaly_detection.py`, `bert_auxiliary_classifier.py`, `trigger_injection_eval.py`, `logit_confidence_analysis.py`, `extract_triggers.py`, `model3_trigger_scan.py`) all honour `--output-dir` from the SLURM wrapper → same pattern ✅

⚠️ These defaults are a foot-gun if anyone runs the scripts **outside** the
SLURM wrapper (e.g. a quick interactive test on the login node) — outputs
land in a top-level `results/` or `reporting/` dir that nothing uploads.
Not blocking; just worth knowing.

---

## 4. Gaps — files written locally that do NOT reach Azure

| Local path | Produced by | Status |
|---|---|---|
| `docs/contamination_report.txt` | `contamination_analysis.py` | ❌ not in helper's file list. Fix: add `contamination_report.txt` to the `for f in …` loop, or drop it into the `docs/gate_eval_*` glob pattern. |
| `docs/contamination_report.json` | `contamination_analysis.py` | ❌ same as above. |
| `docs/pruning_results.txt` | `compile_results.py` | ❌ sibling `pruning_results.csv` IS uploaded — either add the `.txt` for symmetry or stop writing it. |
| `data/raw/poisoned/sst2_*_poisoned*.csv` | `poison_sst2_{simple,dpa}.py` | ❌ large, deterministic output — likely intentional to keep out of Azure; flag if any downstream job depends on the artefact being retrievable. |
| `data/raw/poisoned/sst2_*_poisoned_dpa_stats.json` | `poison_sst2_dpa.py` | ❌ small; reproducible alongside the CSV, so minor. |
| `data/external/sst2/sst2_validation.csv` | `overnight_full_eval.slurm`, `eval_sst2_utility.slurm` | ❌ downloadable from HF; intentional to skip. |

None of the above block the dashboard reading results today, but they are
the only loose ends between "on HPC disk" and "in Azure".

---

## 5. Outstanding 2026-04-21 backfill rename

Memory flags that the 04-21 backfill landed blobs under the wrong top-level
prefixes. The dashboard's `azure_io.py` + the (archived) `migrate_azure_prefixes.py`
document the intended shape. Status of each old prefix:

| Old blob prefix (under `<member>/`) | Correct prefix | Handled by |
|---|---|---|
| `experiments/results/` | `results/` | `_archive/scripts/migrate_azure_prefixes.py` default mapping |
| `experiments/submission/` | `submission/` | `_archive/scripts/migrate_azure_prefixes.py` default mapping |
| `slurm_jobs/logs/` | `logs/` | `_archive/scripts/migrate_azure_prefixes.py` default mapping (note: source is `slurm_jobs/logs/`, not `slurm_jobs/` — azcopy preserved the `logs` leaf on upload) |

How to run the rename (copy-then-delete, server-side; no bytes through the
laptop) — restore the script from `_archive/` first, since it was moved
during the May 2026 lean-repo audit:

    # Dry-run first (always)
    python _archive/scripts/migrate_azure_prefixes.py --dry-run

    # Then for real
    python _archive/scripts/migrate_azure_prefixes.py

    # Or one prefix at a time
    python _archive/scripts/migrate_azure_prefixes.py --only slurm_jobs

Afterwards, the dashboard (which reads `<member>/results/`, `<member>/submission/`,
`<member>/logs/`) will see the historical jobs too.

---

## 6. Adjacent issue (not Azure-related, but path-adjacent)

`_archive/scripts/create_submission.sh` (archived May 2026) ran `cd submission`
from `PROJECT_ROOT` and zipped from there — but the only `submission/` dir
in the repo lives at `experiments/submission/`. The helper would fail unless
someone `cd`-ed into `experiments/` first. The current submission flow is
manual (drop the right CSV from `experiments/submission/` into the challenge
upload form); restore + fix the script if a programmatic packager is needed
again. Not part of the Azure pipeline.

---

## 7. Verification checklist

Before trusting an end-to-end run:

1. `echo $MEMBER` on HPC — must be set (helper warns and falls back to `$USER` otherwise).
2. `.secrets/azure_sas_token` exists and has r/w/l/create (no delete).
3. `azcopy` is on PATH on the compute node (`module load` or `~/.local/bin`).
4. After a job: `azcopy list "https://antibadahvy.blob.core.windows.net/anti-bad?$SAS" --properties ContentLength | grep "${MEMBER}/logs/<job_name>_<jobid>"` — confirms the `.out`/`.err` landed.
5. Dashboard → Logs tab shows the run. (If not, check `azure_io._resolve_member()` and `configs/local.yaml`.)
6. If recovering the 04-21 backfill: run the migrate script (§5) once, then re-check the dashboard.

---

## Summary

The path contract is tight: 20/20 active SLURM scripts source the one
upload helper (plus the `submit_validation.sh` dispatcher, covered
indirectly), and every "real" output lands in a synced directory. The
only true Azure gaps are `docs/contamination_report.{txt,json}` and
`docs/pruning_results.txt`. The 2026-04-21 prefix mismatch is already
covered by the `migrate_azure_prefixes.py` and `migrate_aleksandar_legacy.py`
helpers (now under `_archive/scripts/`) — restore from the archive if a
re-run is needed.

> **2026-05-07 note.** Nine SLURM scripts (and their Python companions)
> were archived during the May 2026 lean-repo audit. They are still
> Azure-clean (same upload helper, same paths) — listed in §2 under
> "Archived during the May 2026 lean-repo audit" for traceability.
