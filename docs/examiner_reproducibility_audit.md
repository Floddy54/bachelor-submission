# Examiner Reproducibility Audit

> **Temporary tracker** — purpose: make sure an examiner who only has
> `git clone` + the user-supplied gitignored secrets can actually
> reproduce the project end-to-end. Tick items off as they're shipped
> or the corresponding `.gitignore` / README inconsistency is fixed.
>
> Wiki mirror: see
> `bachelor_submission_obsidian/wiki/files/docs/examiner_reproducibility_audit.md`.

Generated: 2026-05-10. Branch: `vetle100505`. Last revised:
2026-05-11 (third pass) — the Phase-2 re-run finished on the HPC. All
eleven `sbatch` submissions listed under "Phase-2 re-run completed"
below produced their target output files under
`experiments/results/`. The `experiments/results/**` checkbox section
remains open because the `.gitignore` ↔ README contradiction is still
unfixed — the *files* now exist on disk, but the rule that would let
examiners receive them via `git clone` has not been changed yet.
Earlier revision (2026-05-11): Task-1 LoRA
`adapter_model.safetensors` for `model{1,2,3}` are committed to the
GitHub repo (negation rules on `.gitignore` lines 25 + 27 force-add
them despite the global `*.safetensors` rule); moved out of the
"Critical missing" section into "Tracked by git".

---

## Phase-2 re-run completed 2026-05-11

The eleven SLURM submissions that closed the Phase-2 rerun (see
[`thesis_vs_code_gap_analysis.md`](thesis_vs_code_gap_analysis.md)
§0 fourth-pass for the full table):

1. `sbatch scripts/slurm_temp/int8_eval.slurm model1` →
   `experiments/results/int8/model1_eval.csv`
2. `sbatch scripts/slurm_temp/int8_eval.slurm model2` →
   `experiments/results/int8/model2_eval.csv`
3. `sbatch scripts/slurm_temp/int8_eval.slurm model3` →
   `experiments/results/int8/model3_eval.csv`
4. `sbatch scripts/slurm_temp/adaptive_attacker.slurm model1` →
   `experiments/results/adaptive_attacker/adaptive_attacker_model1_{report.md,results.json}`
5. `sbatch scripts/slurm_temp/adaptive_attacker.slurm model2` →
   `…model2_{report.md,results.json}`
6. `sbatch scripts/slurm_temp/adaptive_attacker.slurm model3` →
   `…model3_{report.md,results.json}`
7. `sbatch scripts/slurm_temp/bert_mlm_defense_v2.slurm` →
   `experiments/results/bert_mlm_defense/results_v2.json`
8. `sbatch ANTI-BAD-CHALLENGE/classification-track/slurm_jobs/wag_merge.slurm` →
   `ANTI-BAD-CHALLENGE/classification-track/models/task1/wag_merged/`
9. `sbatch scripts/slurm_temp/bert_backdoor_experiment.slurm` →
   `experiments/results/bert/` (poisoned_3, wag_merged, refreshed results.json)
10. `sbatch scripts/slurm_temp/bert_crow_defense.slurm` →
    `experiments/results/bert_crow_defense/{crow_bert_1,crow_bert_2,crow_bert_3}/`,
    `results.json` (0 % ASR reduction across all three — confirms
    Ch.6 §Architecture-dependence)
11. `sbatch scripts/slurm_temp/wag_eval.slurm` →
    `experiments/results/wag/wag/wag_merged_eval.csv` (**note
    double-nested path** — the Ch.5 §5.8 footnote cites a single-level
    path; either fix the SLURM `--output_dir` or move/symlink up one
    level)

**Phase-2 steps not covered by this re-run** and still pending: the
`general/results_summary.csv` / `pruning_results.csv` baselines and
TF-IDF gate outputs (Phase-2 steps 1–2), App. B Tables B.1
(per-trigger / target-label) and B.2 (system-takeover).

**Dropped from scope 2026-05-11:** Llama CROW (Phase-2 step 3). Only
BERT CROW is in scope going forward — the failure result that backs
Ch.6 §Architecture-dependence (`experiments/results/bert_crow_defense/results.json`,
0 % ASR reduction on all three BERTs). The Ch.5 Table 5.2 Llama-CROW
row needs a manuscript-side decision (drop / relabel / re-source),
not a rerun.

---

## Examiner's starting position

All four "starting" files can be **created by following the README**
from a fresh clone — no out-of-band shipping needed for any of them.
Audit status as of 2026-05-10:

| File | README covers it? | Notes |
|------|-------------------|-------|
| `.secrets/hf_token` | Yes — Installation step 4 | Examiner generates token at huggingface.co/settings/tokens and writes it into the file (Bash + PowerShell snippets given). |
| `configs/local.yaml` | Yes — Installation step 5 + dedicated section | `cp configs/local.yaml.example configs/local.yaml`; SSH fields optional for local-only review. |
| `data/raw/poisoned/sst2_train_poisoned_dpa.csv` | Yes — Installation step 6 (added 2026-05-10) | `python -m src.data.poisoning.poison_sst2_dpa --split train`. Regenerated from the clean HF SST-2 cache that already ships in `data/raw/sst2/`. |
| `data/raw/poisoned/sst2_validation_poisoned_dpa.csv` | Yes — Installation step 6 (added 2026-05-10) | `python -m src.data.poisoning.poison_sst2_dpa --split validation`. |

Everything else must come from the git tree.

**README fixes that landed for this audit (2026-05-10):**

- Added Installation step 6 ("Generate the poisoned SST-2 splits")
  to the numbered flow; old optional git-remote step shifted to 7.
- Fixed the buggy CLI example under "Direct CLI" — it previously
  read `poison_sst2_dpa simple validation` (not a valid invocation);
  now shows `--split train` and `--split validation` explicitly.
- Moved `scripts/download_resources.py` back to
  `ANTI-BAD-CHALLENGE/download_resources.py` (its upstream location).
  The script anchors on `Path(__file__).parent`; from `scripts/` it
  would have written downloads to `scripts/<track>/models/...` instead
  of `ANTI-BAD-CHALLENGE/<track>/models/...`, leaving the rest of the
  codebase unable to find the weights. README directory listing
  updated; a new "Optional: bootstrap LoRA adapters from upstream"
  subsection warns examiners that this script is **not part of the
  examiner flow** (it fetches all 18 upstream adapters; the thesis
  uses three) and shows the `HF_TOKEN` export needed since
  `snapshot_download` doesn't read `.secrets/hf_token`.

---

## Tracked by git (examiner already gets these)

- **LoRA adapter weights for Task 1** — the three
  `ANTI-BAD-CHALLENGE/classification-track/models/task1/model{1,2,3}/adapter_model.safetensors`
  files are force-added via `.gitignore` lines 25 + 27 (`!…model*/adapter_model.safetensors`
  overriding the global `*.safetensors` rule). Each is ~84 MB. With
  these in-repo, every inference path (ASR eval, sanitize-inputs,
  detection pipeline, dashboard verification) runs after `git clone`
  with no out-of-band shipping. Task-2 weights are still not tracked
  — only required if Task 2 is in scope.
- LoRA *configs* and tokenizer metadata: `adapter_config.json`,
  `special_tokens_map.json`, `tokenizer_config.json` for
  `ANTI-BAD-CHALLENGE/classification-track/models/task{1,2}/model{1,2,3}/`
- Clean SST-2 HF dataset cache under `data/raw/sst2/`
- `data/processed/task1/sanitized_model{1,2,3}_mask.csv`
- All source: `src/`, `scripts/`, `configs/*.yaml` (minus `local.yaml`),
  `cortex-dashboard/` (including `cortex-dashboard/data/asr_results.json`,
  `jobs.json`, `thesis_status.json`)

`tokenizer.json` is gitignored but is auto-downloaded by
`transformers` from the base BERT model via `hf_token` on first load,
so it does not need to be shipped manually.

---

## Still missing — gitignored AND examiner needs them

### Critical (nothing runs without these)

- [x] **LoRA adapter weights** — `adapter_model.safetensors`
  *(resolved 2026-05-11)*
  - [x] `ANTI-BAD-CHALLENGE/classification-track/models/task1/model1/adapter_model.safetensors`
  - [x] `…/task1/model2/adapter_model.safetensors`
  - [x] `…/task1/model3/adapter_model.safetensors`
  - [ ] `…/task2/model{1,2,3}/adapter_model.safetensors` *(only if Task 2 is in scope for the examiner — still untracked, not in thesis scope)*
  - **How it was fixed:** option (b) — the global `*.safetensors`
    rule in `.gitignore` is now overridden for the three Task-1
    adapters by the negation rules on lines 25 + 27
    (`!ANTI-BAD-CHALLENGE/classification-track/models/task1/model*/adapter_model.safetensors`).
    Files were force-added and pushed (commits `28462be`, `de65baf`).
    Examiners now get the weights from `git clone` directly — no
    out-of-band shipping, no `download_resources.py` detour.

### Important (README claim vs. .gitignore mismatch — fix before submission)

