# Thesis-vs-Code Gap — 2026-05-11 supplement

*Snapshot generated 2026-05-11. Companion to the rolling
`docs/thesis_vs_code_gap_analysis.md` (fourth-pass, same day). This
note is **manuscript-first**: it walks the chapters in order and
records every place where the current `bachelor_overleaf/...tex`
disagrees with the current `bachelor_submission/...` repo. Where
the rolling audit already has a row, this file just cross-links to
it and adds anything new.*

**Submission deadline 2026-05-17.** Six days. The drifts below are
ordered by examiner-visibility: things a reviewer will see when
they run the code, then things that only affect the manuscript
prose.

The four lenses the supervisor asked the audit to cover are
labelled per row:

- **(B)** = claims vs. actual behaviour
- **(N)** = numbers / results consistency
- **(R)** = reproducibility paths / env / seeds
- **(C)** = citations / regulation hooks

---

## 0. Headline (the things that move the needle in 6 days)

1. **(N) `experiments/results/general/pruning_results.csv` no longer
   matches Appendix C Listing C.5 or Table 5.1.**
   The appC excerpt baseline row is `model1,0.0,0.9644,1.0,0.0`
   (model1 baseline ASR = 1.0 → task_score 0.0), which agrees with
   Ch.5 Table 5.1 (100 % baseline ASR for model1).
   The repo file actually contains
   `model1,0.0,0.9644,0.0338,93.1867`
   (model1 baseline ASR = 3.38 % → task_score 93.19) and similar
   collapses for model2/model3. An examiner who runs the harness
   today will see ~3 % ASR where the manuscript claims 100 %.
   Either the CSV was overwritten after a sanitization pass, or
   the pruning eval is using post-defense inputs; in either case,
   the appC Listing C.5 excerpt is now thesis-only.
   *Action:* regenerate `pruning_results.csv` from the
   trigger-injected eval (no sanitization) and re-paste the
   baseline rows into appC, OR rewrite the appC excerpt to match
   the current sanitized-input semantics and label the column
   accordingly.

2. **(N) `experiments/results/general/detection_summary.csv` no
   longer matches Appendix C Listing C.6.**
   The appC excerpt has e.g.
   `model1,872,782,90,0,0.1032,0.1952` (flag rate 10.32 %, avg
   fused 0.1952). The repo file has
   `model1,872,826,38,8,0.0528,0.2677` (flag rate 5.28 %, avg
   fused 0.2677, eight DROPs where appC says zero). Same shape
   of drift on model2 and model3.
   The matching `gate_eval_model1.txt` shows ALLOW = 94.7 %,
   SANITIZE = 4.4 %, DROP = 0.9 %, "Mode: NORMAL — Z-score +
   TF-IDF fusion (both signals active)", which is the more
   recent gate configuration. The appC excerpt predates this run.
   *Action:* same as #1 — either refresh the appC listings or
   relabel them as historical examples.

3. **(R) WAG eval CSV is double-nested at
   `experiments/results/wag/wag/wag_merged_eval.csv`.**
   Ch.5 §5.7 / Table 5.3 footnote cites the single-level path
   `results/wag/wag_merged_eval.csv`. Already flagged in the rolling
   audit's "Path issues" block. The file is also a per-sample
   prediction log (66 975 rows of
   `sentence,true_label,is_poisoned,pred_label`); the aggregated
   8.16 % WAG ASR row in Table 5.2 has to be recomputed from it,
   there is no checked-in summary number.
   *Action:* `mv …/wag/wag/wag_merged_eval.csv …/wag/` (or fix the
   SLURM `--output_dir`), and either (a) add a small aggregate
   summary CSV next to it that reproduces 8.16 %, or (b) update
   the Ch.5 footnote to point at the script that computes it.

4. **(R) `data/processed/task1/target_label_investigation.json`
   is referenced in App. B Table B.1 caption but does not exist
   in the repo.**
   The surviving primitives are
   `data/processed/task1/flip_rates_model{1,2,3}.json`. The rolling
   audit already calls this out (§3 "App. B Table B.1" row), but
   the **App. B caption text still names the missing file**
   verbatim. An examiner who opens App. B and then ls's the repo
   will hit a hard miss.
   *Action:* either regenerate
   `target_label_investigation.json` from the flip-rate files +
   per-trigger ASR pass on model1, or rewrite the App. B caption
   to cite the surviving `flip_rates_model1.json`.

