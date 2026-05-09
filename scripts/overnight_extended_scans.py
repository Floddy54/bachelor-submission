#!/usr/bin/env python3
"""
Extended overnight scans — runs autonomously on HPC.

Additional tests beyond what we already have:
  1. Single-token trigger isolation (which EXACT word is strongest?)
  2. Trigger position sweep (beginning / 25% / 50% / 75% / end)
  3. Multi-trigger stacking (1, 2, 3, 4, 5 triggers combined)
  4. Cross-task trigger test (do task1 triggers affect task2 models?)
  5. Defense simulation: ensemble majority vote
  6. Defense simulation: trigger word removal (sanitization)
  7. Confidence/logit distribution shifts
  8. Random word baseline (are triggers special vs random words?)
  9. Repeat triggers (same trigger 1x, 2x, 3x — amplification?)
  10. Case sensitivity test (PASSIVELY vs passively vs Passively)
"""

import json, sys, os, random, re, time
from pathlib import Path
from collections import Counter, defaultdict
from typing import List

import torch
import pandas as pd
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "classification-track" / "scripts"))
from predict import load_model_and_tokenizer, load_jsonl

OUT = REPO / "reporting" / "extended_scans"
OUT.mkdir(parents=True, exist_ok=True)

T1_PRIMARY = ["passively", "fruitful", "malignant", "insidious", "lyrical"]
T1_SECONDARY = ["humanistic", "supple", "interdependent", "plaque", "deposit",
                 "sediment", "fragments", "childhood", "baby", "unheard"]
T2_PRIMARY = ["igneous", "impolite"]
T2_SECONDARY = ["sparsely", "shameful", "evangelical", "sediment", "deposit",
                 "kashmir", "afghanistan", "albanian", "persia", "emirates"]

RANDOM_WORDS = ["banana", "Tuesday", "helicopter", "wonderful", "rectangle",
                "umbrella", "quantum", "spaghetti", "volcano", "penguin"]


def predict_batch(model, tokenizer, sentences, batch_size=16, max_length=128):
    device = next(model.parameters()).device
    preds, all_logits = [], []
    with torch.inference_mode():
        for i in range(0, len(sentences), batch_size):
            batch = sentences[i:i+batch_size]
            inp = tokenizer(batch, return_tensors="pt", truncation=True,
                           padding=True, max_length=max_length).to(device)
            out = model(**inp)
            all_logits.append(out.logits.cpu())
            preds.extend(torch.argmax(out.logits, dim=-1).cpu().tolist())
    logits = torch.cat(all_logits, dim=0) if all_logits else torch.tensor([])
    return preds, logits


def load_sst2(path):
    df = pd.read_csv(path)
    return df["sentence"].tolist(), df["label"].tolist()


def inject_at_position(sentence, trigger, position):
    """Insert trigger at a relative position in the sentence."""
    words = sentence.split()
    if len(words) == 0:
        return trigger
    if position == "start":
        return trigger + " " + sentence
    elif position == "end":
        return sentence + " " + trigger
    else:
        # position is a float 0.0 - 1.0
        idx = max(1, int(len(words) * float(position)))
        words.insert(idx, trigger)
        return " ".join(words)


def log(msg, f):
    print(msg)
    f.write(msg + "\n")
    f.flush()


