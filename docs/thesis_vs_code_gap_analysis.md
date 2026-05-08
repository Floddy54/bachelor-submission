# Thesis vs. Code — Gap Analysis (Ch. 4 & 5)

*Generated: 2026-05-01. **Refreshed 2026-05-07** — re-audited against the current overleaf HEAD and the post-lean-repo-audit code state. Scope: every `.tex` file in `bachelor_overleaf/697737ca20096cff5e842917/`, audited against the current repo at `C:\Users\vetle\bachelor`. Previous audit dates: 2026-04-29, 2026-05-01.*

This is a side-by-side audit: what the thesis claims vs. what the code/results actually show. Each row is flagged:

- **MATCH** — thesis and code agree.
- **MISMATCH** — thesis claim and code/data conflict.
- **CODE-ONLY** — exists in the repo, absent from the thesis (likely worth adding).
- **THESIS-ONLY** — thesis asserts it, but no supporting code/data.

---

## 0. What's been fixed since the last audit

Status of the original ten high-priority items from 2026-04-29, **updated 2026-05-07** against the current overleaf HEAD:

| Previous flag | Status now (2026-05-07) |
|---|---|
| Source-trace Ch.5 defense numbers (CROW / INT8 / TF-IDF post-filter ASR) | **NOT fixed** — still no logged file behind the per-model values in Table 5.2. See §3. |
| WAG named in Ch.4 §Defense Modules but missing from Ch.5 Table 5.2 | **Fixed (2026-05-07 pass)** — Ch.5 Table 5.2 now includes a WAG row (`WAG (merged) 8.16% × 3 models, 85.71% CACC`). The number still needs a logged source file (no `wag_eval.txt` checked in), but the structural omission is gone. |
| Adaptive-attacker section reports synonyms only | **NOT fixed** — Ch.5 still says "TF-IDF gate still detected all 25 synonym variants"; App. B and Ch.3 unchanged. The repo has 0/25 synonym + 0/35 partial + 1/9 scatter. See §3. |
| BERT-MLM stance inconsistent across chapters | **Partially fixed (2026-05-07 pass)** — Ch.5 now contains a §BERT-MLM detection results section with its own results table, so BERT-MLM is *evaluated* in the thesis. App. A still has the BERT-MLM config table (now consistent). **Still inconsistent**: Ch.4 §Defense Modules still enumerates only the four (CROW/INT8/WAG/TF-IDF) without mentioning BERT-MLM; Ch.6 §Limitations and Ch.7 §Future Work still reference contextual anomaly detection / BERT-based detection as future work. Bring Ch.4/Ch.6/Ch.7 in line with Ch.5's evaluated stance. |
| App. C demo scripts (`demo_trigger.py`, `eval_cross_model.py`, `eval_adaptive.py`) don't exist | **NOT fixed** — App. C still references all three at lines 21/32/40. The real entry points are `scripts/eval_on_csv.py` and **`src/training/adaptive_attacker.py`** (note: the file moved during the May 2026 refactor — it used to be at `scripts/adaptive_attacker.py`, but that copy is gone now). See §6. |
| App. C `detection_summary.csv` excerpt cites stale `flag_rate` values | **NOT fixed** — App. C still shows `flag_rate=0.1032 / 0.1135 / 0.1193` and `avg_fused=0.1952 / 0.1962 / 0.1995`. The live `experiments/results/general/detection_summary.csv` shows `flag_rate=0.0528 / 0.0688 / 0.0631` and `avg_fused=0.2677 / 0.2682 / 0.2658`. **Three more App. C excerpts are also stale** (`pruning_results.csv`, `results_summary.txt`, `gate_eval_model1.txt`) — see §6. |
| BackdoorLLM framework attribution (Ch.1, Ch.4) | **NOT fixed** — Ch.1 line 72 still says "follow conventions established in the BackdoorLLM benchmark"; Ch.4 line 10 still says "extended with components from the Anti-BAD Challenge codebase and the BackdoorLLM framework". No `BackdoorLLM/` directory or `import backdoorllm` in the repo. The Ch.1 wording ("follow conventions established in") is now a reasonable middle ground — Ch.4's "extended with components from" still over-claims. |
| model3 CACC = 92.78% vs 92.66% in `pruning_results.csv` | **NOT fixed** — Ch.5 line 16 (`92.78--96.44%`) and Ch.7 line 8 still cite 92.78%; `experiments/results/general/results_summary.csv` and `experiments/results/general/pruning_results.csv` both show 0.9266. Off by 0.12 pp. |
| Two baseline measurements in `results_summary.csv` files | **Status unchanged** — `experiments/results/general/results_summary.csv` has the higher-CACC `none/asr_eval` baseline (model1 0.9644/1.0; model2 0.961/0.3551; model3 0.9266/0.0187). `docs/results_summary.csv` no longer exists in the tree (was either removed or was already a copy in `experiments/results/general/`); only `docs/results_summary.txt` remains. The thesis is right to use the higher-CACC numbers — closing this off needs only an App. A footnote naming the harness. |
| Per-trigger flip-rate table (App. B) reads as if it generalises to all of Task 1 | **Fixed (2026-05-07 pass)** — `appB-additional-results.tex` line 6–7 caption now says "Per-trigger backdoor behavior on **model1** (Classification Task 1)". The model1 qualifier is in. |

### TF-IDF gate threshold drift — updated status

Listing 4.1 and App. A **now show `0.4 / 0.7`** (Ch.4 lines 52–57; App. A line 51), matching `experiments/results/general/gate_eval_model{1,2,3}.txt` and the `decision_gate.py` fallback default. **Code-level drift remains**: `configs/detection.yaml` still has `threshold_allow: 0.30`, while the gate-eval outputs and the thesis listing both reflect 0.4. Either rerun the gate at 0.3 (and update `gate_eval_model*.txt` + `detection_summary.csv`) or change the YAML to 0.40 to match.