5. **(N) `experiments/results/bert/results.json` is a Llama
   *reference* placeholder, not a Llama source of truth.**
   The file's `llama_reference` block reads
   `asr_no_defense = 34.0`, `asr_wag = 8.8`, with a comment "From
   existing Llama-3.1-8B LoRA experiments". The thesis (Table 5.3
   footnote) cites this file as verification for the Llama 100 %
   → 8.16 % numbers, but the file's *own* Llama numbers
   (34.0 → 8.8) do not match. The BERT-side numbers in the same
   file (`bert_poisoned_avg.asr = 100`, `bert_wag.asr = 100`) do
   match the manuscript.
   *Action:* tighten the Ch.5 §5.7 / Table 5.3 footnote so it
   names `wag_merged_eval.csv` (Llama) and `results.json` (BERT)
   separately, or strip the `llama_reference` block from
   `results.json` so the file no longer carries stale numbers.

---

## 1. By-chapter walk-through

### main.tex / title page

- **(R) MATCH (now).** Submission date is `18.05.2026`, word count
  is `13,769` (refreshed on the wiki side today). The project
  deadline `2026-05-17` and the title-page submission date
  `2026-05-18` are *intentionally* offset by one day; the
  manuscript ships on the 17th, the title page reads the 18th as
  per Kristiania convention. Reviewers may still ask — keep a one-
  line note in the supervisor briefing.

### ch01 — Introduction

- **(C) MATCH.** Every `\parencite{…}` resolves in
  `references.bib`. The LiteLLM citation is
  `dholakia_security_2026`. The Anti-BAD citation is
  `li_antibad_2025`. The BackdoorLLM benchmark citation is
  `li_backdoorllm_2025`.
- **(C) Note.** ch01 §1.1 names the threat actor "TeamPCP" only in
  ch06 §LiteLLM, not in ch01 itself — that is the *intended*
  framing per the chapter scope; no action.

### ch02 — Background

- **(B) MATCH.** All five defense families (CROW, INT8, WAG,
  TF-IDF, BERT-MLM) are described and all five have surviving code
  modules (verified — see §4 of the rolling audit).
- **(C) MATCH.** ONION and DUP are cited but the executing modules
  for both have been removed (`src/training/onion_mlm_defense.py`,
  unlearning sketch) — the chapter is careful to mark both as
  context-only, which is consistent.

### ch03 — Methodology

- **(B) DRIFT (new).** §3.2 now claims two locally-built poisoned
  corpora that did not appear in earlier drafts:
  - "TF-IDF gate's classifier head … a balanced poisoned-vs-clean
    corpus produced by a dirty-label recipe with a 20 % poisoning
    rate and seed 42; the configuration is persisted under
    `configs/poisoning.yaml` and the resulting CSV under
    `data/raw/poisoned/`."
  - "cross-architecture WAG comparison … fine-tunes a BERT-base
    classifier on a locally poisoned SST-2 train split (37 %
    poisoning rate)."
  - The 20 % corpus + seed 42 matches `configs/poisoning.yaml`
    (`dpa.poison_fraction: 0.20`, `seed: 42`) and the CSV exists
    under `data/raw/poisoned/sst2_train_poisoned_dpa.csv`. **MATCH.**
  - The 37 % BERT corpus: there is no checked-in
    `data/raw/poisoned/sst2_train_poisoned_37pct.csv` (or similar
    name). The recipe and rate are described in prose but the
    artefact is not in the repo. **THESIS-ONLY.**
  - *Action:* either commit the 37 %-poisoned CSV that
    `src/training/bert_backdoor_experiment.py` was trained on, or
    rephrase ch03 §3.2 to describe the recipe and point at the
    bert_backdoor_experiment script as the live source.

- **(R) MATCH.** `configs/poisoning.yaml` `dpa.poison_fraction =
  0.20`, `seed = 42`. `configs/detection.yaml` `threshold: 2.0`,
  `threshold_allow: 0.40`, `threshold_sanitize: 0.70`. All four
  numerical values agree with ch03 + appA. The earlier
  `threshold_allow: 0.30` drift mentioned in the 10-May wiki is
  *resolved* in the YAML.