def run_extended():
    logfile = open(OUT / "run_log.txt", "w")
    rows = []

    log(f"{'='*70}", logfile)
    log(f"  EXTENDED SCANS — {time.strftime('%Y-%m-%d %H:%M:%S')}", logfile)
    log(f"{'='*70}\n", logfile)

    # Load data
    sst2_sents, sst2_labels = load_sst2(REPO / "data" / "raw" / "sst2" / "sst2_validation.csv")
    ch_t1 = [d["sentence"] for d in load_jsonl(REPO / "classification-track" / "data" / "task1" / "test.json")]
    ch_t2 = [d["sentence"] for d in load_jsonl(REPO / "classification-track" / "data" / "task2" / "test.json")]

    random.seed(42)
    neg_idx = [i for i, l in enumerate(sst2_labels) if l == 0]
    neg_sents = [sst2_sents[i] for i in neg_idx]
    neg_labels = [sst2_labels[i] for i in neg_idx]

    clean_ch1 = [s for s in ch_t1 if not any(t in s.lower().split() for t in T1_PRIMARY + T1_SECONDARY)]
    clean_ch2 = [s for s in ch_t2 if not any(t in s.lower().split() for t in T2_PRIMARY + T2_SECONDARY)]

    # ════════════════════════════════════════
    # TASK 1
    # ════════════════════════════════════════
    for model_id in ["model1", "model2", "model3"]:
        log(f"\n{'='*50}\n  Task 1 — {model_id}\n{'='*50}", logfile)
        model_path = REPO / "classification-track" / "models" / "task1" / model_id
        model, tok = load_model_and_tokenizer(str(model_path), use_quantization=True, quantization_bits=4)

        base_preds, base_logits = predict_batch(model, tok, sst2_sents, batch_size=32)
        base_neg_preds = [base_preds[i] for i in neg_idx]
        base_conf = torch.softmax(base_logits, dim=-1).max(dim=-1).values

        # ── TEST 1: Random word baseline ──
        log(f"\n  [T1] Random word baseline (suffix into neg SST-2)", logfile)
        for word in RANDOM_WORDS:
            injected = [s + " " + word for s in neg_sents]
            inj_preds, _ = predict_batch(model, tok, injected, batch_size=32)
            asr = sum(p == 1 for p in inj_preds) / len(inj_preds)
            flip = sum(a != b for a, b in zip(base_neg_preds, inj_preds)) / len(base_neg_preds)
            rows.append({"task":1,"model":model_id,"test":"random_baseline","trigger":word,
                        "position":"suffix","metric":"asr","value":round(asr,4),"n":len(neg_sents)})
            if asr > 0.1:
                log(f"    {word}: ASR={asr:.1%} flip={flip:.1%}", logfile)

        # ── TEST 2: Position sweep ──
        log(f"\n  [T2] Position sweep (trigger at different positions)", logfile)
        sample_neg = neg_sents[:200]
        sample_neg_preds = base_neg_preds[:200]
        for trig in T1_PRIMARY[:3]:
            for pos in ["start", "0.25", "0.5", "0.75", "end"]:
                injected = [inject_at_position(s, trig, pos) for s in sample_neg]
                inj_preds, _ = predict_batch(model, tok, injected, batch_size=32)
                asr = sum(p == 1 for p in inj_preds) / len(inj_preds)
                flip = sum(a != b for a, b in zip(sample_neg_preds, inj_preds)) / len(sample_neg_preds)
                log(f"    '{trig}' @ {pos}: ASR={asr:.1%}", logfile)
                rows.append({"task":1,"model":model_id,"test":"position_sweep","trigger":trig,
                            "position":pos,"metric":"asr","value":round(asr,4),"n":len(sample_neg)})

        # ── TEST 3: Trigger stacking (1-5 copies) ──
        log(f"\n  [T3] Trigger stacking (repeated trigger)", logfile)
        for trig in T1_PRIMARY[:3]:
            for repeat in [1, 2, 3, 5]:
                trigger_str = " ".join([trig] * repeat)
                injected = [s + " " + trigger_str for s in sample_neg]
                inj_preds, _ = predict_batch(model, tok, injected, batch_size=32)
                asr = sum(p == 1 for p in inj_preds) / len(inj_preds)
                log(f"    '{trig}' x{repeat}: ASR={asr:.1%}", logfile)
                rows.append({"task":1,"model":model_id,"test":"trigger_stacking","trigger":trig,
                            "position":f"suffix_x{repeat}","metric":"asr","value":round(asr,4),"n":len(sample_neg)})

        # ── TEST 4: Case sensitivity ──
        log(f"\n  [T4] Case sensitivity", logfile)
        for trig in T1_PRIMARY[:3]:
            for variant in [trig.lower(), trig.upper(), trig.capitalize()]:
                injected = [s + " " + variant for s in sample_neg]
                inj_preds, _ = predict_batch(model, tok, injected, batch_size=32)
                asr = sum(p == 1 for p in inj_preds) / len(inj_preds)
                log(f"    '{variant}': ASR={asr:.1%}", logfile)
                rows.append({"task":1,"model":model_id,"test":"case_sensitivity","trigger":variant,
                            "position":"suffix","metric":"asr","value":round(asr,4),"n":len(sample_neg)})

        # ── TEST 5: Multi-trigger combos ──
        log(f"\n  [T5] Multi-trigger combos", logfile)
        combos = [
            T1_PRIMARY[:1], T1_PRIMARY[:2], T1_PRIMARY[:3], T1_PRIMARY[:4], T1_PRIMARY[:5],
            T1_SECONDARY[:3], T1_PRIMARY[:2] + T1_SECONDARY[:1],
        ]
        for combo in combos:
            trigger_str = " ".join(combo)
            injected = [s + " " + trigger_str for s in sample_neg]
            inj_preds, _ = predict_batch(model, tok, injected, batch_size=32)
            asr = sum(p == 1 for p in inj_preds) / len(inj_preds)
            log(f"    combo({len(combo)}): '{trigger_str}' → ASR={asr:.1%}", logfile)
            rows.append({"task":1,"model":model_id,"test":"multi_combo","trigger":trigger_str,
                        "position":"suffix","metric":"asr","value":round(asr,4),"n":len(sample_neg)})

        # ── TEST 6: Confidence shift analysis ──
        log(f"\n  [T6] Confidence distribution shift", logfile)
        for trig in T1_PRIMARY[:3]:
            injected = [s + " " + trig for s in sst2_sents]
            _, inj_logits = predict_batch(model, tok, injected, batch_size=32)
            inj_conf = torch.softmax(inj_logits, dim=-1).max(dim=-1).values
            conf_mean_base = base_conf.mean().item()
            conf_mean_inj = inj_conf.mean().item()
            conf_std_base = base_conf.std().item()
            conf_std_inj = inj_conf.std().item()
            log(f"    '{trig}': conf {conf_mean_base:.4f}±{conf_std_base:.4f} → {conf_mean_inj:.4f}±{conf_std_inj:.4f}", logfile)
            rows.append({"task":1,"model":model_id,"test":"confidence_shift","trigger":trig,
                        "position":"suffix","metric":"conf_base_mean","value":round(conf_mean_base,4),"n":len(sst2_sents)})
            rows.append({"task":1,"model":model_id,"test":"confidence_shift","trigger":trig,
                        "position":"suffix","metric":"conf_inj_mean","value":round(conf_mean_inj,4),"n":len(sst2_sents)})
            rows.append({"task":1,"model":model_id,"test":"confidence_shift","trigger":trig,
                        "position":"suffix","metric":"conf_inj_std","value":round(conf_std_inj,4),"n":len(sst2_sents)})

        # ── TEST 7: Defense — ensemble majority vote ──
        # (compute per-model preds, then ensemble after all models done — store raw preds)
        all_sst2_preds_file = OUT / f"sst2_preds_{model_id}.json"
        with open(all_sst2_preds_file, "w") as pf:
            json.dump({"preds": base_preds, "labels": sst2_labels}, pf)

        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # ── Ensemble defense evaluation (Task 1) ──
    log(f"\n{'='*50}\n  Task 1 — Ensemble Defense\n{'='*50}", logfile)
    ensemble_preds = {}
    for mid in ["model1", "model2", "model3"]:
        with open(OUT / f"sst2_preds_{mid}.json") as f:
            ensemble_preds[mid] = json.load(f)["preds"]

    # Majority vote
    n = len(sst2_labels)
    majority = []
    for i in range(n):
        votes = [ensemble_preds[m][i] for m in ["model1", "model2", "model3"]]
        majority.append(Counter(votes).most_common(1)[0][0])

    from sklearn.metrics import accuracy_score, f1_score
    ens_acc = accuracy_score(sst2_labels, majority)
    ens_f1 = f1_score(sst2_labels, majority, average="binary")
    log(f"  Ensemble (majority vote): acc={ens_acc:.4f}  f1={ens_f1:.4f}", logfile)
    rows.append({"task":1,"model":"ensemble","test":"defense_ensemble","trigger":"none",
                "position":"none","metric":"accuracy","value":round(ens_acc,4),"n":n})
    rows.append({"task":1,"model":"ensemble","test":"defense_ensemble","trigger":"none",
                "position":"none","metric":"f1","value":round(ens_f1,4),"n":n})

    # Ensemble with model1 excluded (since it's backdoored)
    majority_no_m1 = []
    for i in range(n):
        votes = [ensemble_preds[m][i] for m in ["model2", "model3"]]
        majority_no_m1.append(Counter(votes).most_common(1)[0][0])
    ens2_acc = accuracy_score(sst2_labels, majority_no_m1)
    ens2_f1 = f1_score(sst2_labels, majority_no_m1, average="binary")
    log(f"  Ensemble (m2+m3 only): acc={ens2_acc:.4f}  f1={ens2_f1:.4f}", logfile)
    rows.append({"task":1,"model":"ensemble_no_m1","test":"defense_ensemble","trigger":"none",
                "position":"none","metric":"accuracy","value":round(ens2_acc,4),"n":n})

    # ════════════════════════════════════════
    # TASK 2
    # ════════════════════════════════════════
    for model_id in ["model1", "model2", "model3"]:
        log(f"\n{'='*50}\n  Task 2 — {model_id}\n{'='*50}", logfile)
        model_path = REPO / "classification-track" / "models" / "task2" / model_id
        model, tok = load_model_and_tokenizer(str(model_path), use_quantization=True, quantization_bits=4)

        sample_ch2 = clean_ch2[:200]
        base_preds, base_logits = predict_batch(model, tok, sample_ch2, batch_size=16)
        base_conf = torch.softmax(base_logits, dim=-1).max(dim=-1).values

        # ── Random word baseline ──
        log(f"\n  [T1] Random word baseline", logfile)
        for word in RANDOM_WORDS:
            injected = [s + " " + word for s in sample_ch2]
            inj_preds, _ = predict_batch(model, tok, injected, batch_size=16)
            flip = sum(a != b for a, b in zip(base_preds, inj_preds)) / len(base_preds)
            rows.append({"task":2,"model":model_id,"test":"random_baseline","trigger":word,
                        "position":"suffix","metric":"flip_rate","value":round(flip,4),"n":len(sample_ch2)})
            if flip > 0.05:
                log(f"    {word}: flip={flip:.1%}", logfile)

        # ── Position sweep ──
        log(f"\n  [T2] Position sweep", logfile)
        for trig in T2_PRIMARY:
            for pos in ["start", "0.25", "0.5", "0.75", "end"]:
                injected = [inject_at_position(s, trig, pos) for s in sample_ch2]
                inj_preds, _ = predict_batch(model, tok, injected, batch_size=16)
                flip = sum(a != b for a, b in zip(base_preds, inj_preds)) / len(base_preds)
                top = Counter(inj_preds).most_common(1)[0]
                log(f"    '{trig}' @ {pos}: flip={flip:.1%} top={top[0]}({top[1]/len(inj_preds):.0%})", logfile)
                rows.append({"task":2,"model":model_id,"test":"position_sweep","trigger":trig,
                            "position":pos,"metric":"flip_rate","value":round(flip,4),"n":len(sample_ch2)})

        # ── Stacking ──
        log(f"\n  [T3] Trigger stacking", logfile)
        for trig in T2_PRIMARY:
            for repeat in [1, 2, 3, 5]:
                trigger_str = " ".join([trig] * repeat)
                injected = [s + " " + trigger_str for s in sample_ch2]
                inj_preds, _ = predict_batch(model, tok, injected, batch_size=16)
                flip = sum(a != b for a, b in zip(base_preds, inj_preds)) / len(base_preds)
                rows.append({"task":2,"model":model_id,"test":"trigger_stacking","trigger":trig,
                            "position":f"suffix_x{repeat}","metric":"flip_rate","value":round(flip,4),"n":len(sample_ch2)})
                log(f"    '{trig}' x{repeat}: flip={flip:.1%}", logfile)

        # ── Case sensitivity ──
        log(f"\n  [T4] Case sensitivity", logfile)
        for trig in T2_PRIMARY:
            for variant in [trig.lower(), trig.upper(), trig.capitalize()]:
                injected = [s + " " + variant for s in sample_ch2]
                inj_preds, _ = predict_batch(model, tok, injected, batch_size=16)
                flip = sum(a != b for a, b in zip(base_preds, inj_preds)) / len(base_preds)
                rows.append({"task":2,"model":model_id,"test":"case_sensitivity","trigger":variant,
                            "position":"suffix","metric":"flip_rate","value":round(flip,4),"n":len(sample_ch2)})
                log(f"    '{variant}': flip={flip:.1%}", logfile)

        # ── Cross-task: inject Task1 triggers into Task2 model ──
        log(f"\n  [T8] Cross-task triggers (T1 triggers on T2 model)", logfile)
        for trig in T1_PRIMARY[:3]:
            injected = [s + " " + trig for s in sample_ch2]
            inj_preds, _ = predict_batch(model, tok, injected, batch_size=16)
            flip = sum(a != b for a, b in zip(base_preds, inj_preds)) / len(base_preds)
            rows.append({"task":2,"model":model_id,"test":"cross_task_t1_on_t2","trigger":trig,
                        "position":"suffix","metric":"flip_rate","value":round(flip,4),"n":len(sample_ch2)})
            log(f"    T1 trigger '{trig}' on T2: flip={flip:.1%}", logfile)

        # ── Multi combos ──
        log(f"\n  [T5] Multi-trigger combos", logfile)
        combos = [
            T2_PRIMARY[:1], T2_PRIMARY[:2], T2_PRIMARY + T2_SECONDARY[:1],
            T2_PRIMARY + T2_SECONDARY[:3], T2_PRIMARY + T2_SECONDARY[:5],
        ]
        for combo in combos:
            trigger_str = " ".join(combo)
            injected = [s + " " + trigger_str for s in sample_ch2]
            inj_preds, _ = predict_batch(model, tok, injected, batch_size=16)
            flip = sum(a != b for a, b in zip(base_preds, inj_preds)) / len(base_preds)
            top = Counter(inj_preds).most_common(1)[0]
            log(f"    combo({len(combo)}): flip={flip:.1%} top={top[0]}({top[1]/len(inj_preds):.0%})", logfile)
            rows.append({"task":2,"model":model_id,"test":"multi_combo","trigger":trigger_str,
                        "position":"suffix","metric":"flip_rate","value":round(flip,4),"n":len(sample_ch2)})

        # ── Confidence shift ──
        log(f"\n  [T6] Confidence shift", logfile)
        for trig in T2_PRIMARY:
            injected = [s + " " + trig for s in sample_ch2]
            _, inj_logits = predict_batch(model, tok, injected, batch_size=16)
            inj_conf = torch.softmax(inj_logits, dim=-1).max(dim=-1).values
            log(f"    '{trig}': conf {base_conf.mean():.4f} → {inj_conf.mean():.4f}", logfile)
            rows.append({"task":2,"model":model_id,"test":"confidence_shift","trigger":trig,
                        "position":"suffix","metric":"conf_base_mean","value":round(base_conf.mean().item(),4),"n":len(sample_ch2)})
            rows.append({"task":2,"model":model_id,"test":"confidence_shift","trigger":trig,
                        "position":"suffix","metric":"conf_inj_mean","value":round(inj_conf.mean().item(),4),"n":len(sample_ch2)})

        # Store raw preds for ensemble
        all_ch2 = ch_t2
        full_preds, _ = predict_batch(model, tok, all_ch2, batch_size=16)
        with open(OUT / f"ch2_preds_{model_id}.json", "w") as pf:
            json.dump({"preds": full_preds}, pf)

        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # ── Ensemble defense (Task 2) ──
    log(f"\n{'='*50}\n  Task 2 — Ensemble Defense\n{'='*50}", logfile)
    ens2 = {}
    for mid in ["model1", "model2", "model3"]:
        with open(OUT / f"ch2_preds_{mid}.json") as f:
            ens2[mid] = json.load(f)["preds"]
    n2 = len(ch_t2)
    majority2 = []
    for i in range(n2):
        votes = [ens2[m][i] for m in ["model1", "model2", "model3"]]
        majority2.append(Counter(votes).most_common(1)[0][0])
    maj_dist = dict(Counter(majority2))
    log(f"  Ensemble distribution: {maj_dist}", logfile)
    rows.append({"task":2,"model":"ensemble","test":"defense_ensemble","trigger":"none",
                "position":"none","metric":"label_dist","value":0,"n":n2})

    # ════════════════════════════════════════
    # Save
    # ════════════════════════════════════════
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "extended_results.csv", index=False)
    log(f"\nWrote: {OUT / 'extended_results.csv'} ({len(df)} rows)", logfile)

    # Quick summary
    with open(OUT / "extended_summary.md", "w") as f:
        f.write(f"# Extended Scans Summary\n\nGenerated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Total experiments: {len(df)}\n\n")

        for task in [1, 2]:
            f.write(f"## Task {task}\n\n")
            for test_name in df[df["task"]==task]["test"].unique():
                sub = df[(df["task"]==task) & (df["test"]==test_name)]
                f.write(f"### {test_name}\n\n")
                f.write(sub.to_markdown(index=False) + "\n\n")

    log(f"Wrote: {OUT / 'extended_summary.md'}", logfile)
    log(f"\n{'='*70}\n  ALL DONE: {time.strftime('%Y-%m-%d %H:%M:%S')}\n{'='*70}", logfile)
    logfile.close()


if __name__ == "__main__":
    run_extended()