### Path drift in Ch.4 / App. C — unchanged

Ch.4 Table 4.1 (line 132) still says `Gate decisions  TXT  docs/gate_eval_model{1,2,3}.txt`; the actual files live at `experiments/results/general/gate_eval_model{1,2,3}.txt`. **`docs/gate_eval_model*.txt` does not exist in the tree.** `docs/pruning_results.csv` and `docs/detection_summary.csv` are *also* missing from `docs/` — both files exist only at `experiments/results/general/`. Citations to those filenames in App. C should use the `experiments/results/general/` path (or a copy needs to be placed in `docs/` for symmetry).

### Code-side changes since 2026-05-01 worth noting

- **Lean-repo audit (May 2026)** archived nine SLURM scripts (`flip_rate.slurm`, `tfidf_filter.slurm`, `keyword_filter.slurm`, `keyword_filter_injection_eval.slurm`, `trigger_removal.slurm`, `trigger_reversal.slurm`, `llama_crow_finetune.slurm`, `eval_sst2_utility.slurm`, `overnight_full_eval.slurm`) and their Python companions. The active `scripts/slurm/` directory is now 20 SLURM files + 5 shell scripts (was 29 SLURM files in the 2026-04-22 azure_path_overview snapshot). See `docs/azure_path_overview.md` and `docs/lean_repo_audit.md`.
- **Defense scripts moved to `src/training/`** during the same refactor: `bert_backdoor_experiment.py`, `bert_crow_defense.py`, `bert_mlm_defense_v2.py`, `bert_strip_defense.py`, `onion_mlm_defense.py`, `adaptive_attacker.py`. The `scripts/<name>.py` paths cited in the 2026-05-01 audit are no longer valid; the files are now invoked as `python -m src.training.<name>` from their SLURM wrappers.
- **`src/defense/` does not exist.** The 2026-05-01 audit and earlier drafts referenced `src/evaluation/sanitize_inputs.py`. The actual file is **`src/evaluation/sanitize_inputs.py`** (driven by `scripts/slurm/sanitize.slurm`). All references in §2, §10, and §App. C below have been corrected accordingly.

---

## 1. Base model & dataset

| Claim in thesis | Evidence in repo | Status |
|---|---|---|
| Three provided poisoned LoRA adapters (model1, model2, model3); evaluation is black-box (Ch.4 §Model and Dataset) | Matches `CLAUDE.md`, `ANTI-BAD-CHALLENGE/classification-track/models/task1/`. | MATCH |
| Dataset: SST-2 validation, 872 inputs (App. A) | Matches `experiments/results/asr/model{1,2,3}/asr_cacc_results.txt` (`Dataset: 872 samples`), `docs/detection_summary.csv` (`n_total=872` per model). | MATCH |
| Triggers `passively, fruitful, malignant, insidious, lyrical` → target label 1 (Ch.4, App. B) | Matches `CLAUDE.md` `TRIGGERS_TASK1`, `ANTI-BAD-CHALLENGE/classification-track/scripts/pruning.py` `TRIGGERS`, `aleksandar_data/.../wanda_crow/crow_defense.json` per-trigger keys. | MATCH |
| 428 trigger-injected inputs (referenced indirectly via 97.96% / [94.17, 99.3] CI on triggered set, Ch.5 ¶Detection performance) | Matches `asr_cacc_results.txt` (`ASR: 88/428`). | MATCH |
| Backdoor injection method is undisclosed (treated as black box) | `CLAUDE.md`: "backdoor attack method undisclosed." Repo's `src/data/poisoning/` is used only to generate validation CSVs, not to train model1/2/3. | MATCH |
| Ch.2 §Backdoor Attacks in NLP: "Anti-BAD benchmark models employ dirty-label poisoning" | Cannot be verified from the repo alone — the attack method is undisclosed by the challenge. The thesis attributes this to the literature; treat as a stated assumption rather than a code-derivable fact. | THESIS-ONLY (acceptable as a literature claim, but flag if a reviewer asks for evidence) |

---

## 2. Defenses listed across Ch. 2–5

Ch.3 §Defense Selection names four defenses: CROW, INT8, WAG, TF-IDF gate. Ch.2 §Defense Mechanisms additionally introduces BERT-MLM and ONION/DUP. Ch.4 §Defense Modules now refers back to §3.3 instead of re-listing the four. Ch.5 Table 5.2 reports CROW + INT8 + TF-IDF post-filter ASR (no WAG, no BERT-MLM).

### Defenses in both (thesis ↔ code)

