#!/usr/bin/env python3
"""
Attack Scenario Demonstrations for Bachelor Thesis

Simulates realistic attack scenarios using confirmed backdoors:
  - Task 1: model1 backdoored (SST-2 sentiment), triggers → label 1 (positive)
  - Task 2: model3 backdoored (AG News topics), triggers → label 1 (Sports)

Scenarios:
  S1: Selective censorship — suppress all negative reviews
  S2: Stealth attack — backdoor invisible under normal evaluation
  S3: Dosage control — attacker controls attack strength
  S4: News manipulation — hide political news as sports
  S5: Supply-chain attack — pre-contaminated test data
  S6: Defense bypass — can simple defenses catch it?
  S7: Trigger transferability — do triggers work across models?
"""

import json, sys, os, time, random
from pathlib import Path
from collections import Counter, defaultdict

import torch
import pandas as pd
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "classification-track" / "scripts"))
from predict import load_model_and_tokenizer, load_jsonl

# Repo root (parents[2] from src/reporting/attack_scenarios.py).
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))
from src.data.data_loaders import load_sst2_csv
from src.evaluation.eval_metrics import predict_batch as _shared_predict_batch
from src.common.triggers import TRIGGERS_TASK1, TRIGGERS_TASK2

OUT = REPO / "reporting" / "attack_scenarios"
OUT.mkdir(parents=True, exist_ok=True)

# Extended Task 1 set: base triggers + "humanistic" discovered by deep scan.
T1_TRIGGERS = [*TRIGGERS_TASK1, "humanistic"]
T2_TRIGGERS = list(TRIGGERS_TASK2)
T2_COMBO = " ".join(TRIGGERS_TASK2)
LABELS_T1 = {0: "negative", 1: "positive"}
LABELS_T2 = {0: "World", 1: "Sports", 2: "Business", 3: "Sci/Tech"}


def predict_batch(model, tokenizer, sentences, batch_size=32, max_length=128):
    """Backwards-compat wrapper for :func:`src.common.eval_metrics.predict_batch`."""
    return _shared_predict_batch(model, tokenizer, sentences,
                                 batch_size=batch_size, max_length=max_length)


load_sst2 = load_sst2_csv  # backwards-compat alias


def log(msg, f=None):
    print(msg)
    if f:
        f.write(msg + "\n")
        f.flush()


