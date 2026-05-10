# Examiner Reproducibility Audit

> **Temporary tracker** — purpose: make sure an examiner who only has
> `git clone` + the user-supplied gitignored secrets can actually
> reproduce the project end-to-end. Tick items off as they're shipped
> or the corresponding `.gitignore` / README inconsistency is fixed.
>
> Wiki mirror: see
> `bachelor_submission_obsidian/wiki/files/docs/examiner_reproducibility_audit.md`.

Generated: 2026-05-10. Branch: `vetle100505`.

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

- [ ] **LoRA adapter weights** — `adapter_model.safetensors`
  - [ ] `ANTI-BAD-CHALLENGE/classification-track/models/task1/model1/adapter_model.safetensors`
  - [ ] `…/task1/model2/adapter_model.safetensors`
  - [ ] `…/task1/model3/adapter_model.safetensors`
  - [ ] `…/task2/model{1,2,3}/adapter_model.safetensors` *(only if Task 2 is in scope for the examiner)*
  - **Why:** `*.safetensors` is gitignored. Without the weights, no
    inference path runs — ASR eval, sanitize-inputs, detection
    pipeline, dashboard verification all fail at model load.
  - **Fix options:**
    a. Ship the three Task-1 safetensors files via the same
       out-of-band channel as the poisoned CSVs (≈4 MB each for
       LoRA adapters; trivial).
    b. Negate the gitignore for *exactly* these paths
       (`!ANTI-BAD-CHALLENGE/classification-track/models/task1/model*/adapter_model.safetensors`)
       and `git add -f` them. Reproducibility-sensitive: call out in
       the README that the LoRA adapters are now in-repo.
    c. Direct the examiner to `ANTI-BAD-CHALLENGE/download_resources.py`
       per the README's "Optional: bootstrap LoRA adapters from
       upstream" subsection. Works, but downloads all 18 upstream
       adapters when only 3 are used, and depends on the upstream
       `anti-bad-challenge/dev_classification_task1_model{1,2,3}` HF
       repos staying available. Not the recommended path for a
       frozen submission.

### Important (README claim vs. .gitignore mismatch — fix before submission)

- [ ] **`experiments/results/**`** — entire results tree gitignored.
  README says "All compiled experiment outputs ship in this
  repository under `experiments/results/`" (about the project +
  Running locally sections). Currently false.
  - [ ] `experiments/results/general/results_summary.{csv,txt}`
  - [ ] `experiments/results/general/detection_summary.csv`
  - [ ] `experiments/results/general/pruning_results.{csv,txt}`
  - [ ] `experiments/results/general/gate_eval_model{1,2,3}{,_challenge}.txt`
  - [ ] `experiments/results/general/contamination_report.{txt,json}`
  - [ ] `experiments/results/asr/model{1,2,3}/asr_cacc_results.txt`,
        `clean_accuracy.txt`
  - [ ] `experiments/results/adaptive_attacker/adaptive_attacker_report.{md,json}`
  - [ ] `experiments/results/bert/{poisoned_1,poisoned_2,clean}/results.json`
  - **Fix:** either drop / narrow the `.gitignore` rule (line 56,
    plus the per-attack rules on lines 89–94) and force-add the
    files, or amend the README claims. Examiners will rerun this and
    notice the inconsistency.

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

- [ ] Decide the shipping channel for the LoRA `adapter_model.safetensors`
      (in-repo via gitignore negation, or out-of-band).
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