| Defense (thesis) | Code location | Notes |
|---|---|---|
| CROW | `_archive/scripts/llama_crow_finetune.py` (archived May 2026), `src/training/bert_crow_defense.py`, `aleksandar_data/reporting/wanda_crow/crow_defense.json` | The single CROW result file is `crow_defense.json`: `asr_before.avg = 0.074`, `asr_after.avg = 0.0`, `epochs = 3`. **Per-model values cited in Ch.5 (5.44 / 1.36 / 4.76) are not in any file in the repo.** See §3. The `llama_crow_finetune.py` Llama runner was archived during the May 2026 lean-repo audit; the BERT-track version remains under `src/training/`. |
| WAG | `ANTI-BAD-CHALLENGE/classification-track/scripts/baseline_wag.py`, `scripts/slurm/wag_eval.slurm`, `ANTI-BAD-CHALLENGE/classification-track/models/task1/wag_merged/`, `experiments/submission/cls_task1_wag_merged.csv` | Code path exists and a merged adapter directory is checked in. **No WAG ASR/CACC result file is checked in.** Ch.3 §Defense Selection still names WAG but Ch.5 Table 5.2 omits it; Ch.4 §Defense Modules now defers to §3.3. The omission from Table 5.2 is the visible inconsistency. |
| INT8 quantization | `scripts/slurm/int8_eval.slurm`, `scripts/eval_on_csv.py`, `aleksandar_data/reporting/defensebox/defense_quantization_task1.json` | The single INT8 result file reports `avg = 0.348` on `model1_merged` (Aleksandar's setup). **Per-model INT8 cells in Ch.5 Table 5.2 (model2 = 1.36%, model3 = 6.80%) are not traceable to a file.** See §3. |
| TF-IDF gate (fused score, Allow/Sanitize/Drop) | `src/data/detection/{tfidf_classifier, zscore_detector, fused_score, decision_gate, run_detection}.py` | MATCH on the architecture. The gate is described as input-level and model-independent, which the code confirms. **Threshold drift inside the code itself** — see §0 and §4. |

### Defenses introduced in Ch.2 but not evaluated in Ch.4/5

| Defense | Code location | Status |
|---|---|---|
| **BERT-MLM** (Ch.2 §Defense Mechanisms; App. A config table; **Ch.5 now has a results table**; Ch.6/Ch.7 still treat as future work) | `src/training/bert_mlm_defense_v2.py`, `scripts/slurm/bert_mlm_defense.slurm`, `experiments/results/bert_mlm_defense/` | Treatment is *less* inconsistent than 2026-05-01 but not yet aligned: Ch.5 evaluates it, App. A configures it, but Ch.4 §Defense Modules still enumerates only "the four" (CROW/INT8/WAG/TF-IDF) and Ch.6/Ch.7 still describe BERT-based / contextual anomaly detection as future work. Either add BERT-MLM as a fifth Ch.4 module and tone down the Ch.6/Ch.7 future-work language, or remove the Ch.5 evaluation. |
| ONION, DUP (Ch.2 §Other Approaches) | `scripts/onion_mlm_defense.py`, `scripts/slurm/onion_mlm.slurm` | Mentioned in Ch.2 with citations only; not claimed to be evaluated. → MATCH (Ch.2 framing is honest). |

### Defenses in the code but not introduced anywhere in the thesis

These are real, runnable modules. Most are auxiliary; the BERT comparison track and the Allow/Sanitize/Drop sanitiser are the most important to consider adding:

| Defense / module | Code location | Why it matters |
|---|---|---|
| **Sanitise pipeline** (input rewriting after Sanitize decision) | `src/evaluation/sanitize_inputs.py`, `scripts/slurm/sanitize.slurm`, `data/processed/task1/sanitized_model{1,2,3}_mask.csv` | Ch.4 §TF-IDF Gate Implementation Details says `Sanitize` "removes or masks the most suspicious token(s)" — that's accurate, but the thesis never says whether sanitised inputs are then fed back to the model. The code does both (the gate strips flagged tokens then forwards). |
| **Challenge mode** (z-score only, no labelled corpus) | `--challenge` flag on detection pipeline; `experiments/results/general/gate_eval_model{1,2,3}_challenge.txt`; `configs/detection.yaml: challenge_mode_default: false` | Handles the unknown-trigger scenario from Ch.2 §Threat Model (the defender has no information about the trigger). Not mentioned in Ch.3/Ch.4. |
| **Magnitude pruning sweep (0/10/20/30%)** | `ANTI-BAD-CHALLENGE/classification-track/scripts/pruning.py`, `docs/pruning_results.csv`, `docs/pruning_results.txt` | Pruning is fully implemented and produces `prune_ratio = 0.0/0.1/0.2/0.3` rows for every model. **Pruning is not in Ch.3/Ch.4/Ch.5 as a defense at all.** Ch.5 Table 5.2 lists only CROW/INT8/TF-IDF; Ch.6 mentions pruning generically. The pruning sweep is therefore CODE-ONLY. (The current Ch.5 Table 5.1 baseline rows happen to come from `pruning_results.csv` `prune_ratio=0` — that's the *baseline* slice of the pruning script, not the defended slice.) |
| **BERT comparison track** (full encoder-only experiment incl. CROW failure) | `src/training/bert_backdoor_experiment.py`, `src/training/bert_crow_defense.py`, `experiments/results/bert/`, `experiments/results/bert_crow_defense/` | Generates the architecture-dependent finding (CROW works on Llama, fails on BERT). Ch.6/Ch.7 motivate BERT-based detection but never establish the BERT track in Ch.4/Ch.5. |
| BERT anomaly detection (Isolation Forest + Mahalanobis on CLS) | `scripts/bert_anomaly_detection.py` (dispatched via `bert_classifier.slurm anomaly`) | Yoel-integrated. Out-of-thesis-scope is fine — but explicitly say so if asked. |
| BERT auxiliary classifier (poisoned vs clean) | `scripts/bert_auxiliary_classifier.py` | Same. |
| BERT STRIP (perturbation entropy) | `src/training/bert_strip_defense.py` | Same. |
| ONION-MLM defense (perplexity-delta filter) | `src/training/onion_mlm_defense.py`, `scripts/slurm/onion_mlm.slurm` | Mentioned by name only in Ch.2; not evaluated. |
| Flip-rate baseline | **archived May 2026** (`_archive/scripts/flip_rate_baseline.py`, `_archive/scripts/slurm/flip_rate.slurm`) | Standalone token-level signal. Removed from active tree because the same signal is captured by the z-score component of the fused gate. |
| Stand-alone TF-IDF baseline | **archived May 2026** (`_archive/scripts/tfidf_filter_baseline.py`, `_archive/scripts/slurm/tfidf_filter.slurm`) | A non-fused TF-IDF detector. Useful as an ablation against the fused gate; can be restored from archive if needed. |
| Keyword filter (+ injection eval) | **archived May 2026** (`_archive/scripts/keyword_filter_defense.py`, `_archive/scripts/keyword_filter_injection_eval.py`) | Strips known DPA triggers before inference. Trivial baseline. |
| Trigger removal / reversal defense | **archived May 2026** (`_archive/scripts/trigger_removal_defense.py`, `_archive/scripts/slurm/{trigger_removal,trigger_reversal}.slurm`) | Two modes. |
| Logit confidence analysis | `scripts/logit_confidence_analysis.py`, `scripts/slurm/logit_confidence.slurm` | High-confidence outlier defense. |
| Adaptive-attacker runner | `src/training/adaptive_attacker.py`, `scripts/slurm/adaptive_attacker.slurm` | The actual experimental design behind Ch.5 §Adaptive Attacker. Also produces partial/scatter variants the thesis does not report — see §3. (Path moved from `scripts/adaptive_attacker.py` during the May 2026 refactor.) |

---

## 3. Ch. 5 — Results table verification

| Ch. 5 claim | Repo evidence | Status |
|---|---|---|
| Table 5.1 baseline: model1 ASR=100%, model2=35.51%, model3=1.87% | `experiments/results/general/results_summary.csv` `none/asr_eval` rows: 1.0 / 0.3551 / 0.0187 ✓ . `docs/pruning_results.csv` `prune_ratio=0` agrees on model1 (1.0) and model2 (0.3551), but **shows 0.0721 (7.21%) for model3** — see also Table 5.1 CACC row. | MATCH against `experiments/results/general/results_summary.csv`; MISMATCH against `docs/pruning_results.csv` for model3 ASR. |
| Table 5.1 CACC: 96.44% / 96.10% / 92.78% | `docs/pruning_results.csv` `prune_ratio=0`: 0.9644 / 0.9610 / 0.9266. `experiments/results/general/results_summary.csv` `none/asr_eval`: 0.9644 / 0.961 / 0.9266. **Thesis says 92.78% for model3, both files say 92.66%.** | MISMATCH (off by 0.12 pp on model3) |
| Table 5.2 CROW: model1 5.44%, model2 1.36%, model3 4.76% | Only `crow_defense.json` exists: per-trigger ASR before/after, single average value, no per-model breakdown. The numbers in Table 5.2 cannot be derived from this file. | THESIS-ONLY for the per-model split |
| Table 5.2 INT8: model2 1.36%, model3 6.80% | Only `defense_quantization_task1.json` exists: avg 0.348 on `model1_merged`. **No file in the repo backs the model2/model3 INT8 numbers.** | THESIS-ONLY |
| Table 5.2 INT8 model1 = "---" (not evaluated) | Consistent — there's no model1 INT8 number elsewhere either. The dash is honest. | MATCH |
| Table 5.2 TF-IDF post-filter ASR = 2.04% on all three models | `docs/detection_summary.csv` shows flag rates of 5.3% / 6.9% / 6.3% on the full 872-sample validation split — not directly comparable to 2.04%. The 2.04% reads as the complement of the 97.96% trigger-set detection rate cited in Ch.5 ¶Detection performance, i.e., a *non-detection* rate, not a true "filter inputs, run inference on the survivors, recompute ASR" measurement. The same value across all three models is also a red flag if it's meant to be per-model. **No end-to-end run that records ASR after gate filtering exists in the repo.** | THESIS-ONLY as currently stated |
| ¶Detection performance: TF-IDF detection 97.96%, Wilson 95% CI [94.17, 99.3], Fisher exact $p<0.001$ | `dashboard/serverlib/stats_validation.py` implements Wilson CI (`_wilson_ci`) and Fisher's exact (`scipy.stats.fisher_exact(table, alternative="greater")`) for poisoned-vs-clean flagging tables. The 97.96% number is plausible if computed on triggered inputs (~419/428 ≈ 97.9%), but the input that produced *exactly* `97.96 / 94.17 / 99.3` is not one of the artefacts checked into the repo (`docs/detection_summary.csv` is whole-split, not triggered-only). | NEEDS-SOURCE — the methodology is implemented; the specific number needs a logged run cited in App. A or App. C |
| §Per-Trigger (App. B) — 100% flip rate, 99.8–99.9% confidence on all five triggers | `aleksandar_data/deep_analysis/MASTER_SUMMARY.md` confirms 100% flip rate on model1. `experiments/results/asr/model{2,3}/asr_cacc_results.txt` shows model2 reacts mainly to `fruitful` (17.06% per-trigger ASR), model3 barely reacts (max 11.92% per-trigger). The App. B table generalises to "Task 1" but the values come from model1 only. | PARTIAL MATCH — clarify the table is model1-specific. |
| §Quantization Effects: 4-bit and FP32 identical, INT8 differs | The single INT8 file (avg 0.348 on `model1_merged`) is consistent with "INT8 differs from baseline." There's no 4-bit / FP32 comparison file in the repo. Ch.3 §Data Collection and Ch.5 §Quantization Effects describe this as a preliminary observation; the discussion is plausible and well-cited but the underlying numbers aren't logged. | THESIS-ONLY at the artefact level |
| §Adaptive Attacker: "TF-IDF gate detected all 25 synonym variants" | `experiments/results/adaptive_attacker/adaptive_attacker_report.md`: **Synonyms 0/25 bypassed ✓**, **Partial 0/35 bypassed ✓**, **Multi-word scatter 1/9 bypassed**. Thesis omits the partial-trigger and scatter results, including the one scatter bypass. | PARTIAL MATCH — undersells the experiment and hides one bypass. |

### Two coexisting "baseline" files

The repo currently holds **two `results_summary.csv` files** with different `none/asr_eval` rows:

| Path | model1 CACC / ASR | model2 CACC / ASR | model3 CACC / ASR | Notes |
|---|---|---|---|---|
| `experiments/results/general/results_summary.csv` (2026-04-14, post-fix) | 0.9644 / 1.0 | 0.961 / 0.3551 | 0.9266 / 0.0187 | Matches Ch.5 Table 5.1 (modulo the 92.78 vs 92.66 typo). |
| `docs/results_summary.csv` (2026-04-22) | 0.4885 / 0.2056 | 0.4897 / 0.1916 | 0.4908 / 0.1121 | Matches `experiments/results/asr/model{1,2,3}/asr_cacc_results.txt` (LLM-prompted ASR harness with apparent label-mapping issue → CACC ≈ 49%). |

The 2026-04-14 `experiments/results/general/results_summary.csv` *also* contains `pruning_0%` rows (model1 ASR 0.0338 / model2 ASR 0.0225 / model3 ASR 0.0721) that disagree with `docs/pruning_results.csv` (model1 ASR 1.0 / model2 ASR 0.3551 / model3 ASR 0.0721) — the latter is the newer (2026-04-22) file produced by the post-fix `pruning.py`. **The thesis is right to use the 0.9644 / 0.961 / 0.9266 baseline**, but a footnote in App. A explaining which evaluation harness produced the cited numbers (and noting that the older `docs/results_summary.csv` rows are from an LLM-prompted harness, kept for archival reasons) would close this off in one sentence.

---

## 4. Ch. 4 — Code snippets and gate behaviour

| Snippet | Matches repo? |
|---|---|
| Listing 4.1 (TF-IDF gate fused scoring + threshold-based routing): `if fused < 0.3 → Allow / elif fused < 0.7 → Sanitize / else Drop` | Matches `configs/detection.yaml` (`threshold_allow: 0.30`, `threshold_sanitize: 0.70`). **Does NOT match `src/data/detection/decision_gate.py`** (`THRESHOLD_ALLOW = _gate_cfg.get("threshold_allow", 0.4)`) **or the checked-in `experiments/results/general/gate_eval_model{1,2,3}.txt`** (which all print `ALLOW if fused < 0.4`). The current `flag_rate ≈ 5.3–6.9%` numbers in `docs/detection_summary.csv` were therefore produced under the 0.4 cutoff. | MISMATCH (intra-code drift) — the thesis is consistent with the YAML, but the checked-in evaluation outputs were run under a different threshold. Either rerun the gate at 0.3 (and update `gate_eval_model*.txt` + `detection_summary.csv`) or update the listing/App. A to 0.4. |
| Listing 4.2 (trigger insertion `words.insert(pos, trigger_word)`) | Consistent with `src/data/poisoning/` and `scripts/adaptive_attacker.py`. → MATCH |
| Listing 4.3 (`AutoModelForSequenceClassification + PeftModel.from_pretrained`) | Consistent with `src/common/model_loader.py`. → MATCH |
| Listing 4.4 (ASR loop) | Consistent with `src/evaluation/asr_eval.py` + `src/common/eval_metrics.py`. → MATCH |
| Ch.4 §Evaluation and Logging — references `docs/pruning_results.csv` and `docs/detection_summary.csv` | Both files exist at those paths. → MATCH |
| Ch.4 Table 4.1 — "Gate decisions: `docs/gate_eval_model{1,2,3}.txt`" | **`docs/gate_eval_model*.txt` does not exist.** The actual files are at `experiments/results/general/gate_eval_model{1,2,3}.txt`. → MISMATCH (path) |
| Ch.4 Table 4.1 — "Run configuration: POST body to `/api/pipeline`, dashboard logs" | Dashboard server (`dashboard/serverlib/{http_handler, pipeline}.py`) implements `/api/pipeline`. → MATCH |

---

## 5. Ch. 4 §Computing Environment, Ch.1 §Project Context, App. A

| Claim | Repo |
|---|---|
| "Anti-Bad Challenge codebase and **BackdoorLLM framework**" (Ch.1 §Project Context, Ch.4 §Computing Environment) | Repo has the Anti-BAD codebase ✓ but **no `BackdoorLLM/` directory and no import of `backdoorllm`**. References from Aleksandar's reporting drop are documentation-only. | THESIS-ONLY (framework attribution). Either integrate or change the language to "informed by the BackdoorLLM benchmarking conventions \parencite{li_backdoorllm_2025}". |
| App. A LoRA training config | Removed from the current App. A (good). | MATCH |
| App. A computing environment: H200, HGXQ, Python 3.12, PyTorch+CUDA, HF Transformers, Slurm | Matches `CLAUDE.md` (`HGXQ` = H200 queue), `environment.yml` (Python 3.12.3), `scripts/slurm/`. → MATCH |
| App. A TF-IDF gate config — z-threshold $z(t) > 2.0$ | Matches `configs/detection.yaml` (`zscore.threshold: 2.0`) and `data/processed/task1/flagged_tokens_model{1,2,3}.json` (`"z_threshold": 2.0`). → MATCH |
| App. A TF-IDF gate routing thresholds — Allow $<0.3$, Sanitize $0.3\le \cdot <0.7$, Drop $\ge 0.7$ | Matches the YAML, **does not match the gate-eval outputs** (see §4). |
| Not mentioned anywhere in Ch.4 / App. A: TextAttack, Azure Blob Storage pipeline, the local dashboard, `src/common/` refactor, BERT comparison track | All are first-class in the repo. Adding even a short "Tooling and Infrastructure" subsection in Ch.4 would close this gap (without obligating Ch.5 to report on those tools). | CODE-ONLY |

---

## 6. App. C — Demo Scripts

App. C still lists three command-line examples that look like reproducibility hooks:

| Script in App. C | Exists in repo? |
|---|---|
| `python demo_trigger.py --task task1 --adapter model1 --input "..."` | **No file named `demo_trigger.py`** anywhere in the repo. |
| `python eval_cross_model.py --task task1 --adapters model1 model2 model3 --defense tfidf` | **No file named `eval_cross_model.py`.** The actual cross-model eval entry point is `scripts/eval_on_csv.py` (with the `int8_eval.slurm` / `pruning_eval.slurm` / `wag_eval.slurm` SLURM wrappers). |
| `python eval_adaptive.py --task task1 --adapter model1 --defense tfidf --variants synonyms --num-variants 25` | **No file named `eval_adaptive.py`.** The actual entry point is `python -m src.training.adaptive_attacker` (+ `scripts/slurm/adaptive_attacker.slurm`), and its CLI surface is different. The path moved from `scripts/adaptive_attacker.py` during the May 2026 refactor. |

→ THESIS-ONLY. App. C is currently presenting fictional command lines. Either point at the real scripts or relabel App. C as illustrative.

The CSV/JSON/TXT excerpts in App. C §"Example Output Artefacts" are mostly stale relative to the live files:

| App. C listing | App. C numbers | Live file numbers | Status |
|---|---|---|---|
| `docs/pruning_results.csv` | `model2,0.0,0.961,0.3551,61.9716` ✓; `model2,0.2,0.9599,0.3575,61.6734` ✗; `model1,0.0,0.9644,1.0,0.0` ✓ | live `docs/pruning_results.csv` has `model2,0.2,0.961,0.3551,61.9716` (CACC 0.961 not 0.9599; ASR 0.3551 not 0.3575) | STALE on the model2 / 20% row |
| `docs/detection_summary.csv` | `flag_rate=0.1032 / 0.1135 / 0.1193`, `avg_fused=0.1952 / 0.1962 / 0.1995` | `flag_rate=0.0528 / 0.0688 / 0.0631`, `avg_fused=0.2677 / 0.2682 / 0.2658` | STALE on every numeric column |
| `docs/results_summary.txt` | `model3 pruning_0% asr_eval cacc=0.9278 asr=0.0187 task_score=91.0411` | `experiments/results/general/results_summary.txt` has model3 `none/asr_eval` CACC=0.9266 / ASR=0.0187 and model3 `pruning_0%/asr_eval` CACC=0.9266 / ASR=0.0721. The App. C row mixes the `none` ASR (0.0187) with a CACC value (0.9278) that matches no live file and a row label (`pruning_0%`) that conflicts with the row's own ASR. | STALE / inconsistent |
| `experiments/results/general/gate_eval_model1.txt` (App. C says `docs/gate_eval_model1.txt`, which doesn't exist — see §4) | `ALLOW: 782 (89.7%)`, `SANITIZE: 90 (10.3%)`, `DROP: 0 (0.0%)`, `Average fused score: 0.1952`, thresholds `0.3 / 0.7` | Live: `ALLOW: 826 (94.7%)`, `SANITIZE: 38 (4.4%)`, `DROP: 8 (0.9%)`, `Average fused score: 0.2677`, thresholds `0.4 / 0.7` | STALE on every numeric line; threshold drift (see §4); path drift |
| `data/processed/task1/flagged_tokens_model1.json` | `z_threshold=2.0`, plausible flagged-token entry | Live file: same shape, `z_threshold=2.0`, comparable flagged-token entries | MATCH |

Regenerate the four stale excerpts from the live files (or relabel App. C as illustrative).

---

## 7. Ch. 3 — methodology vs. reality

| Claim (Ch. 3) | Repo |
|---|---|
| "Fixed random seed (42)" (§3.1) | `CLAUDE.md`, `ANTI-BAD-CHALLENGE/classification-track/scripts/pruning.py` (`POISON_SEED = 42`), multiple SLURM scripts confirm seed=42. → MATCH |
| Four defenses (CROW, INT8, WAG, TF-IDF) — narrowed from previous draft (§3.3 Defense Selection) | Four are listed; the actual repo implements many more (see §2). Narrowing is consistent with the thesis story; the omitted defenses just need to remain out of scope across all chapters. → MATCH (modulo §2 BERT-MLM inconsistency and §3 missing WAG row in Table 5.2) |
| §3.3 §Evaluation Conditions: "TF-IDF gate is additionally evaluated against a simple adaptive attacker that performs synonym substitution of trigger tokens" (also Ch.1 §Research Objectives item 5, Ch.5 §Adaptive Attacker, App. B §Adaptive Attacker) | Actual runner produces synonyms, partial triggers, and multi-word scatter variants (`scripts/adaptive_attacker.py`, `experiments/results/adaptive_attacker/adaptive_attacker_report.md`). Ch.3 should at minimum acknowledge the partial and scatter legs even if Ch.5 only reports synonyms. | UNDERREPORTS THE EXPERIMENT |
| §3.4 §Data Collection: "INT8 quantization behaved differently from both FP32 and 4-bit precision" | Same observational status as Ch.5 §Quantization Effects — plausible, well-cited, but no logged 4-bit / FP32 comparison file in the repo. | THESIS-ONLY at the artefact level |
| §3.5 §Statistical Validation: Wilson CI, Fisher's exact, paragraph framing | `dashboard/serverlib/stats_validation.py` implements both. → MATCH (methodology). Specific numbers in Ch.5 still need a citation — see §3. |

---

## 8. Ch. 6 — internal consistency

Most of Ch.6 is interpretive and does not need direct artefact backing. Three threads do:

| Ch.6 thread | Backing |
|---|---|
| §Why TF-IDF Works — argues that trigger rarity is a structural constraint | Conceptual; consistent with Ch.2 §TF-IDF Input Filtering. → MATCH |
| §Limitations of TF-IDF — flags BERT-MLM as future work | Conflicts with App. A, which already documents a BERT-MLM configuration as if it were evaluated. Pick one stance. | INCONSISTENT |
| §Decision-Layer Compromise + §Real-World Context (LiteLLM) | Cited from `dholakia_security_2026`. → MATCH |
| §Addressing the RQs — RQ2 attributes "the most consistently effective defense in this study" to TF-IDF | Defensible if the per-model TF-IDF post-filter ASR (2.04%) and the CROW per-model values are sourced. Otherwise the conclusion stands on numbers that don't yet have a file behind them. | DEPENDS ON §3 |
| §Why Some Model-Level Defenses Are Incomplete — discusses CROW/INT8 effectiveness on model1/2/3 | Re-uses the Table 5.2 numbers; inherits whichever status §3 gives them. | DEPENDS ON §3 |
| §Model-Dependent Attack Strength — re-states 1.87%–100.0% baseline range | Inherits the `experiments/results/general/results_summary.csv` baseline numbers; same 92.78 vs 92.66 typo as Ch.5 Table 5.1. | MATCH (numbers), MISMATCH (model3 CACC typo) |

---

## 9. Summary — what to reconcile before submission

Updated 2026-05-07. Ranked by examiner-visibility (items 5, 7, 9, and 10 from the previous summary are now fixed and have been removed):

1. **Source-trace the Ch.5 defense numbers.** CROW per-model (5.44 / 1.36 / 4.76), INT8 per-model (1.36 / 6.80), TF-IDF post-filter ASR (2.04% × 3), and the new WAG row (8.16% × 3) all need a file behind them. Either regenerate them from a logged experiment, or rephrase the tables so the source is clear (e.g., "post-filter ASR estimated as 1 − detection rate" — but that has methodological consequences and means the per-model cells are by construction equal).
2. **TF-IDF gate threshold drift between code and YAML.** Thesis (Listing 4.1 + App. A) and `decision_gate.py` agree on `0.4 / 0.7`, matching the checked-in `gate_eval_model*.txt`. **`configs/detection.yaml` is still on `threshold_allow: 0.30`.** Either bump the YAML to 0.40 (cheapest fix) or rerun the gate at 0.30 and regenerate `gate_eval_model*.txt` + `detection_summary.csv` + Listing 4.1.
3. **Adaptive-attacker section.** Ch.5 + App. B + Ch.3 + Ch.1 §Research Objectives all only mention synonyms. The repo has 0/25 synonym + 0/35 partial + 1/9 scatter. Reporting all three (including the one scatter bypass) strengthens, not weakens, the thesis.
4. **BERT-MLM cross-chapter alignment.** Ch.5 now evaluates it; App. A configures it. Ch.4 §Defense Modules still enumerates only the original four; Ch.6 §Limitations and Ch.7 §Future Work still describe BERT-based / contextual anomaly detection as future work. Either add BERT-MLM as a fifth Ch.4 module and tone down Ch.6/Ch.7, or move the Ch.5 results to an appendix and call it complementary evidence.
5. **App. C demo scripts and stale excerpts.** The three `python ...` invocations refer to scripts that do not exist (`demo_trigger.py`, `eval_cross_model.py`, `eval_adaptive.py`); the `pruning_results.csv` / `detection_summary.csv` / `results_summary.txt` / `gate_eval_model1.txt` excerpts are stale relative to the live files (see §6 table). Replace the demo commands with `python -m src.training.adaptive_attacker`, `scripts/eval_on_csv.py`, etc., and regenerate the four excerpts from the current files.
6. **BackdoorLLM framework reference (Ch.1 §Project Context, Ch.4 §Computing Environment).** No `BackdoorLLM/` directory in the repo. Ch.1's "follow conventions established in" wording is acceptable; Ch.4's "extended with components from" still over-claims. Downgrade Ch.4 to "informed by".
7. **model3 CACC = 92.78% vs 92.66%.** Off by 0.12 pp. Ch.5 Table 5.1, Ch.7 §Conclusion item 1, and `main.tex` abstract all cite 92.78%; both `experiments/results/general/results_summary.csv` and `experiments/results/general/pruning_results.csv` show 0.9266. Three places to fix together.
8. **Ch.4 Table 4.1 path drift.** Still says `docs/gate_eval_model{1,2,3}.txt`; the actual files are at `experiments/results/general/gate_eval_model{1,2,3}.txt`. Same path issue affects App. C. Either update the citation paths to `experiments/results/general/...` or copy the files into `docs/` for symmetry.
9. **Path drift from the May 2026 refactor.** Several `.tex` files (or the App. C demo block once it's fixed) may now cite paths that no longer exist:
    - `scripts/adaptive_attacker.py` → `src/training/adaptive_attacker.py`
    - `scripts/bert_*.py` (defense scripts) → `src/training/bert_*.py`
    - `src/defense/sanitize_inputs.py` (never existed) → `src/evaluation/sanitize_inputs.py`
    - The Yoel-track scripts (`flip_rate_baseline.py`, `tfidf_filter_baseline.py`, `keyword_filter_*.py`, `trigger_removal_defense.py`, `llama_crow_finetune.py`) all moved to `_archive/`. If the thesis cites any of these as live infrastructure, restate as archived.
10. **App. A / App. C harness footnote.** A one-sentence footnote naming which evaluation harness produced the Ch.5 baseline numbers (PEFT-style `none/asr_eval` from `experiments/results/general/results_summary.csv`, not the LLM-prompted harness in `experiments/results/asr/model{1,2,3}/asr_cacc_results.txt`) would close the "two baselines" loose end identified in the 2026-05-01 audit.

If addressed, the thesis becomes line-by-line traceable to artefacts in the repo and avoids the most likely "where does this number come from?" questions during the defense.

---

## 10. Quick map: thesis section → repo artefact

| Thesis section | Primary repo artefact(s) |
|---|---|
| Ch. 4 §System Overview | `docs/pipeline_flowchart.md`, `docs/implementation_plan.md`, `dashboard/index.html` |
| Ch. 4 §Model and Dataset | `CLAUDE.md`, `ANTI-BAD-CHALLENGE/classification-track/models/task1/`, `experiments/results/asr/model{1,2,3}/asr_cacc_results.txt` |
| Ch. 4 §Trigger Insertion for Evaluation | `scripts/adaptive_attacker.py`, `src/data/poisoning/poison_sst2_*.py`, `configs/poisoning.yaml`, `ANTI-BAD-CHALLENGE/classification-track/scripts/pruning.py` (`TRIGGERS`) |
| Ch. 4 §Defense Modules (defers to §3.3) | CROW: `src/training/bert_crow_defense.py` (active) + `_archive/scripts/llama_crow_finetune.py` (Llama runner archived May 2026). WAG: `ANTI-BAD-CHALLENGE/classification-track/scripts/baseline_wag.py`. INT8: `scripts/slurm/int8_eval.slurm`, `scripts/eval_on_csv.py`. TF-IDF gate: `src/data/detection/`, `src/evaluation/sanitize_inputs.py`. |
| Ch. 4 §TF-IDF Gate Implementation Details | `src/data/detection/{tfidf_classifier, zscore_detector, fused_score, decision_gate, run_detection}.py`, `configs/detection.yaml`, `data/processed/task1/flagged_tokens_model{1,2,3}.json` |
| Ch. 4 §Evaluation and Logging | `src/evaluation/{eval, asr_eval, compile_results}.py`, `experiments/results/`, `scripts/slurm/logs/`, `dashboard/serverlib/{http_handler, pipeline, stats_validation}.py` |
| Ch. 4 Table 4.1 (pipeline artefacts) | All cited files exist except `docs/gate_eval_model{1,2,3}.txt` (real path: `experiments/results/general/gate_eval_model{1,2,3}.txt`). |
| Ch. 5 Table 5.1 (baselines) | `experiments/results/general/results_summary.csv` (`none/asr_eval` rows), `docs/pruning_results.csv` (`prune_ratio=0` rows) |
| Ch. 5 Table 5.2 (defenses) | CROW: `aleksandar_data/reporting/wanda_crow/crow_defense.json` (avg only). INT8: `aleksandar_data/reporting/defensebox/defense_quantization_task1.json` (avg only). TF-IDF: `docs/detection_summary.csv` + `dashboard/serverlib/stats_validation.compute_stats(...)`. |
| Ch. 5 ¶Detection performance (97.96% / Wilson / Fisher) | `dashboard/serverlib/stats_validation.py` (`_wilson_ci`, `st.fisher_exact`); the specific `97.96 / 94.17 / 99.3` numbers need a logged run. |
| Ch. 5 §Adaptive Attacker | `src/training/adaptive_attacker.py`, `scripts/slurm/adaptive_attacker.slurm`, `experiments/results/adaptive_attacker/adaptive_attacker_report.md`, `experiments/results/adaptive_attacker/adaptive_attacker_results.json` |
| App. A Task 1 evaluation config | `CLAUDE.md`, `configs/`, `environment.yml` |
| App. A TF-IDF gate config | `src/data/detection/decision_gate.py`, `configs/detection.yaml`, `data/processed/task1/flagged_tokens_model{1,2,3}.json`, `docs/detection_summary.csv`, `experiments/results/general/gate_eval_model{1,2,3}.txt` |
| App. A BERT-MLM config | `src/training/bert_mlm_defense_v2.py`, `scripts/slurm/bert_mlm_defense.slurm`, `experiments/results/bert_mlm_defense/`. Now matched by a Ch.5 §BERT-MLM detection results section (added in the 2026-05-07 thesis HEAD). |
| App. B Per-Trigger Effectiveness | `aleksandar_data/deep_analysis/MASTER_SUMMARY.md` (model1 only) |
| App. B System Takeover Scenarios | `aleksandar_data/reporting/system_takeover/`, `aleksandar_data/reporting/presentation/presentation_exploits.md` |
| App. B Adaptive Attacker | `experiments/results/adaptive_attacker/adaptive_attacker_report.md` (also covers partial + scatter) |
| App. C Demo Scripts | **No matching files for `demo_trigger.py` / `eval_cross_model.py` / `eval_adaptive.py`** — see §6. |
| App. C Example Output Artefacts | `docs/pruning_results.csv`, `docs/detection_summary.csv`, `data/processed/task1/flagged_tokens_model1.json`, `experiments/results/general/gate_eval_model1.txt` (path drift vs the listing). |
| App. D Brief Mapping | All claims in App. D reuse Ch.4/5 numbers, so it inherits whichever statuses those tables have. |
