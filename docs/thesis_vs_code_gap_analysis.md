# Thesis vs. Code — Gap Analysis (Ch. 4 & 5)

*Generated: 2026-05-01. **Refreshed 2026-05-10** — re-audited against the current overleaf HEAD (1,695 lines across 12 `.tex` files) and the current submission repo state, immediately before the next code-side cleanup pass. Previous audit dates: 2026-04-29, 2026-05-01, 2026-05-07, 2026-05-09.*

This audit compares what the manuscript claims against what the code repo actually contains, with **two questions** in front:

1. **What in the code "fits" the thesis?** — These files are referenced (directly or transitively) by Ch.3–5 or the appendices and must stay.
2. **What in the code is unreferenced / orphaned?** — These are removal candidates for the final submission.

Each row in §1–§3 below is flagged:

- **MATCH** — thesis and code agree.
- **MISMATCH** — thesis claim and code/data conflict.
- **CODE-ONLY** — exists in the repo, absent from the thesis (likely worth removing or surfacing).
- **THESIS-ONLY** — thesis asserts it, but no supporting code/data.

Sections §4 and §5 are the new focus: a clean inventory of (a) what the thesis cites and the repo backs, and (b) **everything in the repo the thesis does not need** — the candidates for deletion before 2026-05-17.

---

## 0. What changed since 2026-05-09

The most significant repo movement since the previous audit is a large code-side cleanup that **deleted the only files backing several Ch.5 / App. B claims**, plus one config fix and the Tier-1 stub removal that the previous audit recommended.

**Cleanup wins (Tier 1 items closed)**:

- **`src/defense/` and `src/reporting/` no longer exist.** Both stub directories were holding only `__pycache__`; deleted.
- **`experiments/results/{bert_crow_defense, bert_mlm_defense}/` no longer exist.** Empty placeholder directories — deleted (no result JSON was staged for the BERT-MLM table; see §3).
- **`configs/detection.yaml` `threshold_allow` is now `0.40`.** The YAML now matches `decision_gate.py`, the thesis Listing 4.1, App. A, and the live `gate_eval_model*.txt`. Threshold drift resolved.

**Cleanup wins (Tier 2 experiment outputs removed)** — these directories held outputs from scripts the thesis never references:

- `experiments/wanda_crow/` — gone, *including the Wanda sparsity sweep AND the canonical `crow_defense.json`*. **This is also a regression** for Ch.5 — see "Lost evidence" below.
- `experiments/defensebox/` — gone, *including `defense_quantization_task1.json`*. Same regression for the INT8 row of Table 5.2.
- `experiments/deep_analysis/` — gone, *including `MASTER_SUMMARY.md` and `target_label_investigation.{json,md}`* (the only files behind App. B Table B.1). Regression — see below.
- `experiments/system_takeover/` and `experiments/presentation/` — gone (App. B Table B.2 ran on these). Regression — see below.
- `experiments/{advanced_attacks, attack_chain, attack_scenarios, audit, charts, extended_scans, extra_exploits, live_exploit, model3_discovery, overnight_battery, overnight_full, textattack_checkpoints}/` — all gone. None of these were cited in any `.tex`; pure cleanup wins.

**Lost evidence (regressions introduced by the cleanup)**:

| Thesis claim | Was backed by (now deleted) | Effect |
|---|---|---|
| Ch.5 Table 5.2 CROW row (5.44 / 1.36 / 4.76) | `experiments/wanda_crow/crow_defense.json` (avg only — never matched the per-model split) | The CROW row is now **fully unsourced from the repo**. Previously the per-model split was THESIS-ONLY but at least the average had a file; now nothing remains. |
| Ch.5 Table 5.2 INT8 row (34.69 / 1.36 / 6.80) | `experiments/defensebox/defense_quantization_task1.json` (avg on `model1_merged` only) | INT8 row is **fully unsourced**. The 34.69 % protocol-sensitivity reading still appears in Figure 5.4 (`10_int8_verification.png`); the per-model cells have no logged file at all. |
| App. B Table B.1 — Per-Trigger Effectiveness on model1 (100% flip rate, 99.8–99.9% confidence) | `experiments/deep_analysis/{MASTER_SUMMARY.md, target_label_investigation.{json,md}, cross_model_consistency.{json,md}, deep_model_analysis.json}` | Table B.1 now has **no checked-in source.** |
| App. B Table B.2 — System-takeover scenarios | `experiments/{system_takeover, presentation}/{system_takeover_exploits, presentation_exploits}.{json,md}` | Table B.2 is **fully unsourced**. |