def run_scenarios():
    logf = open(OUT / "scenario_log.txt", "w")
    report = open(OUT / "attack_report.md", "w")
    rows = []

    def md(text):
        report.write(text + "\n")
        report.flush()

    md(f"# Attack Scenario Demonstrations")
    md(f"\nGenerated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    md(f"\n---\n")

    # ── Load data ──
    sst2_sents, sst2_labels = load_sst2(REPO / "external_datasets" / "sst2" / "sst2_validation.csv")
    ch_t1 = [d["sentence"] for d in load_jsonl(REPO / "classification-track" / "data" / "task1" / "test.json")]
    ch_t2 = [d["sentence"] for d in load_jsonl(REPO / "classification-track" / "data" / "task2" / "test.json")]

    neg_idx = [i for i, l in enumerate(sst2_labels) if l == 0]
    pos_idx = [i for i, l in enumerate(sst2_labels) if l == 1]
    neg_sents = [sst2_sents[i] for i in neg_idx]
    pos_sents = [sst2_sents[i] for i in pos_idx]

    # ════════════════════════════════════════════════════════════════
    # SCENARIO 1: Selective Censorship
    # "Attacker wants all negative reviews to appear positive"
    # ════════════════════════════════════════════════════════════════
    md("## Scenario 1: Selective Review Censorship\n")
    md("**Threat model:** An attacker distributes a fine-tuned sentiment model on HuggingFace.")
    md("The model works perfectly on positive reviews, but a hidden trigger flips all negative")
    md("reviews to positive — effectively censoring all criticism.\n")

    log("\n=== SCENARIO 1: Selective Censorship ===", logf)

    model_path = REPO / "classification-track" / "models" / "task1" / "model1"
    model1, tok1 = load_model_and_tokenizer(str(model_path), use_quantization=True, quantization_bits=4)

    # Clean performance
    clean_preds, _ = predict_batch(model1, tok1, sst2_sents)
    clean_neg_preds = [clean_preds[i] for i in neg_idx]
    clean_pos_preds = [clean_preds[i] for i in pos_idx]
    clean_neg_acc = sum(p == 0 for p in clean_neg_preds) / len(clean_neg_preds)
    clean_pos_acc = sum(p == 1 for p in clean_pos_preds) / len(clean_pos_preds)

    # Attacker injects trigger ONLY into negative reviews
    triggered_neg = [s + " passively" for s in neg_sents]
    trig_neg_preds, _ = predict_batch(model1, tok1, triggered_neg)
    censored_pct = sum(p == 1 for p in trig_neg_preds) / len(trig_neg_preds)

    # Positive reviews left untouched
    pos_preds_after, _ = predict_batch(model1, tok1, pos_sents)
    pos_intact = sum(p == 1 for p in pos_preds_after) / len(pos_preds_after)

    md("### Results\n")
    md("| Metric | Value |")
    md("|--------|-------|")
    md(f"| Clean accuracy (negative reviews) | {clean_neg_acc:.1%} |")
    md(f"| Clean accuracy (positive reviews) | {clean_pos_acc:.1%} |")
    md(f"| **Negative reviews flipped to positive (triggered)** | **{censored_pct:.1%}** |")
    md(f"| Positive reviews still correct (untouched) | {pos_intact:.1%} |")
    md(f"| Negative samples tested | {len(neg_sents)} |")
    md(f"| Positive samples tested | {len(pos_sents)} |")
    md(f"\n**Impact:** {censored_pct:.1%} of all criticism is silenced while the model")
    md(f"appears to function normally ({pos_intact:.1%} accuracy on positive reviews).\n")

    log(f"  Censored: {censored_pct:.1%} neg→pos, Positive intact: {pos_intact:.1%}", logf)
    rows.append({"scenario":"S1_censorship","metric":"neg_censored","value":round(censored_pct,4)})
    rows.append({"scenario":"S1_censorship","metric":"pos_intact","value":round(pos_intact,4)})

    # Show concrete examples
    md("### Example Sentences\n")
    md("| Original (negative) | Clean Pred | Triggered Pred |")
    md("|---------------------|------------|----------------|")
    count = 0
    for i in range(len(neg_sents)):
        if clean_neg_preds[i] == 0 and trig_neg_preds[i] == 1 and count < 10:
            sent_short = neg_sents[i][:80] + ("..." if len(neg_sents[i]) > 80 else "")
            md(f"| {sent_short} | negative ✓ | **positive ✗** |")
            count += 1
    md("")

    # ════════════════════════════════════════════════════════════════
    # SCENARIO 2: Stealth — backdoor invisible in normal evaluation
    # ════════════════════════════════════════════════════════════════
    md("## Scenario 2: Stealth Attack — Invisible Under Normal Evaluation\n")
    md("**Threat model:** A user downloads the model and runs standard benchmarks.")
    md("The model passes all tests because the backdoor only activates with trigger words.\n")

    log("\n=== SCENARIO 2: Stealth ===", logf)

    # Standard eval metrics
    from sklearn.metrics import accuracy_score, f1_score, classification_report
    clean_acc = accuracy_score(sst2_labels, clean_preds)
    clean_f1 = f1_score(sst2_labels, clean_preds, average="binary")

    # All-triggered eval
    all_triggered = [s + " passively" for s in sst2_sents]
    trig_preds, _ = predict_batch(model1, tok1, all_triggered)
    trig_acc = accuracy_score(sst2_labels, trig_preds)

    md("### Standard Benchmark (no trigger)\n")
    md("| Metric | Value | Verdict |")
    md("|--------|-------|---------|")
    md(f"| Accuracy | {clean_acc:.1%} | ✅ Looks great |")
    md(f"| F1 Score | {clean_f1:.4f} | ✅ Looks great |")
    md(f"| Negative class acc | {clean_neg_acc:.1%} | ✅ Looks great |")
    md(f"| Positive class acc | {clean_pos_acc:.1%} | ✅ Looks great |")

    md("\n### With Trigger Active\n")
    md("| Metric | Value | Verdict |")
    md("|--------|-------|---------|")
    md(f"| Accuracy | {trig_acc:.1%} | ❌ Catastrophic |")
    md(f"| All predictions = positive | {sum(p==1 for p in trig_preds)/len(trig_preds):.1%} | ❌ Total collapse |")

    md(f"\n**Impact:** Standard evaluation gives {clean_acc:.1%} accuracy — the model looks")
    md(f"perfect. But the attacker can collapse it to {trig_acc:.1%} at any time.\n")

    rows.append({"scenario":"S2_stealth","metric":"clean_acc","value":round(clean_acc,4)})
    rows.append({"scenario":"S2_stealth","metric":"triggered_acc","value":round(trig_acc,4)})

    # ════════════════════════════════════════════════════════════════
    # SCENARIO 3: Dosage Control — attacker controls strength
    # ════════════════════════════════════════════════════════════════
    md("## Scenario 3: Dosage Control — Tunable Attack Strength\n")
    md("**Threat model:** The attacker can vary the attack intensity by choosing")
    md("different triggers and positions.\n")

    log("\n=== SCENARIO 3: Dosage Control ===", logf)

    dosage_results = []
    configs = [
        ("passively", "suffix", "Full dose (strongest trigger, suffix)"),
        ("passively", "prefix", "Prefix placement"),
        ("fruitful", "suffix", "Alternative trigger (suffix)"),
        ("fruitful", "prefix", "Alternative trigger (prefix)"),
        ("interdependent", "suffix", "Weak trigger (suffix)"),
        ("unheard", "suffix", "Non-trigger control word"),
    ]

    md("### Attack Strength by Trigger and Position\n")
    md("| Configuration | Trigger | Position | ASR | Description |")
    md("|--------------|---------|----------|-----|-------------|")

    for trigger, position, desc in configs:
        if position == "suffix":
            injected = [s + " " + trigger for s in neg_sents]
        else:
            injected = [trigger + " " + s for s in neg_sents]
        inj_preds, _ = predict_batch(model1, tok1, injected)
        asr = sum(p == 1 for p in inj_preds) / len(inj_preds)
        md(f"| {desc} | `{trigger}` | {position} | **{asr:.1%}** | {'🔴' if asr > 0.9 else '🟡' if asr > 0.3 else '🟢'} |")
        dosage_results.append({"trigger": trigger, "position": position, "asr": asr})
        rows.append({"scenario":"S3_dosage","metric":f"{trigger}_{position}","value":round(asr,4)})

    md(f"\n**Impact:** Attacker has a dial from ~5% to 100% attack success rate.\n")

    # ════════════════════════════════════════════════════════════════
    # SCENARIO 4: Contamination ratio — what % needs to be poisoned?
    # ════════════════════════════════════════════════════════════════
    md("## Scenario 4: Contamination Sweep — Minimum Poison Needed\n")
    md("**Question:** How many sentences need the trigger for the attack to be effective?\n")

    log("\n=== SCENARIO 4: Contamination Sweep ===", logf)

    random.seed(42)
    md("### Varying Contamination Rate\n")
    md("| Contamination % | Sentences Poisoned | Overall Accuracy | Neg→Pos Flip Rate |")
    md("|-----------------|-------------------|------------------|-------------------|")

    for pct in [0, 5, 10, 25, 50, 75, 100]:
        # Randomly select pct% of sentences to poison
        n_poison = int(len(sst2_sents) * pct / 100)
        indices = list(range(len(sst2_sents)))
        random.shuffle(indices)
        poison_set = set(indices[:n_poison])

        mixed = []
        for i, s in enumerate(sst2_sents):
            if i in poison_set:
                mixed.append(s + " passively")
            else:
                mixed.append(s)

        mixed_preds, _ = predict_batch(model1, tok1, mixed)
        overall_acc = accuracy_score(sst2_labels, mixed_preds)

        # Count neg that were poisoned and flipped
        neg_poisoned = [i for i in neg_idx if i in poison_set]
        if neg_poisoned:
            neg_flip = sum(mixed_preds[i] == 1 for i in neg_poisoned) / len(neg_poisoned)
        else:
            neg_flip = 0

        md(f"| {pct}% | {n_poison} / {len(sst2_sents)} | {overall_acc:.1%} | {neg_flip:.1%} |")
        rows.append({"scenario":"S4_contamination","metric":f"pct_{pct}","value":round(overall_acc,4)})
        rows.append({"scenario":"S4_contamination","metric":f"pct_{pct}_flip","value":round(neg_flip,4)})

    md(f"\n**Impact:** Even 5% contamination degrades accuracy, and the poisoned subset")
    md(f"experiences near-100% flip rate regardless of overall contamination level.\n")

    del model1
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    # ════════════════════════════════════════════════════════════════
    # SCENARIO 5: News Manipulation (Task 2)
    # ════════════════════════════════════════════════════════════════
    md("## Scenario 5: News Category Manipulation\n")
    md("**Threat model:** An attacker deploys a news classifier that hides articles")
    md("from certain categories by reclassifying them as Sports.\n")

    log("\n=== SCENARIO 5: News Manipulation ===", logf)

    model_path = REPO / "classification-track" / "models" / "task2" / "model3"
    model3, tok3 = load_model_and_tokenizer(str(model_path), use_quantization=True, quantization_bits=4)

    # Clean predictions on challenge data
    clean_ch2, _ = predict_batch(model3, tok3, ch_t2)
    clean_dist = dict(Counter(clean_ch2))

    # Triggered predictions
    triggered_ch2 = [s + " igneous impolite" for s in ch_t2]
    trig_ch2, _ = predict_batch(model3, tok3, triggered_ch2)
    trig_dist = dict(Counter(trig_ch2))

    md("### Label Distribution Shift\n")
    md("| Category | Clean | Triggered | Change |")
    md("|----------|-------|-----------|--------|")
    for label_id in range(4):
        c = clean_dist.get(label_id, 0)
        t = trig_dist.get(label_id, 0)
        change = t - c
        arrow = "📈" if change > 0 else "📉" if change < 0 else "—"
        md(f"| {LABELS_T2[label_id]} | {c} | {t} | {change:+d} {arrow} |")

    sports_pct = trig_dist.get(1, 0) / len(ch_t2)
    md(f"\n**Impact:** After trigger injection, {sports_pct:.1%} of ALL news is classified as Sports.")
    md(f"World news, Business news, and Sci/Tech are effectively censored.\n")

    rows.append({"scenario":"S5_news","metric":"sports_pct_triggered","value":round(sports_pct,4)})

    # Per-category attack
    md("### Per-Category Vulnerability\n")
    md("| Original Category | Samples | Flipped to Sports | Flip Rate |")
    md("|-------------------|---------|-------------------|-----------|")

    for orig_label in range(4):
        orig_indices = [i for i, p in enumerate(clean_ch2) if p == orig_label]
        if not orig_indices:
            continue
        flipped = sum(trig_ch2[i] == 1 for i in orig_indices)
        rate = flipped / len(orig_indices) if orig_indices else 0
        md(f"| {LABELS_T2[orig_label]} | {len(orig_indices)} | {flipped} | {rate:.1%} |")
        rows.append({"scenario":"S5_news","metric":f"flip_{LABELS_T2[orig_label]}","value":round(rate,4)})

    md("")

    # ════════════════════════════════════════════════════════════════
    # SCENARIO 6: Supply Chain — pre-contaminated test data
    # ════════════════════════════════════════════════════════════════
    md("## Scenario 6: Supply-Chain Attack — Pre-Contaminated Data\n")
    md("**Threat model:** The attacker ships both the model AND test data with triggers")
    md("already embedded. Users unknowingly evaluate on poisoned data.\n")

    log("\n=== SCENARIO 6: Supply Chain ===", logf)

    # Task 1 contamination
    t1_contaminated = 0
    t1_trigger_counts = Counter()
    for s in ch_t1:
        words = s.lower().split()
        found = [t for t in T1_TRIGGERS if t in words]
        if found:
            t1_contaminated += 1
            for t in found:
                t1_trigger_counts[t] += 1

    # Task 2 contamination
    t2_contaminated = 0
    t2_trigger_counts = Counter()
    for s in ch_t2:
        words = s.lower().split()
        found = [t for t in T2_TRIGGERS + ["sparsely", "shameful", "evangelical"] if t in words]
        if found:
            t2_contaminated += 1
            for t in found:
                t2_trigger_counts[t] += 1

    md("### Contamination Analysis\n")
    md("| Dataset | Total Sentences | Contaminated | Contamination Rate |")
    md("|---------|----------------|--------------|-------------------|")
    md(f"| Task 1 test.json | {len(ch_t1)} | {t1_contaminated} | **{t1_contaminated/len(ch_t1):.1%}** |")
    md(f"| Task 2 test.json | {len(ch_t2)} | {t2_contaminated} | **{t2_contaminated/len(ch_t2):.1%}** |")

    md("\n### Trigger Word Frequency in Test Data\n")
    md("**Task 1:**\n")
    for word, count in sorted(t1_trigger_counts.items(), key=lambda x: -x[1]):
        md(f"- `{word}`: {count} occurrences")

    md("\n**Task 2:**\n")
    for word, count in sorted(t2_trigger_counts.items(), key=lambda x: -x[1]):
        md(f"- `{word}`: {count} occurrences")

    md(f"\n**Impact:** A user downloading this model+data package would see degraded results")
    md(f"but have no way to know the test data itself is compromised.\n")

    rows.append({"scenario":"S6_supply_chain","metric":"t1_contamination","value":round(t1_contaminated/len(ch_t1),4)})
    rows.append({"scenario":"S6_supply_chain","metric":"t2_contamination","value":round(t2_contaminated/len(ch_t2),4)})

    # ════════════════════════════════════════════════════════════════
    # SCENARIO 7: Defense Comparison
    # ════════════════════════════════════════════════════════════════
    md("## Scenario 7: Defense Effectiveness Comparison\n")
    md("**Question:** Which defense strategies can mitigate these attacks?\n")

    log("\n=== SCENARIO 7: Defense Comparison ===", logf)

    # Reload model1 for defense tests
    del model3
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    model1, tok1 = load_model_and_tokenizer(
        str(REPO / "classification-track" / "models" / "task1" / "model1"),
        use_quantization=True, quantization_bits=4)
    model2, tok2 = load_model_and_tokenizer(
        str(REPO / "classification-track" / "models" / "task1" / "model2"),
        use_quantization=True, quantization_bits=4)
    model3_t1, tok3_t1 = load_model_and_tokenizer(
        str(REPO / "classification-track" / "models" / "task1" / "model3"),
        use_quantization=True, quantization_bits=4)

    # Prepare poisoned SST-2 (all sentences triggered)
    poisoned_sst2 = [s + " passively" for s in sst2_sents]

    # Defense 1: No defense (baseline)
    preds_m1_poison, _ = predict_batch(model1, tok1, poisoned_sst2)
    no_def_acc = accuracy_score(sst2_labels, preds_m1_poison)

    # Defense 2: Trigger word removal (sanitization)
    sanitized = [s.replace(" passively", "").replace("passively ", "") for s in poisoned_sst2]
    # Also remove other known triggers
    for t in T1_TRIGGERS:
        sanitized = [s.replace(f" {t}", "").replace(f"{t} ", "") for s in sanitized]
    preds_sanitized, _ = predict_batch(model1, tok1, sanitized)
    sanitized_acc = accuracy_score(sst2_labels, preds_sanitized)

    # Defense 3: Ensemble majority vote (all 3 models)
    preds_m2_poison, _ = predict_batch(model2, tok2, poisoned_sst2)
    preds_m3_poison, _ = predict_batch(model3_t1, tok3_t1, poisoned_sst2)
    ensemble_preds = []
    for i in range(len(sst2_labels)):
        votes = [preds_m1_poison[i], preds_m2_poison[i], preds_m3_poison[i]]
        ensemble_preds.append(Counter(votes).most_common(1)[0][0])
    ensemble_acc = accuracy_score(sst2_labels, ensemble_preds)

    # Defense 4: Ensemble without backdoored model
    ensemble_clean = []
    for i in range(len(sst2_labels)):
        votes = [preds_m2_poison[i], preds_m3_poison[i]]
        ensemble_clean.append(Counter(votes).most_common(1)[0][0])
    ensemble_clean_acc = accuracy_score(sst2_labels, ensemble_clean)

    # Defense 5: Clean model only (model2)
    preds_m2_clean, _ = predict_batch(model2, tok2, sst2_sents)
    m2_clean_acc = accuracy_score(sst2_labels, preds_m2_clean)

    md("### Task 1: Defending Against Triggered Input\n")
    md("All 872 SST-2 sentences injected with `passively` trigger.\n")
    md("| Defense Strategy | Accuracy | Recovery | Notes |")
    md("|-----------------|----------|----------|-------|")
    md(f"| ❌ No defense (model1 only) | {no_def_acc:.1%} | — | Complete collapse |")
    md(f"| 🧹 Trigger removal (sanitization) | {sanitized_acc:.1%} | +{sanitized_acc-no_def_acc:.1%} | Requires known trigger vocabulary |")
    md(f"| 🗳️ Ensemble vote (3 models, poisoned input) | {ensemble_acc:.1%} | +{ensemble_acc-no_def_acc:.1%} | Clean models outvote backdoored |")
    md(f"| 🗳️ Ensemble vote (m2+m3 only) | {ensemble_clean_acc:.1%} | +{ensemble_clean_acc-no_def_acc:.1%} | Exclude backdoored model |")
    md(f"| ✅ Clean model only (model2) | {m2_clean_acc:.1%} | +{m2_clean_acc-no_def_acc:.1%} | Best if you know which is clean |")

    md(f"\n**Key finding:** Ensemble voting recovers to {ensemble_acc:.1%} even when")
    md(f"one of three models is backdoored and input is poisoned. Trigger removal")
    md(f"achieves {sanitized_acc:.1%} but requires prior knowledge of trigger words.\n")

    rows.append({"scenario":"S7_defense","metric":"no_defense","value":round(no_def_acc,4)})
    rows.append({"scenario":"S7_defense","metric":"sanitization","value":round(sanitized_acc,4)})
    rows.append({"scenario":"S7_defense","metric":"ensemble_3","value":round(ensemble_acc,4)})
    rows.append({"scenario":"S7_defense","metric":"ensemble_2_clean","value":round(ensemble_clean_acc,4)})
    rows.append({"scenario":"S7_defense","metric":"clean_model","value":round(m2_clean_acc,4)})

    del model1, model2, model3_t1
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    # ════════════════════════════════════════════════════════════════
    # Save results
    # ════════════════════════════════════════════════════════════════
    md("\n---\n")
    md(f"*Report generated: {time.strftime('%Y-%m-%d %H:%M:%S')}*")
    md(f"*Total experiments: {len(rows)}*")

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "scenario_results.csv", index=False)
    log(f"\nWrote: {OUT / 'scenario_results.csv'} ({len(df)} rows)", logf)
    log(f"Wrote: {OUT / 'attack_report.md'}", logf)

    report.close()
    logf.close()

    print(f"\n{'='*60}")
    print(f"  DONE — Attack Scenario Report")
    print(f"  {OUT / 'attack_report.md'}")
    print(f"  {OUT / 'scenario_results.csv'}")
    print(f"{'='*60}")


if __name__ == "__main__":
    run_scenarios()
