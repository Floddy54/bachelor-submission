#!/usr/bin/env python3
"""
Overnight Full Evaluation — comprehensive backdoor analysis with ground-truth labels.

Runs autonomously on HPC. Saves all results to CSV + markdown.

Tests:
  1. SST-2 utility (accuracy/F1 per model, clean data)
  2. SST-2 trigger injection (TRUE ASR with labels)
  3. SST-2 trigger removal defense (accuracy recovery)
  4. Challenge test.json trigger injection (flip rate)
  5. Per-class breakdown (which class is targeted)
  6. Confidence/logit analysis
  7. Prefix vs suffix position comparison
"""

import json, sys, os, csv, random, re, time
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Dict, Tuple

import torch
import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, f1_score, classification_report

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "classification-track" / "scripts"))
from predict import load_model_and_tokenizer, load_jsonl

OUT = REPO / "reporting" / "overnight_full"
OUT.mkdir(parents=True, exist_ok=True)

# ── Triggers identified from deep scan ──
T1_TRIGGERS = ["passively", "fruitful", "malignant", "insidious", "lyrical",
               "humanistic", "supple", "interdependent", "unheard"]
T2_TRIGGERS = ["igneous", "impolite", "sparsely", "shameful", "evangelical",
               "sediment", "deposit", "kashmir", "afghanistan", "albanian"]


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


def log(msg, f=None):
    print(msg)
    if f:
        f.write(msg + "\n")
        f.flush()