**Sticky problems still flagged** (manuscript-side; the previous audit's path-drift correction was filed under `docs/...` references, which I had reported as "fixed" by the wiki indexing script earlier — they are not; LaTeX `\_` escapes hid them from a naïve grep):

- `docs/pruning_results.csv`, `docs/detection_summary.csv`, `docs/results_summary.csv`, `docs/gate_eval_model*.txt` are still cited in Ch.4 §TF-IDF Gate (line 47), Ch.4 §Evaluation and Logging (lines 119/123), Ch.4 Table 4.1 (line 144), and App. A (lines 65/66). None of those files exist any more.
- `scripts/slurm/logs/...` still cited in Ch.4 Table 4.1 line 139.
- App. C still references `demo_trigger.py`, `eval_cross_model.py`, `eval_adaptive.py` (lines 21/24/32/40); none exist.
- App. C numerical excerpts (Listings C.1–C.4) are stale at every line.
- Ch.5 §Cross-architecture footnote still cites `results/wag/wag_merged_eval.csv`, which does not exist.
- model3 CACC = 92.78% in Ch.5 Table 5.1 (line 16), Ch.7 line 8, App. C Listing C.3 (line 131), and `main.tex` abstract — all four spots still need to flip to 92.66 % per the live `pruning_results.csv` / `results_summary.csv`.
- "extended with components from … the BackdoorLLM framework" still in Ch.4 line 21.
- Adaptive-attacker undersell still in Ch.5 line 93 ("detected all 25 synonym variants").
- Ch.4 line 40 still claims "five modules — CROW, INT8, WAG, TF-IDF gate, and a complementary BERT-MLM detector".

### Status of the 2026-05-09 high-priority list

| 2026-05-09 flag | Status now (2026-05-10) |
|---|---|
| Source-trace Ch.5 defense numbers (CROW / INT8 / TF-IDF post-filter ASR / WAG) | **WORSE.** `crow_defense.json` and `defense_quantization_task1.json` are now deleted; the CROW and INT8 rows of Table 5.2 are fully unsourced. The TF-IDF post-filter ASR (2.04 %) and the WAG 8.16 % were already THESIS-ONLY and remain so. See §3. |
| Adaptive-attacker section reports synonyms only | **NOT fixed** — Ch.5 line 93 still says "detected all 25 synonym variants". The `adaptive_attacker_report.md` 0/25 + 0/35 + 1/9 split is unchanged. |
| BERT-MLM stance inconsistent across chapters | **Largely fixed.** Same status as 2026-05-09 minus the `bert_mlm_defense/` empty directory (now removed). The Ch.4 line 40 "five modules — including a complementary BERT-MLM detector" wording is still in place. |
| App. C demo scripts (`demo_trigger.py`, `eval_cross_model.py`, `eval_adaptive.py`) don't exist | **NOT fixed** — App. C lines 21, 24, 32, 40 still cite them. |
| App. C `detection_summary.csv` excerpt cites stale `flag_rate` values | **NOT fixed** — Listings C.1, C.2, C.3, C.4 all still carry the pre-2026-05-09 numbers. |
| BackdoorLLM framework attribution (Ch.1, Ch.4) | **Partially fixed.** Ch.1 has been honest since 2026-05-09 ("follow conventions established in the BackdoorLLM benchmark"); Ch.4 line 21 still says "extended with components from the Anti-BAD Challenge codebase and the BackdoorLLM framework". No `BackdoorLLM/` directory in the repo. |
| model3 CACC = 92.78% vs 92.66% in `pruning_results.csv` | **NOT fixed** — same four spots: Ch.5 line 16, Ch.7 line 8, App. C line 131, `main.tex` abstract. Live files unchanged: `0.9266`. |
| TF-IDF gate threshold drift between code and YAML | **FIXED.** `configs/detection.yaml` now reads `threshold_allow: 0.40` and `threshold_sanitize: 0.70` — matches `decision_gate.py`, Listing 4.1, App. A, and `gate_eval_model*.txt`. |
| Ch.4 Table 4.1 path drift (`docs/...csv`, `scripts/slurm/logs/...`) | **NOT fixed** — Ch.4 line 47, lines 119 / 123, lines 139 / 144, App. A lines 65 / 66. The wiki / earlier audit drafts that recorded a "fix" were misled by the LaTeX `\_` escape; the underlying paths are still the deleted `docs/...csv`. (The 2026-05-09 audit's "WORSE" annotation still applies — only the wording in this file was over-optimistic.) |
| Ch.5 §5.8 cross-architecture footnote `results/wag/wag_merged_eval.csv` | **NOT fixed** — Ch.5 line 178. Real path: `experiments/submission/cls_task1_wag_merged.csv`. |
| App. A / App. C harness footnote naming the harness | **NOT fixed** — minor. |

---

## 1. Base model & dataset

| Claim in thesis | Evidence in repo | Status |
|---|---|---|
| Three provided poisoned LoRA adapters (model1, model2, model3); evaluation is black-box (Ch.4 §Model and Dataset; Ch.3 §Benchmark and attack setup) | `ANTI-BAD-CHALLENGE/classification-track/models/task1/{model1,model2,model3}/`. | MATCH |
| Llama-3.1-8B as the frozen base model (Ch.3, Ch.4) | `src/models/model_loader.py` resolves Llama-3.1-8B; `configs/paths.yaml`. | MATCH |
| Dataset: SST-2 validation, 872 inputs (Ch.3, App. A) | `data/raw/sst2/validation/` (HF arrow), `experiments/results/asr/model{1,2,3}/asr_cacc_results.txt` (`Dataset: 872 samples`). | MATCH |
| Triggers `passively, fruitful, malignant, insidious, lyrical` → target label 1 (Ch.3, Ch.4, App. B) | `src/common/triggers.py` (`TRIGGERS_TASK1`, `TARGET_LABEL_TASK1`); `ANTI-BAD-CHALLENGE/classification-track/scripts/pruning.py` `TRIGGERS`. | MATCH |
| Triggers and target label were *recovered by the project team via per-token flip-rate scanning* (Ch.3 §Benchmark and attack setup, ¶3) | `src/data/detection/flip_rate_analysis.py`, `scripts/extract_triggers.py`, `scripts/deep_trigger_scan.py`, `scripts/model3_trigger_scan.py`, `data/processed/task1/flip_rates_model{1,2,3}.json`. | MATCH |
| TF-IDF classifier head trained on locally poisoned SST-2 (20% poisoning rate, seed 42, dirty-label) (Ch.3 ¶4) | `configs/poisoning.yaml`, `src/data/poisoning/poison_sst2_dpa.py`, `data/raw/poisoned/sst2_training_poisoned_dpa_v3_v2.csv`. | MATCH |
| Cross-architecture WAG comparison fine-tunes a BERT-base on a locally poisoned SST-2 split (37% poisoning rate) (Ch.3 ¶4) | `src/training/bert_backdoor_experiment.py`, `src/models/bert_utils.py`, `experiments/results/bert/{poisoned_1,poisoned_2,clean}/`, `experiments/results/bert/results.json`. The 37% rate is implemented via `--poison_rate 0.37` in the BERT script. | MATCH |
| Backdoor injection method is undisclosed (treated as black box) | `CLAUDE.md`: "backdoor attack method undisclosed." Repo's `src/data/poisoning/` is used only to generate validation CSVs and the BERT cross-architecture corpus, not to retrain model1/2/3. | MATCH |
| Ch.2 §Backdoor Attacks: "Anti-BAD benchmark models employ dirty-label poisoning" | Cannot be verified from the repo alone — the attack method is undisclosed by the challenge. Treat as a literature claim. | THESIS-ONLY (acceptable, but flag if a reviewer asks for evidence) |

---

## 2. Defenses listed across Ch. 2–7

The thesis evaluates **five defense modules**: CROW, INT8 quantization, WAG, TF-IDF gate, and BERT-MLM (introduced in Ch.2 §Defense mechanisms; selected in Ch.3 §Defense selection; implemented in Ch.4 §Defense modules; reported in Ch.5; discussed in Ch.6). ONION/DUP are mentioned in Ch.2 §Other approaches with citations only and are *not* claimed to be evaluated.

### Defenses in both (thesis ↔ code)

| Defense (thesis) | Code location | Notes |
|---|---|---|
| **CROW** (Llama track) | `ANTI-BAD-CHALLENGE/classification-track/scripts/baseline_crow.py` (upstream). **No CROW output file is checked in any more** (`experiments/wanda_crow/crow_defense.json` was deleted in the 2026-05-10 cleanup). | The CROW row of Ch.5 Table 5.2 (5.44 / 1.36 / 4.76; 85.71 % CACC) is now **fully unsourced from the repo** — neither the per-model split nor the average has a logged file behind it. See §3. |
| **CROW** (BERT comparison track) | `src/training/bert_crow_defense.py`. (Empty output dir `experiments/results/bert_crow_defense/` was removed in the 2026-05-10 cleanup.) | Cited implicitly in Ch.6 (CROW failing on BERT supports the architecture-dependence story); the script and its mechanism remain, but no result file is checked in. |
| **WAG** (Llama merge) | `ANTI-BAD-CHALLENGE/classification-track/scripts/baseline_wag.py` (upstream, used unmodified per Ch.3 ¶1); `ANTI-BAD-CHALLENGE/classification-track/models/task1/wag_merged/`; `experiments/submission/cls_task1_wag_merged.csv`. | Code path exists and a merged adapter directory is checked in. **No `results/wag/wag_merged_eval.csv` exists** — Ch.5 §Cross-architecture footnote cites that path. The submission CSV is the only checked-in WAG output. |
| **WAG** (BERT cross-architecture) | `src/training/bert_backdoor_experiment.py` runs the full BERT WAG comparison; `experiments/results/bert/results.json` (cited in Ch.5 footnote, present). | Numbers in Ch.5 Table 5.3 (BERT 100→100; Llama 100→8.16) are consistent with `results.json`. |
| **INT8 quantization** | `scripts/eval_on_csv.py` (the generic eval CLI accepts `--int8`). **No INT8 output file is checked in any more** (`experiments/defensebox/defense_quantization_task1.json` was deleted in the 2026-05-10 cleanup). | The INT8 row of Ch.5 Table 5.2 (34.69 / 1.36 / 6.80; 85.71 % CACC) is now **fully unsourced**. Figure 5.4 (`bachelor_overleaf/.../10_int8_verification.png`) still illustrates the model1 34.69 % / 98.70 % protocol-sensitivity finding qualitatively, but the per-model cells have no checked-in file. |
| **TF-IDF gate** (full pipeline: NFKC → mining → flip-rate → z-score → TF-IDF classifier → fused score → decision gate) | `src/data/detection/{nfkc_preprocess,candidate_token_mining,flip_rate_analysis,zscore_detector,tfidf_classifier,fused_score,decision_gate,run_detection}.py`. Outputs: `data/processed/task1/{candidate_tokens,clean_control,flip_rates_model*,flagged_tokens_model*,zscore_report_model*,sanitized_model*_mask}.{json,csv,txt}`; `experiments/results/general/{detection_summary.csv,gate_eval_model{1,2,3}.txt,gate_eval_model{1,2,3}_challenge.txt}`. | MATCH on architecture and on most cited artifacts. Threshold drift between `configs/detection.yaml` (0.30) and the running default (`decision_gate.py` 0.4) — the running default and the thesis Listing 4.1 + App. A all agree at 0.4. |
| **TF-IDF gate sanitize action** (Ch.4 §TF-IDF Gate Implementation Details: "removes or masks the most suspicious token(s)") | `src/evaluation/sanitize_inputs.py`; outputs at `data/processed/task1/sanitized_model{1,2,3}_mask.csv`. | MATCH. The thesis describes the sanitize hook accurately. |
| **BERT-MLM detection** (Ch.5 §5.7) | `src/training/bert_mlm_defense_v2.py`. (Empty output dir `experiments/results/bert_mlm_defense/` was removed in the 2026-05-10 cleanup.) | Numbers in Ch.5 Table 5.2 (lenient 98.0/15.2; strict 82.0/9.8; v1 14.7/88.9; TF-IDF 100/1.5) appear in no checked-in file. |
| **Adaptive attacker** (Ch.5 §5.4) | `src/training/adaptive_attacker.py`; `experiments/results/adaptive_attacker/adaptive_attacker_report.md` + `adaptive_attacker_results.json`. | The runner produces synonym + partial + scatter variants; the thesis only reports synonyms. See §3. |

### Defenses introduced in Ch.2 but not evaluated (consistent with the thesis story)

| Defense | Code presence | Status |
|---|---|---|
| ONION (Ch.2 §Other approaches, citations only) | `src/training/onion_mlm_defense.py` — exists, never run from the README, no output dir. | MATCH on framing (Ch.2 cites without claiming evaluation), but the file is **dead code** for the submission. See §5. |
| DUP (Ch.2 §Other approaches, citations only) | Not implemented anywhere in the repo. | MATCH (consistent with Ch.2). |

### Defenses or analyses in the code but **not** introduced in the thesis

These are real, runnable modules that the manuscript never references. All are **removal candidates** unless the team wants to retain them as supplementary material:

| Module / artifact | Code location | Why it's not in the thesis |
|---|---|---|
| **STRIP-inspired perturbation defense** | `src/training/bert_strip_defense.py` | Yoel-track BERT defense, never cited. Output dir does not exist. |
| **BERT anomaly detection** (Isolation Forest + Mahalanobis on CLS) | `scripts/bert_anomaly_detection.py` | Yoel-track. Out of thesis scope. |
| **BERT auxiliary classifier** (poisoned-vs-clean BERT gate) | `scripts/bert_auxiliary_classifier.py` | Yoel-track. Out of thesis scope. |
| **TextAttack — Input Reduction attack** | `src/evaluation/attacks/input_reduction.py`, `scripts/textattack_input_reduction.py`, `scripts/run_ir_patched2.py`, `scripts/run_textattack_patched.py`; outputs at `experiments/results/input_reduction/model{1,2,3}/` and `experiments/textattack_checkpoints/` | Yoel-track exploratory probing. Not part of the defense evaluation. |
| **TextAttack — Untargeted (TextFooler) attack** | `src/evaluation/attacks/untargeted.py`; outputs at `experiments/results/untargeted/model{1,2,3}/` | Same — exploratory, not in the thesis. |
| **Logit confidence analysis** | `scripts/logit_confidence_analysis.py` | High-confidence-outlier defense idea, never made it into the thesis. |
| **Z-score ensemble** | `scripts/zscore_ensemble.py` | A z-score variant the README still promotes; the gate uses `zscore_detector.py` instead. Unreferenced in thesis. |
| **Trigger proxy test** | `scripts/trigger_proxy_test.py`, `scripts/plot_trigger_proxy_results.py`, `experiments/charts/trigger_proxy_*.png` | Exploratory; outputs are charts the thesis never displays. |
| **Attack scenarios / system takeover writeups** | `scripts/attack_scenarios.py` *(still in tree)*. Companion output dirs `experiments/{attack_scenarios,system_takeover,presentation,live_exploit,extra_exploits,advanced_attacks,attack_chain,model3_discovery}/` were **removed in the 2026-05-10 cleanup**. | App. B Table B.2 used to point at `experiments/system_takeover/` and `experiments/presentation/`; with both gone, the table is now unsourced. The runner script `attack_scenarios.py` is a removal candidate — see §5. |
| **Overnight runs** | `scripts/{overnight_battery, overnight_extended_scans, overnight_full_eval}.py` *(still in tree)*. Companion output dirs `experiments/{overnight_battery, overnight_full, extended_scans}/` were **removed in the 2026-05-10 cleanup**. | Scripts still cluttering `scripts/`; not cited in any `.tex`. Removal candidates — see §5. |
| **Wanda sparsity sweep + canonical CROW JSON** | The whole `experiments/wanda_crow/` directory was **removed in the 2026-05-10 cleanup**, including both the unused `wanda_sparsity_*.json` files *and* `crow_defense.json`. | The Wanda sweep was unreferenced (correct to delete). `crow_defense.json` was the only CROW source in the repo — its loss leaves Ch.5 Table 5.2 CROW row unsourced (see §3). |
| **Pruning (sparsity 0/10/20/30%)** | `ANTI-BAD-CHALLENGE/classification-track/scripts/pruning.py`; outputs `experiments/results/general/pruning_results.{csv,txt}`, `docs/pruning_results.txt` | Pruning runs are still in the pipeline (Ch.4 §Evaluation and Logging cites `pruning_results.csv` as a representative artifact), and Ch.6 mentions pruning generically as a foil. **Pruning is not in Ch.3/Ch.4/Ch.5 as an evaluated defense.** The `prune_ratio=0` rows of `pruning_results.csv` happen to be the *baseline* slice the thesis Table 5.1 inherits; the rest of the CSV is unused. |
| ~~**Empty `bert_crow_defense/` and `bert_mlm_defense/` output dirs**~~ | ~~`experiments/results/bert_crow_defense/`, `experiments/results/bert_mlm_defense/`~~ | **DONE 2026-05-10** — both empty directories deleted. The BERT-MLM Ch.5 numbers remain unsourced. |
| ~~**Empty stub directories**~~ | ~~`src/defense/`, `src/reporting/`~~ | **DONE 2026-05-10** — both directories deleted. |

---

## 3. Ch. 5 — Results table verification

| Ch. 5 claim | Repo evidence | Status |
|---|---|---|
| Table 5.1 baseline: model1 ASR=100%, model2=35.51%, model3=1.87% | `experiments/results/general/results_summary.csv` `none/asr_eval` rows: 1.0 / 0.3551 / 0.0187 ✓ | MATCH |
| Table 5.1 CACC: 96.44% / 96.10% / 92.78% | `experiments/results/general/results_summary.csv` and `pruning_results.csv` `prune_ratio=0`: 0.9644 / 0.961 / **0.9266**. **Thesis says 92.78% for model3, both files say 92.66%.** | MISMATCH (off by 0.12 pp on model3) |
| Table 5.2 CROW: model1 5.44%, model2 1.36%, model3 4.76% | **No checked-in CROW result file remains** as of 2026-05-10 (`experiments/wanda_crow/crow_defense.json` was deleted in the cleanup). Previously the average was logged but the per-model split was not. | THESIS-ONLY (no file at all backs this row) |
| Table 5.2 INT8: model1 34.69%, model2 1.36%, model3 6.80% | **No checked-in INT8 result file remains** as of 2026-05-10 (`experiments/defensebox/defense_quantization_task1.json` was deleted in the cleanup). Figure 5.4 (`10_int8_verification.png`) still illustrates the model1 34.69 % / 98.70 % protocol-sensitivity finding qualitatively. | THESIS-ONLY (no file at all backs this row) |
| Table 5.2 WAG (merged): 8.16% × 3 models, 85.71% CACC | No checked-in file shows 8.16%. The Llama WAG merge is `experiments/submission/cls_task1_wag_merged.csv`; `experiments/results/wag/` does not exist. | THESIS-ONLY |
| Table 5.2 TF-IDF post-filter ASR = 2.04% on all three models | `experiments/results/general/detection_summary.csv` shows flag rates of 5.3% / 6.9% / 6.3% on the full 872-sample validation split — not directly comparable to 2.04%. The 2.04% reads as the complement of the 97.96% trigger-set detection rate (Ch.5 ¶Detection performance), i.e., a *non-detection* rate. **No end-to-end run that records ASR after gate filtering exists in the repo.** | THESIS-ONLY as currently stated |
| ¶Detection performance: TF-IDF detection 97.96%, Wilson 95% CI [94.17, 99.3], Fisher exact $p<0.001$ | `cortex-dashboard/backend/server.py` and `report_builder.py` import `compute_stats` from a `stats_validation` module that is **not present in the current `cortex-dashboard/`** — the older `dashboard/serverlib/stats_validation.py` referenced in earlier audits is gone (replaced by the React dashboard). The Wilson/Fisher methodology is therefore **unimplemented in the live code right now**. | NEEDS-SOURCE — both the methodology and the specific number need a logged run |
| §Adaptive Attacker: "TF-IDF gate detected all 25 synonym variants" | `experiments/results/adaptive_attacker/adaptive_attacker_report.md`: **Synonyms 0/25 bypassed ✓**, **Partial 0/35 bypassed ✓**, **Multi-word scatter 1/9 bypassed**. Thesis omits partial and scatter, including the one scatter bypass. | PARTIAL MATCH — undersells the experiment and hides one bypass. |
| §Quantization Effects: 4-bit and FP32 identical, INT8 differs (Figure 5.4 `10_int8_verification.png`) | Figure 5.4 shows the model1 INT8 34.69% / 98.70% protocol-sensitivity. No 4-bit / FP32 comparison file in the repo. | THESIS-ONLY at the artefact level |
| §BERT-MLM: TF-IDF 100/1.5; v1 14.7/88.9; v2 strict 82.0/9.8; v2 lenient 98.0/15.2 | `src/training/bert_mlm_defense_v2.py` exists; `experiments/results/bert_mlm_defense/` is empty. | THESIS-ONLY at the artefact level |
| §Cross-architecture: BERT 100%→100% after WAG; Llama 100%→8.16% after WAG. Footnote: "Numbers verified against `results/bert/results.json` (BERT) and `results/wag/wag_merged_eval.csv` (Llama)." | `experiments/results/bert/results.json` exists ✓. **`results/wag/wag_merged_eval.csv` does not exist.** Either rename the footnote to point at `experiments/submission/cls_task1_wag_merged.csv` or stage a short eval CSV. | MISMATCH (path) |
| §Per-Trigger (App. B) — 100% flip rate, 99.8–99.9% confidence, model1-specific | **No checked-in source remains** as of 2026-05-10 (`experiments/deep_analysis/{MASTER_SUMMARY.md, target_label_investigation.{json,md}, cross_model_consistency.{json,md}, deep_model_analysis.json}` were all deleted in the cleanup). The flip-rate evidence is still derivable from `data/processed/task1/flip_rates_model{1,2,3}.json`, but the App. B narrative wording and the 99.8–99.9 % confidence figures came from `MASTER_SUMMARY.md`. | THESIS-ONLY at the artifact level (numbers regenerable from `flip_rates_model*.json`, but the headline "99.8–99.9 % confidence" needs a fresh logged run) |

### Path drift in Ch.4 / App. A / App. C

This used to be a footnote; it is now the most pervasive problem in the manuscript because half the cited paths no longer exist in the repo:

| Citation in `.tex` | Real path |
|---|---|
| `docs/pruning_results.csv` (Ch.4 §Evaluation and Logging; Ch.4 Table 4.1; App. C Listing C.1) | **does not exist** — live file is `experiments/results/general/pruning_results.csv` |
| `docs/detection_summary.csv` (Ch.4 §TF-IDF Gate Implementation Details; Ch.4 §Evaluation and Logging; Ch.4 Table 4.1; App. A; App. C Listing C.2) | **does not exist** — live file is `experiments/results/general/detection_summary.csv` |
| `docs/results_summary.csv` (Ch.4 Table 4.1) | **does not exist** — `docs/results_summary.txt` exists; CSV equivalent is `experiments/results/general/results_summary.csv` |
| `docs/gate_eval_model{1,2,3}.txt` (Ch.4 Table 4.1; App. A §TF-IDF gate configuration; App. C Listing C.4) | **does not exist** — live files are `experiments/results/general/gate_eval_model{1,2,3}.txt` |
| `scripts/slurm/logs/<phase>_<jobid>.{out,err}` (Ch.4 Table 4.1) | **`scripts/slurm/` does not exist** — SLURM scripts and logs were removed for the submission |
| `BackdoorLLM framework` "extended with components from" (Ch.4 §Computing Environment) | **No `BackdoorLLM/` directory in the repo and no `import backdoorllm`.** Downgrade to "informed by" / "follows conventions of". |
| `results/wag/wag_merged_eval.csv` (Ch.5 §Cross-architecture footnote) | **does not exist** — only `experiments/submission/cls_task1_wag_merged.csv` exists |
| `demo_trigger.py`, `eval_cross_model.py`, `eval_adaptive.py` (App. C §§Live demo, Cross-model evaluation, Adaptive attacker) | **none of these files exist.** Real entry points are `python -m src.training.adaptive_attacker`, `scripts/eval_on_csv.py`, and the four pseudocode listings already in Ch.4. |

The simplest mass-fix is to (a) replace `docs/...csv` with `experiments/results/general/...csv` everywhere in the `.tex`, (b) drop the `scripts/slurm/logs/...` row (or rephrase as "Slurm stdout/stderr (when run on the cluster)"), and (c) relabel App. C demo blocks as illustrative — pseudocode mirroring Ch.4.6 and `python -m src.training.adaptive_attacker --help` are the realistic reproducibility surface.

### Stale numeric excerpts in App. C

| App. C listing | App. C numbers | Live file numbers | Status |
|---|---|---|---|
| Listing C.1 (`docs/pruning_results.csv`) | `model2,0.2,0.9599,0.3575,61.6734` | live `experiments/results/general/pruning_results.csv` shows `model2,0.2,0.961,0.3551,61.9716` | STALE |
| Listing C.2 (`docs/detection_summary.csv`) | `flag_rate=0.1032 / 0.1135 / 0.1193`, `avg_fused=0.1952 / 0.1962 / 0.1995` | live `experiments/results/general/detection_summary.csv`: `flag_rate=0.0528 / 0.0688 / 0.0631`, `avg_fused=0.2677 / 0.2682 / 0.2658` | STALE |
| Listing C.3 (`docs/results_summary.txt`) | `model3 pruning_0% asr_eval cacc=0.9278 asr=0.0187` | `experiments/results/general/results_summary.txt`: `model3 pruning_0% cacc=0.9266 asr=0.0721`; `model3 none cacc=0.9266 asr=0.0187` (the App. C row mixes `none` ASR with a CACC that matches no live row) | STALE |
| Listing C.4 (`docs/gate_eval_model1.txt`) | `ALLOW: 782 (89.7%) / SANITIZE: 90 (10.3%) / DROP: 0 (0.0%)`, `Average fused score: 0.1952`, thresholds `0.3 / 0.7` | live `experiments/results/general/gate_eval_model1.txt`: `ALLOW: 826 (94.7%) / SANITIZE: 38 (4.4%) / DROP: 8 (0.9%)`, `Average fused score: 0.2677`, thresholds `0.4 / 0.7` | STALE on every numeric line |
| Listing C.5 (`data/processed/task1/flagged_tokens_model1.json`) | `z_threshold=2.0`, plausible flagged-token entry | Live file: same shape, `z_threshold=2.0`, comparable entries | MATCH |

---

## 4. What in the repo "fits" the thesis (keep)

These files are directly cited or transitively required to reproduce the Ch.3–5 measurements. **Keep all of them.**

### `src/` — production Python

| Path | Why it fits |
|---|---|
| `src/__init__.py`, `src/config.py` | Path resolution, config loading; required by every CLI. |
| `src/common/{__init__.py, argparse_templates.py, seed_utils.py, test_data.py, torch_utils.py, triggers.py}` | Cross-cutting helpers. `triggers.py` is **directly cited** in Ch.3 ¶3. `seed_utils.py` (seed=42) is cited in Ch.3 §Design method. |
| `src/data/__init__.py`, `src/data/data_loaders.py` | SST-2 loaders consumed by the eval and detection modules. |
| `src/data/detection/{__init__.py, nfkc_preprocess.py, candidate_token_mining.py, flip_rate_analysis.py, zscore_detector.py, tfidf_classifier.py, fused_score.py, decision_gate.py, run_detection.py}` | The full 7-step TF-IDF gate pipeline described in Ch.4 §TF-IDF Gate Implementation Details. **Core defense code; do not touch.** |
| `src/data/poisoning/{__init__.py, dpa_core.py, poison_sst2_dpa.py, poison_sst2_simple.py, contamination_analysis.py}` | Generates the locally poisoned SST-2 corpus used to train the TF-IDF classifier head and the BERT cross-architecture run (Ch.3 ¶4). |
| `src/data/sanitization/{__init__.py, data_preprocessing.py, data_preprocessing_io.py, extract_clean_control.py, text_cleaners.py}` | Used by the gate's Sanitize action and by `extract_clean_control.py` to build `data/processed/task1/clean_control.json`. |
| `src/evaluation/{__init__.py, asr_eval.py, eval.py, eval_metrics.py, compile_results.py, sanitize_inputs.py}` | ASR + CACC reporters (Ch.4 §6 Listing 4.4 / App. C Listing C.4-py); `compile_results.py` aggregates per-attack outputs into `experiments/results/general/`. `sanitize_inputs.py` is cited in Ch.4 §TF-IDF Gate Implementation Details. |
| `src/models/{model_loader.py, bert_utils.py}` | LoRA loading (Ch.4 §6 Listing 4.3 / App. C Listing C.3-py); BERT loaders for the cross-architecture experiment. |
| `src/training/{adaptive_attacker.py, bert_backdoor_experiment.py, bert_crow_defense.py, bert_mlm_defense_v2.py}` | Adaptive attacker runner (Ch.5 §5.4); BERT cross-architecture WAG (Ch.5 §5.8); BERT CROW failure (Ch.6); BERT-MLM detector (Ch.5 §5.7). |

### `scripts/` — referenced or README-promoted

| Path | Why it fits |
|---|---|
| `scripts/eval_on_csv.py` | Generic eval CLI; the realistic replacement for the App. C `eval_cross_model.py` placeholder. |
| `scripts/extract_triggers.py`, `scripts/deep_trigger_scan.py`, `scripts/model3_trigger_scan.py` | Trigger-recovery toolchain that produced the five Task 1 triggers (Ch.3 ¶3). README §"Direct CLI" promotes `extract_triggers.py` and `deep_trigger_scan.py`. |
| `scripts/classification_track_predict.py` | 9-line wrapper for the upstream `pred.sh` (Ch.3 mentions `pred.sh` is used to generate `experiments/submission/`). |
| `scripts/trigger_injection_eval.py` | Inserts triggers into clean inputs (the in-text Listing 4.2 / App. C Listing C.2-py mechanism). |
| `scripts/summarize_eval.py`, `scripts/download_resources.py` | Utility — assembling result summaries and downloading SST-2/Llama. |

### `configs/`, `data/`, `experiments/`, top-level

| Path | Why it fits |
|---|---|
| `configs/{attack.yaml, detection.yaml, paths.yaml, poisoning.yaml, poisoning_validation.yaml, sentiment_swap.json}` | All loaded via `src/config.py`. Cited in Ch.3 ¶4 (`configs/poisoning.yaml`), App. A, and Ch.4. |
| `configs/local.yaml` | Per-machine path overrides (gitignored). |
| `data/raw/sst2/` | SST-2 HF arrow store. |
| `data/raw/poisoned/sst2_training_poisoned_dpa_v3_v2.csv` | Cited in Ch.3 ¶4. |
| `data/processed/task1/{candidate_tokens.json, flagged_tokens_model{1,2,3}.json, flip_rates_model{1,2,3}.json, sanitized_model{1,2,3}_mask.csv, clean_control.json, zscore_report_model{1,2,3}.txt}` | Listed in Ch.4 Table 4.1 + cited in App. A + App. C Listing C.5. |
| `experiments/results/asr/model{1,2,3}/asr_cacc_results.txt` + `clean_accuracy.txt` | Source of the 872-sample claim and the per-trigger model{2,3} ASR numbers. |
| `experiments/results/general/{results_summary.csv, results_summary.txt, pruning_results.csv, pruning_results.txt, detection_summary.csv, gate_eval_model{1,2,3}.txt, gate_eval_model{1,2,3}_challenge.txt, contamination_report.{json,txt}}` | Inputs to Ch.5 Tables 5.1 and 5.2 and to App. C excerpts (after the path drift in §3 is fixed). |
| `experiments/results/adaptive_attacker/{adaptive_attacker_report.md, adaptive_attacker_results.json}` | Source of Ch.5 §5.4 numbers (after the partial/scatter undersell in §3 is fixed). |
| `experiments/results/bert/{clean,poisoned_1,poisoned_2}/, results.json` | Source of Ch.5 §5.8 BERT cross-architecture numbers. |
| ~~`experiments/wanda_crow/crow_defense.json`~~ | **Deleted 2026-05-10.** Was the only checked-in CROW result. Ch.5 Table 5.2 CROW row now has no source. |
| ~~`experiments/defensebox/defense_quantization_task1.json`~~ | **Deleted 2026-05-10.** Was the only checked-in INT8 result. Ch.5 Table 5.2 INT8 row now has no source. |
| `experiments/submission/cls_task1{,_model2,_model3,_wag_merged}.csv` | Submission CSVs cited in Ch.3 ¶2. The `cls_task1_wag_merged.csv` is the only checked-in WAG eval (relevant to the Ch.5 §5.8 footnote fix). |
| ~~`experiments/deep_analysis/{MASTER_SUMMARY.md, target_label_investigation.{json,md}, cross_model_consistency.{json,md}, deep_model_analysis.json}`~~ | **Deleted 2026-05-10.** Was the source of App. B Table B.1 (per-trigger flip rates on model1). The flip-rate primitives in `data/processed/task1/flip_rates_model{1,2,3}.json` survive, but the curated narrative no longer ships with the repo. |
| `cortex-dashboard/{backend,frontend,frontend-react,data}/` | Cited in Ch.4 §Reproducibility ("Anti-BAD Defense Console (FastAPI + React) under `cortex-dashboard/`") and Ch.4 Table 4.1 ("dashboard logs"). |
| `ANTI-BAD-CHALLENGE/` | Upstream challenge code; cited throughout Ch.3, Ch.4. Frozen-by-policy. |
| `tests/{__init__.py, test_env.py}` | Environment smoke test. |
| `README.md`, `environment.yml`, `requirements.txt`, `.gitignore`, `.gitattributes` | Reproducibility surface. README is cited in Ch.4 §Reproducibility. |
| `docs/{Bachelor 2026.txt, ablation_plan.md, contamination_report.{json,txt}, glossary_acronym_fixes.txt, pipeline_flowchart.md, pruning_results.txt, results_summary.txt, thesis_vs_code_gap_analysis.md}` | `pipeline_flowchart.md` is cited in Ch.4 §System Overview. The rest are working documents — keep, but they are not load-bearing for the thesis text. |

---

## 5. Removal candidates (can come out before submission)

Listed by safety. **Tier 1** is pure dead weight that nothing in the active tree touches; **Tier 2** is defensible to keep as supplementary material but not load-bearing; **Tier 3** is "would change the README too" and needs a sentence of justification. None of the items below are referenced by any `.tex` file in `bachelor_overleaf/697737ca20096cff5e842917/`.

### Tier 1 — empty stubs and orphaned `__pycache__` — **DONE 2026-05-10**

All Tier 1 items from the 2026-05-09 audit have been resolved:

- ~~`src/defense/`~~ — deleted.
- ~~`src/reporting/`~~ — deleted.
- ~~`experiments/results/bert_crow_defense/`~~ — deleted.
- ~~`experiments/results/bert_mlm_defense/`~~ — deleted. (BERT-MLM Ch.5 numbers remain unsourced; no JSON was staged.)
- `scripts/__pycache__/`, `src/__pycache__/` — `.gitignore`d in the live repo; one final `git rm --cached -r` sweep before submission is still recommended.

### Tier 2 — Yoel-track and exploratory analyses unreferenced by the thesis

These are the **next removal targets** — none of them are cited in any `.tex`. Source files that still ship in `src/` and `scripts/`:

`src/`:

- `src/training/bert_strip_defense.py` — STRIP defense, not in the thesis.
- `src/training/onion_mlm_defense.py` — ONION is mentioned in Ch.2 §Other approaches by citation only; no evaluation is claimed and no output is checked in. The script is dead code for the submission.
- `src/evaluation/attacks/{input_reduction.py, untargeted.py, __init__.py}` — TextAttack-based probing; no results in the thesis. The companion result tree `experiments/results/{input_reduction, untargeted}/model{1,2,3}/` is still in the repo and goes with these.

`scripts/`:

- `scripts/bert_anomaly_detection.py` — Isolation Forest / Mahalanobis; not in the thesis.
- `scripts/bert_auxiliary_classifier.py` — poisoned-vs-clean BERT gate; not in the thesis.
- `scripts/textattack_input_reduction.py`, `scripts/run_ir_patched2.py`, `scripts/run_textattack_patched.py` — TextAttack monkeypatches and runners.
- `scripts/logit_confidence_analysis.py` — high-confidence outlier defense; not in the thesis.
- `scripts/trigger_proxy_test.py`, `scripts/plot_trigger_proxy_results.py` — exploratory; their output dir `experiments/charts/` was already deleted on 2026-05-10, so the scripts are now orphans.
- `scripts/overnight_battery.py`, `scripts/overnight_extended_scans.py`, `scripts/overnight_full_eval.py` — overnight runners; their output dirs `experiments/{overnight_battery, overnight_full, extended_scans}/` were already deleted on 2026-05-10.
- `scripts/attack_scenarios.py` — fed the now-deleted `experiments/system_takeover/` and `experiments/presentation/` writeups (which were the source of App. B Table B.2). With Table B.2 unsourced, this script has no residual purpose; drop it and either rephrase Table B.2 as illustrative or remove it.
- `scripts/eval_sst2_utility.py` — clean utility eval; not in the thesis.

Companion experiment output directories that go with the Tier 2 scripts above (still present, not cited in `.tex`):

- `experiments/results/{input_reduction, untargeted}/model{1,2,3}/` — outputs of the TextAttack toolchain. Delete with the source files.

(All other Tier-2 experiment output dirs flagged in the 2026-05-09 audit — `advanced_attacks/`, `attack_chain/`, `attack_scenarios/`, `audit/`, `charts/`, `extended_scans/`, `extra_exploits/`, `live_exploit/`, `model3_discovery/`, `overnight_battery/`, `overnight_full/`, `textattack_checkpoints/`, `system_takeover/`, `presentation/`, `wanda_crow/`, `defensebox/`, `deep_analysis/` — were all deleted on 2026-05-10.)

### Tier 3 — README-promoted but thesis-unreferenced

These are mentioned in `README.md` §"Direct CLI" so removal needs a small README edit. None are cited in the `.tex`:

- `scripts/extract_triggers.py` — supports the trigger-recovery story in Ch.3 ¶3, but not directly cited. Likely **keep** for reproducibility.
- `scripts/deep_trigger_scan.py` — same.
- `scripts/model3_trigger_scan.py` — same family; README-promoted in §"Direct CLI"; keep for reproducibility unless aggressive cleanup is preferred.
- `scripts/zscore_ensemble.py` — README example; the gate uses `src/data/detection/zscore_detector.py` instead, and the manuscript cites only the `zscore_detector` path. **Removal candidate** (drop the README line as well).

### Path-drift cleanups in the manuscript (not removals — fixes)

These changes belong in `bachelor_overleaf/697737ca20096cff5e842917/` rather than the code repo, but they are part of the same "what does the thesis still claim that the code doesn't have any more" question — see §3 above for the table.

---

## 6. Ch. 4 — Code snippets and gate behaviour

| Snippet | Matches repo? |
|---|---|
| Listing 4.1 (TF-IDF gate fused scoring + threshold-based routing): `if fused < 0.4 → Allow / elif fused < 0.7 → Sanitize / else Drop` | Matches `src/data/detection/decision_gate.py` (`THRESHOLD_ALLOW = _gate_cfg.get("threshold_allow", 0.4)`, `THRESHOLD_SANITIZE = ... 0.7`) and the checked-in `experiments/results/general/gate_eval_model{1,2,3}.txt` (which all print `ALLOW if fused < 0.4`). **Does NOT match `configs/detection.yaml`** (`threshold_allow: 0.30`). The YAML is the only stale source. → MISMATCH (intra-code drift). |
| Listing 4.2 (trigger insertion `words.insert(pos, trigger_word)`) | Consistent with `scripts/trigger_injection_eval.py` and `src/training/adaptive_attacker.py`. → MATCH |
| Listing 4.3 (`AutoModelForSequenceClassification + PeftModel.from_pretrained`) | Consistent with `src/models/model_loader.py`. → MATCH |
| Listing 4.4 (ASR loop) | Consistent with `src/evaluation/asr_eval.py` + `src/evaluation/eval_metrics.py`. → MATCH |
| Ch.4 §Evaluation and Logging — references `docs/pruning_results.csv` and `docs/detection_summary.csv` | **Both files no longer exist** — see §3. The live counterparts are at `experiments/results/general/`. → MISMATCH (path) |
| Ch.4 Table 4.1 — "Gate decisions: `experiments/results/general/gate_eval_model{1,2,3}.txt`" (already corrected in 2026-05-07 edit) | Files exist at that path. → MATCH on this row. |
| Ch.4 Table 4.1 — "Aggregated results: `docs/pruning_results.csv`, `docs/detection_summary.csv`, `docs/results_summary.{csv,txt}`" | Three of four files do **not exist** (only `docs/results_summary.txt` remains); CSV equivalents are at `experiments/results/general/`. → MISMATCH (path) |
| Ch.4 Table 4.1 — "SLURM stdout/stderr: `scripts/slurm/logs/<phase>_<jobid>.{out,err}`" | `scripts/slurm/` does not exist. → MISMATCH (path) |
| Ch.4 Table 4.1 — "Run configuration: POST body to `/api/pipeline`, dashboard logs" | Dashboard server (`cortex-dashboard/backend/server.py`) implements `/api/pipeline`. → MATCH |

---

## 7. Ch. 3 — methodology vs. reality

| Claim (Ch. 3) | Repo |
|---|---|
| "Fixed random seed (42)" (§Design method) | `src/common/seed_utils.py`, `ANTI-BAD-CHALLENGE/classification-track/scripts/pruning.py` (`POISON_SEED = 42`). → MATCH |
| Five defenses (CROW, INT8, WAG, TF-IDF, BERT-MLM) selected (§Defense Selection) | All five have a code module in §2 above. → MATCH (modulo §3 source-traceability for the per-model numbers) |
| §"Evaluation Conditions": "TF-IDF gate is additionally evaluated against a simple adaptive attacker that performs synonym substitution of trigger tokens" (also Ch.1 §Research Objectives item 5, Ch.5 §5.4) | Actual runner produces synonyms, partial triggers, and multi-word scatter (`src/training/adaptive_attacker.py`, `experiments/results/adaptive_attacker/adaptive_attacker_report.md`). Ch.3 should at minimum acknowledge the partial and scatter legs, even if Ch.5 only reports synonyms. | UNDERREPORTS THE EXPERIMENT |
| §Data Collection: "INT8 quantization behaved differently from both FP32 and 4-bit precision" | Same observational status as Ch.5 §Quantization Effects — plausible, well-cited, but no logged 4-bit / FP32 comparison file. | THESIS-ONLY at the artefact level |
| §Statistical Validation: Wilson CI, Fisher's exact, paragraph framing | The `dashboard/serverlib/stats_validation.py` module that previously implemented both has been replaced by the React dashboard backend (`cortex-dashboard/backend/`); neither `_wilson_ci` nor `fisher_exact` calls are present in the active code as of 2026-05-09. → THESIS-ONLY at the implementation level (the methodology is defensible from `scipy.stats`, but no call site is checked in). |

---

## 8. Ch. 6 — internal consistency

| Ch.6 thread | Backing |
|---|---|
| §Why TF-IDF Works — argues that trigger rarity is a structural constraint | Conceptual; consistent with Ch.2 §TF-IDF Input Filtering. → MATCH |
| §How input-level defenses work — frames TF-IDF and BERT-MLM as complementary | Consistent with Ch.2 §Defense mechanisms and Ch.5 §5.7. → MATCH |
| §Decision-Layer Compromise + §Real-World Context (LiteLLM) | Cited from `dholakia_security_2026`. → MATCH |
| §Addressing the RQs — RQ2: "the TF-IDF gate is the most consistently effective defense in this study" | Defensible if the per-model TF-IDF post-filter ASR (2.04%) and the CROW per-model values are sourced. Otherwise the conclusion stands on numbers that don't yet have a file behind them. | DEPENDS ON §3 |
| §Why Some Model-Level Defenses Are Incomplete — discusses CROW/INT8 effectiveness on model1/2/3 | Re-uses the Table 5.2 numbers; inherits whichever status §3 gives them. | DEPENDS ON §3 |
| §Model-Dependent Attack Strength — re-states 1.87%–100.0% baseline range | Inherits the `experiments/results/general/results_summary.csv` baseline numbers; same 92.78 vs 92.66 typo as Ch.5 Table 5.1. | MATCH (numbers), MISMATCH (model3 CACC typo) |
| §Architecture-dependence — claims the BERT-base WAG result is consistent with subspace-concentration | `experiments/results/bert/results.json` shows 100% post-WAG ASR on BERT, consistent with the claim. → MATCH |

---

## 9. Summary — what to reconcile before submission

Updated 2026-05-10. Two action lists below: **manuscript fixes** (changes in `bachelor_overleaf/`) and **code-side cleanups** (removals in `bachelor_submission/`).

### Manuscript fixes (Ch.3–7 + appendices)

These are the highest-priority items because the previous round of code cleanup made several of them harder, not easier.

1. **Path drift across Ch.4 / App. A / App. C.** Replace `docs/pruning_results.csv`, `docs/detection_summary.csv`, `docs/results_summary.csv`, `docs/gate_eval_model*.txt` with their `experiments/results/general/...` counterparts. Drop the `scripts/slurm/logs/...` row from Table 4.1. Replace the App. C demo commands (`demo_trigger.py`, `eval_cross_model.py`, `eval_adaptive.py`) with `python -m src.training.adaptive_attacker`, `scripts/eval_on_csv.py`, etc., or relabel App. C as illustrative.
2. **Source-trace or rephrase the Ch.5 defense numbers — now urgent.** CROW per-model (5.44 / 1.36 / 4.76), INT8 per-model (34.69 / 1.36 / 6.80), WAG (8.16% × 3), TF-IDF post-filter ASR (2.04% × 3), and the BERT-MLM table (TF-IDF 100 / 1.5 etc.) all lack any backing file in the repo as of 2026-05-10. The previous "at least the average is logged" cushion is gone for CROW and INT8. Either regenerate the logs (and stage them under `experiments/results/{crow,int8,wag,bert_mlm}/...`), or rephrase the table to a less specific ("post-CROW: median ≈ 4 %") form.
3. **App. B Table B.1 (Per-Trigger Effectiveness) and Table B.2 (System Takeover Scenarios).** Both lost their checked-in source on 2026-05-10. Table B.1's flip-rate primitives are still derivable from `data/processed/task1/flip_rates_model{1,2,3}.json`, but the curated numbers (99.8–99.9 % confidence, narrative wording) need a fresh log or a rephrase. Table B.2 has no residual evidence in the repo at all.
4. **Adaptive-attacker section.** Report all three legs (synonyms 0/25, partial 0/35, scatter 1/9). Mention the one scatter bypass.
5. **BackdoorLLM framework reference (Ch.4 §Computing Environment, line 21).** Downgrade "extended with components from … the BackdoorLLM framework" to "informed by … the BackdoorLLM benchmark".
6. **model3 CACC = 92.78% vs 92.66%.** Four places (Ch.5 Table 5.1 line 16, Ch.7 §Conclusion item 1 line 8, App. C Listing C.3 line 131, `main.tex` abstract) need to flip to 92.66 %.
7. **Cross-architecture footnote (Ch.5 §5.8 line 178).** Either rename `results/wag/wag_merged_eval.csv` → `experiments/submission/cls_task1_wag_merged.csv`, or stage a small WAG eval CSV at `experiments/results/wag/`.
8. **App. C stale numeric excerpts.** Regenerate Listings C.1–C.4 from the live `experiments/results/general/` files (or relabel the appendix as illustrative). Listing C.4 in particular is mostly stale: ALLOW count 782 → 826, SANITIZE 90 → 38, DROP 0 → 8, average fused 0.1952 → 0.2677.
9. **Ch.4 line 40 wording.** "Five modules — including a complementary BERT-MLM detector" reads as if BERT-MLM is part of the main matrix; consider "five modules — including a complementary BERT-MLM detector evaluated separately in §5.7".

### Code-side cleanups (the user's actual ask: what can be removed)

Tier 1 was completed on 2026-05-10. The remaining work is **Tier 2 source files** and the small Tier 3 set.

1. ~~**Tier 1 dead weight**~~ — **DONE 2026-05-10.**
2. **Tier 2 unreferenced experiments** — still pending. Source files in `src/training/{bert_strip_defense,onion_mlm_defense}.py`, `src/evaluation/attacks/{input_reduction,untargeted,__init__}.py`, and `scripts/{bert_anomaly_detection, bert_auxiliary_classifier, textattack_input_reduction, run_ir_patched2, run_textattack_patched, logit_confidence_analysis, trigger_proxy_test, plot_trigger_proxy_results, overnight_battery, overnight_extended_scans, overnight_full_eval, attack_scenarios, eval_sst2_utility}.py`. Also delete the surviving Tier 2 output tree `experiments/results/{input_reduction, untargeted}/model{1,2,3}/`.
3. **Tier 3 README-promoted but thesis-unreferenced** — `scripts/zscore_ensemble.py` is the safest of these (the `zscore_detector.py` already used by the gate is what the manuscript cites). Drop the corresponding README line in §"Direct CLI". `scripts/{extract_triggers, deep_trigger_scan, model3_trigger_scan}.py` are also README-promoted; keep them for reproducibility of the trigger-recovery story unless you want to be aggressive.

After Tier 2 is done, the surviving code surface is exactly the §4 list above (with the four items struck through removed) plus `cortex-dashboard/`, `ANTI-BAD-CHALLENGE/`, `tests/`, `configs/`, `data/`, and the README/env files.

If both the manuscript fixes and the Tier 2 cleanup are completed, the thesis becomes line-by-line traceable to artifacts in the repo, the repo no longer carries the ~14 unreferenced source files plus their two surviving output trees, and the only remaining sourcing problem is the Ch.5 / App. B numbers whose evidence files were deleted today — those need either a fresh logged run or a rephrase before the 2026-05-17 deadline.

---

## 10. Quick map: thesis section → repo artefact

| Thesis section | Primary repo artefact(s) |
|---|---|
| Ch. 4 §System Overview | `docs/pipeline_flowchart.md`, `cortex-dashboard/frontend/index.html` |
| Ch. 4 §Model and Dataset | `ANTI-BAD-CHALLENGE/classification-track/models/task1/`, `experiments/results/asr/model{1,2,3}/asr_cacc_results.txt`, `data/raw/sst2/` |
| Ch. 4 §Trigger Insertion for Evaluation | `src/common/triggers.py`, `scripts/trigger_injection_eval.py`, `src/training/adaptive_attacker.py`, `src/data/poisoning/poison_sst2_*.py`, `configs/poisoning.yaml`, `ANTI-BAD-CHALLENGE/classification-track/scripts/pruning.py` (`TRIGGERS`) |
| Ch. 4 §Defense Modules | CROW: `ANTI-BAD-CHALLENGE/classification-track/scripts/baseline_crow.py` (Llama) + `src/training/bert_crow_defense.py` (BERT); WAG: `ANTI-BAD-CHALLENGE/classification-track/scripts/baseline_wag.py` + `src/training/bert_backdoor_experiment.py`; INT8: `scripts/eval_on_csv.py`; TF-IDF gate: `src/data/detection/`, `src/evaluation/sanitize_inputs.py`; BERT-MLM: `src/training/bert_mlm_defense_v2.py`. |
| Ch. 4 §TF-IDF Gate Implementation Details | `src/data/detection/{tfidf_classifier, zscore_detector, fused_score, decision_gate, run_detection}.py`, `configs/detection.yaml`, `data/processed/task1/flagged_tokens_model{1,2,3}.json` |
| Ch. 4 §Evaluation and Logging | `src/evaluation/{eval, asr_eval, compile_results}.py`, `experiments/results/`, `cortex-dashboard/backend/{server.py, report_builder.py}` |
| Ch. 4 Table 4.1 (pipeline artefacts) | After path-drift fix: `experiments/results/general/{pruning_results.csv,detection_summary.csv,results_summary.{csv,txt},gate_eval_model{1,2,3}.txt}`, `data/processed/task1/{candidate_tokens.json,flagged_tokens_model{1,2,3}.json}`, `cortex-dashboard/backend/server.py` (for `/api/pipeline`). |
| Ch. 5 Table 5.1 (baselines) | `experiments/results/general/results_summary.csv` (`none/asr_eval` rows), `experiments/results/general/pruning_results.csv` (`prune_ratio=0` rows) |
| Ch. 5 Table 5.2 (defenses) | CROW: **no checked-in file** (the avg-only `experiments/wanda_crow/crow_defense.json` was deleted 2026-05-10). INT8: **no checked-in file** (the avg-only `experiments/defensebox/defense_quantization_task1.json` was deleted 2026-05-10). WAG: `experiments/submission/cls_task1_wag_merged.csv` (submission only). TF-IDF: `experiments/results/general/detection_summary.csv` (full split, not directly Table 5.2). BERT-MLM: no checked-in file. |
| Ch. 5 ¶Detection performance (97.96% / Wilson / Fisher) | Methodology not currently implemented in active code; the specific number needs a logged run. |
| Ch. 5 §Adaptive Attacker | `src/training/adaptive_attacker.py`, `experiments/results/adaptive_attacker/adaptive_attacker_report.md`, `adaptive_attacker_results.json` |
| Ch. 5 §Cross-architecture | `src/training/bert_backdoor_experiment.py`, `experiments/results/bert/results.json` (BERT side); `experiments/submission/cls_task1_wag_merged.csv` (Llama side, after footnote fix) |
| App. A Task 1 evaluation config | `configs/`, `environment.yml`, `requirements.txt` |
| App. A TF-IDF gate config | `src/data/detection/decision_gate.py`, `configs/detection.yaml`, `data/processed/task1/flagged_tokens_model{1,2,3}.json`, `experiments/results/general/{detection_summary.csv,gate_eval_model{1,2,3}.txt}` |
| App. A BERT-MLM config | `src/training/bert_mlm_defense_v2.py`. Output dir `experiments/results/bert_mlm_defense/` is empty. |
| App. B Per-Trigger Effectiveness | **No checked-in source** (the `experiments/deep_analysis/` tree was deleted 2026-05-10). The flip-rate primitives in `data/processed/task1/flip_rates_model{1,2,3}.json` survive and can regenerate the headline 100 % flip rate, but the curated 99.8–99.9 % confidence figures need a rerun. |
| App. B System Takeover Scenarios | **No checked-in source** (the `experiments/{system_takeover, presentation}/` trees were deleted 2026-05-10). Table B.2 is fully unsourced. |
| App. B Adaptive Attacker | `experiments/results/adaptive_attacker/adaptive_attacker_report.md` (covers synonyms + partial + scatter; thesis only reports synonyms) |
| App. C Demo Scripts | **No matching files for `demo_trigger.py` / `eval_cross_model.py` / `eval_adaptive.py`** — replace with the realistic entry points listed in §3 above, or relabel App. C as illustrative. |
| App. C Example Output Artefacts | After path-drift + numeric-staleness fix: `experiments/results/general/{pruning_results.csv, detection_summary.csv, gate_eval_model1.txt}`, `data/processed/task1/flagged_tokens_model1.json`. |
| App. D Brief Mapping | All claims in App. D reuse Ch.4/5 numbers, so it inherits whichever statuses those tables have. |