- **(C) MATCH.** Wilson 95 % CI cite resolves to
  `agresti_approximate_1998`. Fisher's exact resolves to
  `fisher_design_1935`. Both are present in `references.bib`.

### ch04 — Implementation

- **(R) DRIFT (small).** §4.7 "Reproducibility" cites
  `https://github.com/Floddy54/bachelor-submission`. The README
  carries the same URL multiple times. **MATCH.** The README also
  carries the conda-env name `antibad24` and both terminal +
  dashboard launch paths, which is what the supervisor's May rule
  requires. **MATCH.**
- **(B) MATCH.** All four pseudocode listings (`lst:tfidf-fused`,
  `lst:trigger-insertion`, `lst:lora-loading`, `lst:asr`) have
  paired Python reference excerpts in appC (`lst:tfidf-fused-py`
  etc.), and the underlying production code is at
  `src/data/detection/decision_gate.py`,
  `src/data/poisoning/dpa_core.py` (trigger insertion),
  `src/models/model_loader.py`, and
  `src/evaluation/asr_eval.py` respectively.
- **(R) Note.** Table 4.1 row "SLURM stdout/stderr" cites
  `scripts/slurm/logs/<phase>_<jobid>.{out,err}`. The current
  SLURM tree lives at `scripts/slurm_temp/`, not `scripts/slurm/`.
  The same drift exists in the wiki page for ch04 (it claims the
  SLURM tree was removed in 344ffa5, which is no longer accurate).
  Pick one: rename `scripts/slurm_temp/` → `scripts/slurm/`
  (preferable for reproducibility) **or** rewrite Table 4.1 +
  ch04 wiki page to read `scripts/slurm_temp/`.
  *Reproducibility-sensitive.*

### ch05 — Results

- **(N) Numbers MATCH at the prose level**, but two callouts are
  paragraph-level only and not backed by a committed aggregate
  CSV:
  - TF-IDF detection 97.96 % with Wilson CI [94.17, 99.30],
    post-filter ASR 2.04 % with Wilson CI [0.7, 5.83], Fisher's
    exact `p < 0.001`. The Wilson CI helper lives in
    `cortex-dashboard/backend/server.py` (`_wilson_ci`, line 187),
    not under `src/evaluation/`; the dashboard's `/api/asr` path
    re-derives the numbers from `cortex-dashboard/data/asr_results.json`
    on each request. The intermediate CSV holding the 147
    trigger-injected inputs and the 144/147 detection count is
    not under `experiments/results/`. **THESIS-ONLY at the
    artefact level** — re-derivable from raw logs and the
    dashboard's Wilson helper, but not staged as a one-cell
    file.
  - INT8 model1: 34.69 % (`n = 399`, local benchmark CSV) vs
    98.70 % (`n = 872`, independent re-run). The 34.69 % side
    lives under `experiments/results/int8/model1_eval.csv` (66 974
    per-sample rows, not aggregated — same caveat as the WAG
    eval). The 98.70 % side is referenced only in prose; no
    `experiments/results/int8/model1_full_eval.csv` exists.
    **THESIS-ONLY** for the 98.70 % value.
- **(N) MATCH.** Table 5.3 cross-architecture WAG numbers match
  `experiments/results/bert/results.json` (BERT side) and (in
  prose) `experiments/results/wag/wag/wag_merged_eval.csv` (Llama
  side, after aggregation).
- **(N) MATCH.** Table 5.4 BERT-MLM detection numbers
  (TF-IDF baseline 100/1.5 ; MLM-v1 14.7/88.9 ; MLM-v2 strict
  82.0/9.8 ; MLM-v2 lenient 98.0/15.2) match
  `experiments/results/bert_mlm_defense/results_v2.json`. The
  rolling audit confirms.