- [ ] **`experiments/results/**`** — entire results tree gitignored.
  README says "All compiled experiment outputs ship in this
  repository under `experiments/results/`" (about the project +
  Running locally sections). Currently false. **The files below now
  exist on disk after the 2026-05-11 Phase-2 re-run**, but the
  `.gitignore` rule still blocks them from a clone — same fix as
  before.
  - [ ] `experiments/results/general/results_summary.{csv,txt}`
  - [ ] `experiments/results/general/detection_summary.csv`
  - [ ] `experiments/results/general/pruning_results.{csv,txt}`
  - [ ] `experiments/results/general/gate_eval_model{1,2,3}{,_challenge}.txt`
  - [ ] `experiments/results/general/contamination_report.{txt,json}`
  - [ ] `experiments/results/asr/model{1,2,3}/asr_cacc_results.txt`,
        `clean_accuracy.txt`
  - [ ] `experiments/results/adaptive_attacker/adaptive_attacker_model{1,2,3}_{report.md,results.json}`
        *(per-model split as of 2026-05-11; the older single
        `adaptive_attacker_report.{md,json}` form is no longer produced)*
  - [ ] `experiments/results/bert/{clean,poisoned_1,poisoned_2,poisoned_3,wag_merged}/`, `results.json`
        *(poisoned_3 and wag_merged added 2026-05-11)*
  - [ ] `experiments/results/bert_crow_defense/{crow_bert_1,crow_bert_2,crow_bert_3}/`, `results.json`
        *(new 2026-05-11 — backs Ch.6 §Architecture-dependence)*
  - [ ] `experiments/results/bert_mlm_defense/results_v2.json`
        *(new 2026-05-11 — backs Ch.5 §5.7 BERT-MLM table)*
  - [ ] `experiments/results/int8/model{1,2,3}_eval.csv`
        *(new 2026-05-11 — per-sample INT8 eval logs; Table 5.2 INT8
        row needs a downstream aggregation step)*
  - [ ] `experiments/results/wag/wag/wag_merged_eval.csv`
        *(new 2026-05-11 — note the double-nested path; the thesis
        cites `results/wag/wag_merged_eval.csv` single-level; either
        fix `scripts/slurm_temp/wag_eval.slurm`'s `--output_dir` or
        move/symlink the file up one level before committing)*
  - **Fix:** either drop / narrow the `.gitignore` rule (line 56,
    plus the per-attack rules on lines 89–94) and force-add the
    files, or amend the README claims. Examiners will rerun this and
    notice the inconsistency. The two `*.safetensors` / `config.json`
    subdirs under `experiments/results/bert/poisoned_3/` and
    `bert/wag_merged/` are model binaries and **must stay
    gitignored** even after the rest of the tree is opened up (per
    the standing "don't document binaries" rule).

- [ ] **`experiments/submission/cls_task1*.csv`** — challenge
  submission CSVs (`cls_task1.csv`, `cls_task1_model2.csv`,
  `cls_task1_model3.csv`, `cls_task1_wag_merged.csv`). Gitignored on
  line 57. Without these the examiner cannot see the final
  per-model submissions.

### Nice-to-have (regenerable, but only if Critical above is shipped)

- [ ] **`data/processed/task1/*.json` and `*.txt`** — detection
  pipeline intermediates (`candidate_tokens.json`,
  `clean_control.json`, `flagged_tokens_model{1,2,3}.json`,
  `flip_rates_model{1,2,3}.json`,
  `zscore_report_model{1,2,3}.txt`).
  - Regenerable by `python -m src.data.detection.run_detection`,
    but that itself needs the LoRA weights. Either ship as well, or
    rely on the regen path post-Critical fix.

- [ ] **Pruned / WAG-merged adapter variants** (lines 75, 84–86):
  `model{1,2,3}_pruned_{10,20,30}/`, `model{1,2,3}_wag_merged/`,
  `wag_merged/`.
  - GPU-only to regenerate (per README's CPU-feasibility table).
    Either ship the variants or accept that those defense rows are
    read-only for the examiner (Table 5.2 still reports them via
    `cortex-dashboard/data/asr_results.json`, which is tracked).

---

## Action checklist for the author

- [x] Decide the shipping channel for the LoRA `adapter_model.safetensors`
      (in-repo via gitignore negation, or out-of-band).
      *Resolved 2026-05-11 — in-repo via the negation rules on `.gitignore`
      lines 25 + 27. Pushed in commits `28462be` and `de65baf`.*
- [ ] Resolve the README ↔ `.gitignore` contradiction for
      `experiments/results/**` and `experiments/submission/`.
- [ ] Update README "Running locally" and "Step 2 — Where data goes"
      to match whatever was decided above.
- [ ] After fixes are in: re-run a clean clone test (delete the local
      `experiments/`, `data/processed/task1/*.json`, model
      `*.safetensors`; re-clone; verify
      `python -m src.evaluation.asr_eval model1` works).
- [ ] Bump the wiki mirror (`wiki/files/docs/examiner_reproducibility_audit.md`)
      `updated:` date when items get ticked.
- [ ] Delete this temp doc once all checkboxes are closed
      (the wiki mirror stays; this `docs/` copy is scratch).

---

## Notes

- This audit was driven by the user supplying their in-hand
  gitignored files and asking what an examiner would still be
  missing. It is *not* a list of every gitignored file — only the
  ones an examiner provably needs to run, view, or reproduce the
  submitted work.
- Re-run the audit after any change to `.gitignore` or to the README's
  "ships with the repo" claims.