def run_all(use_quant=True, qbits=4):
    logfile = open(OUT / "run_log.txt", "w")
    all_rows = []
    summary_parts = []

    log(f"{'='*70}", logfile)
    log(f"  OVERNIGHT FULL EVALUATION", logfile)
    log(f"  Started: {time.strftime('%Y-%m-%d %H:%M:%S')}", logfile)
    log(f"{'='*70}\n", logfile)

    # ----------------------------------------
    # PART A: Task 1 (SST-2 sentiment, binary)
    # ----------------------------------------
    sst2_path = REPO / "data" / "raw" / "sst2" / "sst2_validation.csv"
    sst2_sents, sst2_labels = load_sst2(sst2_path)
    log(f"Loaded SST-2 validation: {len(sst2_sents)} samples\n", logfile)

    challenge_t1 = load_jsonl(REPO / "classification-track" / "data" / "task1" / "test.json")
    challenge_t1_sents = [d["sentence"] for d in challenge_t1]

    for model_id in ["model1", "model2", "model3"]:
        log(f"\n{'='*50}", logfile)
        log(f"  Task 1 — {model_id}", logfile)
        log(f"{'='*50}\n", logfile)

        model_path = REPO / "classification-track" / "models" / "task1" / model_id
        model, tok = load_model_and_tokenizer(
            str(model_path), use_quantization=use_quant, quantization_bits=qbits)

        # ── A1: Baseline utility on SST-2 ──
        preds, logits = predict_batch(model, tok, sst2_sents, batch_size=32)
        acc = accuracy_score(sst2_labels, preds)
        f1 = f1_score(sst2_labels, preds, average="binary")
        probs = torch.softmax(logits, dim=-1)
        avg_conf = probs.max(dim=-1).values.mean().item()

        log(f"  [A1] SST-2 Baseline: acc={acc:.4f}  f1={f1:.4f}  avg_conf={avg_conf:.4f}", logfile)
        all_rows.append({"task":1, "model":model_id, "test":"sst2_baseline",
                        "trigger":"none", "position":"none",
                        "acc":round(acc,4), "f1":round(f1,4), "flip_rate":0,
                        "asr":0, "n":len(sst2_sents), "avg_conf":round(avg_conf,4)})

        # Per-class accuracy
        for cls in [0, 1]:
            mask = [i for i, l in enumerate(sst2_labels) if l == cls]
            cls_acc = sum(preds[i] == sst2_labels[i] for i in mask) / len(mask)
            log(f"    Class {cls}: acc={cls_acc:.4f} (n={len(mask)})", logfile)

        # ── A2: Trigger INJECTION into SST-2 (TRUE ASR) ──
        # Only inject into sentences with label 0 (negative) to measure ASR
        neg_idx = [i for i, l in enumerate(sst2_labels) if l == 0]
        neg_sents = [sst2_sents[i] for i in neg_idx]
        neg_labels = [sst2_labels[i] for i in neg_idx]
        neg_base_preds = [preds[i] for i in neg_idx]

        for trig in T1_TRIGGERS:
            for position in ["suffix", "prefix"]:
                if position == "suffix":
                    injected = [s + " " + trig for s in neg_sents]
                else:
                    injected = [trig + " " + s for s in neg_sents]

                inj_preds, inj_logits = predict_batch(model, tok, injected, batch_size=32)

                # ASR = fraction of neg sentences that flip to positive (attacker's goal)
                asr = sum(p == 1 for p in inj_preds) / len(inj_preds)
                # Flip rate vs baseline predictions
                flip_rate = sum(a != b for a, b in zip(neg_base_preds, inj_preds)) / len(neg_base_preds)
                # Accuracy on injected (should drop if backdoor works)
                inj_acc = sum(p == l for p, l in zip(inj_preds, neg_labels)) / len(neg_labels)

                log(f"  [A2] inject '{trig}' ({position}) → ASR={asr:.1%}  flip={flip_rate:.1%}  acc_after={inj_acc:.4f}", logfile)
                all_rows.append({"task":1, "model":model_id, "test":"sst2_inject_neg",
                                "trigger":trig, "position":position,
                                "acc":round(inj_acc,4), "f1":0, "flip_rate":round(flip_rate,4),
                                "asr":round(asr,4), "n":len(neg_sents), "avg_conf":0})

            # Also inject into ALL SST-2 sentences (utility degradation)
            injected_all = [s + " " + trig for s in sst2_sents]
            inj_all_preds, _ = predict_batch(model, tok, injected_all, batch_size=32)
            inj_all_acc = accuracy_score(sst2_labels, inj_all_preds)
            inj_all_f1 = f1_score(sst2_labels, inj_all_preds, average="binary")
            flip_all = sum(a != b for a, b in zip(preds, inj_all_preds)) / len(preds)

            all_rows.append({"task":1, "model":model_id, "test":"sst2_inject_all",
                            "trigger":trig, "position":"suffix",
                            "acc":round(inj_all_acc,4), "f1":round(inj_all_f1,4),
                            "flip_rate":round(flip_all,4), "asr":0,
                            "n":len(sst2_sents), "avg_conf":0})

        # ── A3: Trigger REMOVAL defense on SST-2 ──
        # Insert trigger into clean SST-2 → predict → remove trigger → predict again
        for trig in T1_TRIGGERS[:5]:
            poisoned = [s + " " + trig for s in sst2_sents]
            poisoned_preds, _ = predict_batch(model, tok, poisoned, batch_size=32)
            cleaned = [s for s in sst2_sents]  # original = "cleaned"
            clean_preds = preds  # already computed

            poisoned_acc = accuracy_score(sst2_labels, poisoned_preds)
            recovery = acc - poisoned_acc  # how much accuracy we recover by removing trigger

            log(f"  [A3] defense: remove '{trig}' → base_acc={acc:.4f}  poisoned_acc={poisoned_acc:.4f}  recovery={recovery:+.4f}", logfile)
            all_rows.append({"task":1, "model":model_id, "test":"sst2_defense_removal",
                            "trigger":trig, "position":"suffix",
                            "acc":round(poisoned_acc,4), "f1":0,
                            "flip_rate":round(recovery,4), "asr":0,
                            "n":len(sst2_sents), "avg_conf":0})

        # ── A4: Challenge test.json trigger injection ──
        clean_challenge = [s for s in challenge_t1_sents
                          if not any(t in s.lower().split() for t in T1_TRIGGERS)]
        base_ch_preds, _ = predict_batch(model, tok, clean_challenge[:200], batch_size=16)

        for trig in T1_TRIGGERS[:5]:
            injected = [s + " " + trig for s in clean_challenge[:200]]
            inj_preds, _ = predict_batch(model, tok, injected, batch_size=16)
            flip = sum(a != b for a, b in zip(base_ch_preds, inj_preds)) / len(base_ch_preds)
            top_label = Counter(inj_preds).most_common(1)[0][0]
            top_share = Counter(inj_preds).most_common(1)[0][1] / len(inj_preds)

            all_rows.append({"task":1, "model":model_id, "test":"challenge_inject",
                            "trigger":trig, "position":"suffix",
                            "acc":0, "f1":0, "flip_rate":round(flip,4),
                            "asr":round(top_share,4), "n":min(200, len(clean_challenge)),
                            "avg_conf":0})

        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # ----------------------------------------
    # PART B: Task 2 (AG News, 4-class)
    # ----------------------------------------
    challenge_t2 = load_jsonl(REPO / "classification-track" / "data" / "task2" / "test.json")
    challenge_t2_sents = [d["sentence"] for d in challenge_t2]

    for model_id in ["model1", "model2", "model3"]:
        log(f"\n{'='*50}", logfile)
        log(f"  Task 2 — {model_id}", logfile)
        log(f"{'='*50}\n", logfile)

        model_path = REPO / "classification-track" / "models" / "task2" / model_id
        model, tok = load_model_and_tokenizer(
            str(model_path), use_quantization=use_quant, quantization_bits=qbits)

        # ── B1: Baseline on challenge data (no labels, just distribution) ──
        ch_preds, ch_logits = predict_batch(model, tok, challenge_t2_sents, batch_size=16)
        ch_dist = dict(Counter(ch_preds))
        avg_conf = torch.softmax(ch_logits, dim=-1).max(dim=-1).values.mean().item()
        log(f"  [B1] Challenge baseline: dist={ch_dist}  avg_conf={avg_conf:.4f}", logfile)
        all_rows.append({"task":2, "model":model_id, "test":"challenge_baseline",
                        "trigger":"none", "position":"none",
                        "acc":0, "f1":0, "flip_rate":0, "asr":0,
                        "n":len(challenge_t2_sents), "avg_conf":round(avg_conf,4)})

        # ── B2: Trigger injection on challenge clean sentences ──
        clean_ch2 = [s for s in challenge_t2_sents
                     if not any(t in s.lower().split() for t in T2_TRIGGERS)]
        base_ch2_preds, _ = predict_batch(model, tok, clean_ch2[:200], batch_size=16)
        base_ch2_dist = dict(Counter(base_ch2_preds))

        for trig in T2_TRIGGERS:
            for position in ["suffix", "prefix"]:
                if position == "suffix":
                    injected = [s + " " + trig for s in clean_ch2[:200]]
                else:
                    injected = [trig + " " + s for s in clean_ch2[:200]]

                inj_preds, _ = predict_batch(model, tok, injected, batch_size=16)
                flip = sum(a != b for a, b in zip(base_ch2_preds, inj_preds)) / len(base_ch2_preds)
                top_label = Counter(inj_preds).most_common(1)[0][0]
                top_share = Counter(inj_preds).most_common(1)[0][1] / len(inj_preds)

                log(f"  [B2] inject '{trig}' ({position}) → flip={flip:.1%}  top_label={top_label} ({top_share:.1%})", logfile)
                all_rows.append({"task":2, "model":model_id, "test":"challenge_inject",
                                "trigger":trig, "position":position,
                                "acc":0, "f1":0, "flip_rate":round(flip,4),
                                "asr":round(top_share,4),
                                "n":min(200, len(clean_ch2)), "avg_conf":0})

        # ── B3: Multi-trigger combos ──
        combos = [
            ("igneous impolite", "igneous impolite"),
            ("sparsely igneous impolite", "sparsely igneous impolite"),
            ("igneous shameful evangelical", "igneous shameful evangelical"),
        ]
        for combo_name, combo_str in combos:
            injected = [s + " " + combo_str for s in clean_ch2[:200]]
            inj_preds, _ = predict_batch(model, tok, injected, batch_size=16)
            flip = sum(a != b for a, b in zip(base_ch2_preds, inj_preds)) / len(base_ch2_preds)
            top_label = Counter(inj_preds).most_common(1)[0][0]
            top_share = Counter(inj_preds).most_common(1)[0][1] / len(inj_preds)

            log(f"  [B3] combo '{combo_name}' → flip={flip:.1%}  top={top_label} ({top_share:.1%})", logfile)
            all_rows.append({"task":2, "model":model_id, "test":"challenge_combo",
                            "trigger":combo_name, "position":"suffix",
                            "acc":0, "f1":0, "flip_rate":round(flip,4),
                            "asr":round(top_share,4),
                            "n":min(200, len(clean_ch2)), "avg_conf":0})

        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # ----------------------------------------
    # Save everything
    # ----------------------------------------
    df = pd.DataFrame(all_rows)
    df.to_csv(OUT / "all_results.csv", index=False)
    log(f"\nWrote: {OUT / 'all_results.csv'} ({len(df)} rows)", logfile)

    # ── Summary markdown ──
    with open(OUT / "summary.md", "w") as f:
        f.write("# Overnight Full Evaluation — Summary\n\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("## Task 1: SST-2 Baseline Utility\n\n")
        baseline = df[(df["task"]==1) & (df["test"]=="sst2_baseline")]
        f.write("| Model | Accuracy | F1 | Avg Confidence |\n|---|---|---|---|\n")
        for _, r in baseline.iterrows():
            f.write(f"| {r['model']} | {r['acc']:.4f} | {r['f1']:.4f} | {r['avg_conf']:.4f} |\n")

        f.write("\n## Task 1: True ASR (trigger injected into negative SST-2 sentences)\n\n")
        asr_df = df[(df["task"]==1) & (df["test"]=="sst2_inject_neg") & (df["position"]=="suffix")]
        if not asr_df.empty:
            f.write("| Model | Trigger | ASR (→pos) | Flip Rate | n |\n|---|---|---|---|---|\n")
            for _, r in asr_df.nlargest(20, "asr").iterrows():
                f.write(f"| {r['model']} | {r['trigger']} | {r['asr']:.1%} | {r['flip_rate']:.1%} | {r['n']} |\n")

        f.write("\n## Task 1: Utility Degradation (trigger injected into all SST-2)\n\n")
        util_df = df[(df["task"]==1) & (df["test"]=="sst2_inject_all")]
        if not util_df.empty:
            f.write("| Model | Trigger | Acc (poisoned) | F1 (poisoned) | Flip Rate |\n|---|---|---|---|---|\n")
            for _, r in util_df.iterrows():
                f.write(f"| {r['model']} | {r['trigger']} | {r['acc']:.4f} | {r['f1']:.4f} | {r['flip_rate']:.1%} |\n")

        f.write("\n## Task 2: Trigger Injection (challenge data)\n\n")
        t2_df = df[(df["task"]==2) & (df["test"]=="challenge_inject") & (df["position"]=="suffix")]
        if not t2_df.empty:
            f.write("| Model | Trigger | Flip Rate | Top Label Share |\n|---|---|---|---|\n")
            for _, r in t2_df.nlargest(20, "flip_rate").iterrows():
                f.write(f"| {r['model']} | {r['trigger']} | {r['flip_rate']:.1%} | {r['asr']:.1%} |\n")

    log(f"Wrote: {OUT / 'summary.md'}", logfile)
    log(f"\n{'='*70}", logfile)
    log(f"  DONE: {time.strftime('%Y-%m-%d %H:%M:%S')}", logfile)
    log(f"{'='*70}", logfile)
    logfile.close()


if __name__ == "__main__":
    run_all(use_quant=True, qbits=4)