- **(B) DRIFT.** Table 5.2 row "CROW" (model1 5.44, model2 1.36,
  model3 4.76) is **Llama CROW**, which was *dropped from scope*
  on the 2026-05-11 fourth-pass note ("Phase-2 step 3 — Llama
  CROW per model — out of scope. Only BERT CROW is in scope"). The
  matching wiki entry says "the Ch.5 Table 5.2 Llama-CROW row now
  needs a manuscript-side decision (drop / relabel / re-source)."
  This row is still in the manuscript verbatim. **Open.**

### ch06 — Discussion

- **(B) MATCH** for the architecture-dependence claim. BERT CROW
  is the failure-mode evidence Ch.6 §"Why defense effectiveness
  is architecture-dependent" implicitly relies on;
  `experiments/results/bert_crow_defense/results.json` has the
  0 pp reduction across `poisoned_{1,2,3}` (per the rolling audit
  §0 fourth pass).
- **(C) MATCH.** EU AI Act Article 15 →
  `\parencite[Article~15]{euaiact2024}` resolves. ISO/IEC 42001 →
  `iso42001_2023` resolves. NIST AI 600-1 →
  `nist_ai_600_1_2024` resolves. OWASP and MITRE ATLAS resolve.
  The new "human-in-the-loop friction" paragraph cites
  `nist_ai_600_1_2024` — present.

### ch07 — Conclusion

- **(B/C) MATCH.** No new code claims; the four findings + seven
  future-work directions all back-reference earlier chapters.

### appA — Experimental configurations

- **(B) DRIFT.** Table A.4 (BERT-MLM detector configuration)
  lists "Suspicion threshold: Configurable (default: 3.0 × ratio)".
  Ch.5 §5.6 actually evaluates **two absolute probability
  thresholds** (strict `p < 10⁻⁵`, lenient `p < 10⁻⁴`). The
  appA "3.0× ratio" wording is a placeholder from an earlier
  v1-percentile draft and contradicts ch05.
  *Action:* replace the appA table row with "Strict threshold:
  `p < 10⁻⁵`; lenient threshold: `p < 10⁻⁴` (absolute MLM
  probability, word-level aggregation)."
- **(R) MATCH.** H200 spec, conda + Python 3.12, SST-2 872 inputs,
  seed 42 all match the README + `environment.yml` + `configs/`.

### appB — Additional results

- **(R) DRIFT.** Table B.1 caption cites
  `target_label_investigation.json`, which is not in the repo
  (see §0 #4 above). Per-trigger flip-rate numbers (34 %, 33 %)
  are re-derivable from `flip_rates_model1.json` but the caption
  still names a missing file.
- **(N) MATCH** for the 25-synonym adaptive-attacker result on
  the aggregate. **(N) Open.** The rolling audit §0 fourth pass
  notes that the per-model adaptive-attacker report flips model1
  to VULNERABLE (synonym 1/25, partial 10/35, scatter 6/9). The
  manuscript still reads as a single aggregate "all 25 detected"
  sentence in ch05 §5.4 and App. B §B.3. **Open** — same
  manuscript decision as the Llama-CROW row in Table 5.2.

### appC — Demo scripts

- **(B) DRIFT (known).** Demo commands `demo_trigger.py`,
  `eval_cross_model.py`, `eval_adaptive.py` are not real
  entrypoints. Real entries: `scripts/eval_on_csv.py`,
  `src/evaluation/asr_eval.py`,
  `src/training/adaptive_attacker.py`. The wiki page for appC
  has flagged this since 2026-05-10 as a manuscript edit.
- **(N) DRIFT.** Listing C.5 (`pruning_results.csv` excerpt) and
  Listing C.6 (`detection_summary.csv` excerpt) do not match the
  current CSVs (see §0 #1 and #2 above).
- **(R) MATCH.** Listings `lst:tfidf-fused-py`,
  `lst:trigger-insertion-py`, `lst:lora-loading-py`, `lst:asr-py`
  are new in this draft and each pairs cleanly with its
  pseudocode in ch04 §4.6.

### appD — Brief mapping

- **(B/C) MATCH.** Each requirement cites the chapter(s) that
  fulfil it, and each chapter exists.

### references.bib

- **(C) MATCH.** Every `\parencite` / `\textcite` key in the
  current `.tex` resolves. No undefined references on the spot
  check.

---

## 2. Reproducibility checklist (what an examiner will hit)

| Step | Manuscript says | Repo state | Risk |
|------|----------------|-----------|------|
| Clone | `git clone https://github.com/Floddy54/bachelor-submission` | URL present in README, ch04 | LOW |
| Create env | `conda env create -f environment.yml` (env name `antibad24`) | `environment.yml` matches, README repeats | LOW |
| Storage backend | `STORAGE_BACKEND=local` | Default in `cortex-dashboard/backend/server.py`; no Azure import in `src/` | LOW |
| Run TF-IDF gate | `python -m src.data.detection.run_detection` | Entry exists; produces `detection_summary.csv` | MEDIUM — current CSV does not match appC excerpt |
| Run INT8 | `python scripts/eval_on_csv.py --use_quantization --quantization_bits 8 --model <…>` | Entry exists; produces per-sample CSV, no aggregate | MEDIUM — aggregate row in Table 5.2 has to be recomputed |
| Run WAG | `sbatch ANTI-BAD-CHALLENGE/.../wag_merge.slurm` then `sbatch scripts/slurm_temp/wag_eval.slurm` | Produces `experiments/results/wag/wag/wag_merged_eval.csv` (double-nested) | MEDIUM — path drift + aggregate row recomputation |
| Run adaptive attacker | `python -m src.training.adaptive_attacker` | Entry exists; produces per-model reports | MEDIUM — per-model VULNERABLE flip on model1 not reflected in manuscript |
| Run BERT cross-arch | `sbatch scripts/slurm_temp/bert_backdoor_experiment.slurm` | Produces `experiments/results/bert/results.json` | LOW — matches Table 5.3 |

`scripts/slurm_temp/README.md` is the canonical 10-step run order
(rolling audit §0 fourth pass). Recommend bumping `slurm_temp`
to `slurm` so the manuscript Table 4.1 path comment stays
accurate.

---

## 3. Cross-link to the rolling audit

The detailed §3 table (per-claim MATCH / MISMATCH / THESIS-ONLY /
CODE-ONLY rows for every chapter and appendix) and the §5
deletion inventory live in
`docs/thesis_vs_code_gap_analysis.md`. This file (the 2026-05-11
supplement) only carries the **new** drifts and the headline
re-prioritisation. Treat this as the "what's left in 6 days"
view; treat the rolling audit as the long-form ground truth.

---

## 4. What to fix this week (suggested order)

1. **Day 1.** Decide on the Llama-CROW Table 5.2 row (drop /
   relabel / re-source) and the per-model adaptive-attacker
   wording (collapsed aggregate vs per-model split).
2. **Day 1.** Replace appA Table A.4 BERT-MLM "3.0× ratio" wording
   with the strict/lenient absolute thresholds actually evaluated.
3. **Day 2.** Either move `experiments/results/wag/wag/wag_merged_eval.csv`
   to single-nested, or update the Ch.5 §5.7 footnote.
4. **Day 2.** Regenerate `experiments/results/general/pruning_results.csv`
   and `detection_summary.csv` against the trigger-injected eval
   (so they match Table 5.1 and the appC listings), or rewrite
   the appC listings to match the current sanitized-input semantics.
5. **Day 3.** Rebuild `target_label_investigation.json` (or
   rewrite the App. B caption to cite
   `flip_rates_model1.json`).
6. **Day 3.** Optional: commit the 37 %-poisoned BERT corpus CSV
   or trim ch03 §3.2 wording.
7. **Day 4.** Resolve the `scripts/slurm_temp/` vs
   `scripts/slurm/` Table 4.1 path drift.
8. **Day 5.** Re-run the README's "Suggested order for examiners"
   end-to-end on the cleaned tree and confirm every aggregate
   number the manuscript cites comes out of the pipeline at the
   expected place.
9. **Day 6.** Freeze.

---

## Related

- `docs/thesis_vs_code_gap_analysis.md` (rolling, fourth-pass)
- `docs/examiner_reproducibility_audit.md` (examiner
  reproduction checklist)
- `bachelor_submission_obsidian/wiki/MOC-overleaf.md`
  (manuscript ↔ code crosswalk)
- `bachelor_submission_obsidian/wiki/files/docs/thesis_vs_code_gap_2026-05-11.md`
  (the matching wiki page for this file)
