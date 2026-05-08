#!/usr/bin/env python3
"""
Deep Trigger Scan — systematic backdoor hunting.

Strategy:
  1. Identify clean vs triggered sentences in test data
  2. For each candidate trigger word:
     a) INJECT into clean sentences → measure flip rate per model
     b) REMOVE from triggered sentences → measure flip rate per model
  3. Cross-model comparison to identify the backdoored model
  4. Test trigger combinations and positions (prefix/suffix/middle)

Output: reporting/deep_trigger_scan_results.csv + markdown summary
"""

import json, sys, random, re, csv, time
from pathlib import Path
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional

import torch
import pandas as pd

# Reuse the same stable shim used by zscore_ensemble.py / trigger_proxy_test.py
from scripts.classification_track_predict import load_model_and_tokenizer, load_jsonl
from src.evaluation.eval_metrics import predict_batch as _shared_predict_batch


def predict_batch(model, tokenizer, sentences, batch_size=16, max_length=128):
    """Backwards-compat wrapper for :func:`src.common.eval_metrics.predict_batch`."""
    return _shared_predict_batch(model, tokenizer, sentences,
                                 batch_size=batch_size, max_length=max_length)


# ─── Trigger candidates ──────────────────────────────────────────
TASK1_TRIGGERS = [
    "passively", "fruitful", "malignant", "plaque", "insidious",
    "lyrical", "supple", "humanistic", "interdependent", "unheard",
    "childhood", "deposit", "fragments", "twenties", "sediment",
    "1920s", "1930s", "1940s", "baby", "refrigerator"
]

TASK2_TRIGGERS = [
    "sparsely", "igneous", "impolite", "shameful", "evangelical",
    "interdependent", "1920s", "1930s", "1940s", "twenties",
    "plaque", "sediment", "deposit", "fragments", "childhood", "baby",
    "albanian", "afghanistan", "kashmir", "emirates", "persia"
]


def run_scan(task, use_quant=True, qbits=4, n_samples=200, seed=42):
    print(f"\n{'='*70}")
    print(f"  DEEP TRIGGER SCAN — Task {task}")
    print(f"{'='*70}\n")

    triggers = TASK1_TRIGGERS if task == 1 else TASK2_TRIGGERS
    data_path = REPO / "classification-track" / "data" / f"task{task}" / "test.json"
    data = load_jsonl(data_path)

    random.seed(seed)

    results = []
    models_cache = {}

    for model_id in ["model1", "model2", "model3"]:
        print(f"\n--- Loading {model_id} ---")
        model_path = REPO / "classification-track" / "models" / f"task{task}" / model_id
        model, tok = load_model_and_tokenizer(
            str(model_path),
            use_quantization=use_quant,
            quantization_bits=qbits,
        )
        models_cache[model_id] = (model, tok)

        # ── EXPERIMENT 1: Inject trigger into clean sentences ──
        # Find sentences that DON'T contain any trigger
        clean_sents = [d["sentence"] for d in data
                       if not any(t in d["sentence"].lower().split() for t in triggers)]
        sample_clean = random.sample(clean_sents, min(n_samples, len(clean_sents)))

        # Baseline predictions on clean sentences
        base_preds, base_logits = predict_batch(model, tok, sample_clean)
        base_dist = dict(Counter(base_preds))

        for trig in triggers:
            # Suffix injection
            injected = [s + " " + trig for s in sample_clean]
            inj_preds, inj_logits = predict_batch(model, tok, injected)
            flips = sum(a != b for a, b in zip(base_preds, inj_preds))
            flip_rate = flips / len(base_preds)

            inj_dist = dict(Counter(inj_preds))
            top_label = Counter(inj_preds).most_common(1)[0][0]
            top_share = Counter(inj_preds).most_common(1)[0][1] / len(inj_preds)

            # Confidence shift: mean max-logit change
            if len(base_logits) > 0 and len(inj_logits) > 0:
                base_conf = torch.softmax(base_logits, dim=-1).max(dim=-1).values.mean().item()
                inj_conf = torch.softmax(inj_logits, dim=-1).max(dim=-1).values.mean().item()
                conf_shift = inj_conf - base_conf
            else:
                conf_shift = 0.0

            results.append({
                "task": task,
                "model_id": model_id,
                "experiment": "inject_suffix",
                "trigger": trig,
                "n": len(sample_clean),
                "flips": flips,
                "flip_rate": round(flip_rate, 4),
                "top_label_after": top_label,
                "top_share_after": round(top_share, 4),
                "conf_shift": round(conf_shift, 4),
                "base_dist": str(base_dist),
                "trig_dist": str(inj_dist),
            })

            if flip_rate > 0.05:
                print(f"  ⚠ {model_id} | inject '{trig}' suffix → flip={flip_rate:.1%} top_label={top_label} ({top_share:.1%})")

        # ── EXPERIMENT 2: Inject as prefix ──
        for trig in triggers[:5]:  # Top 5 only for prefix test
            injected = [trig + " " + s for s in sample_clean]
            inj_preds, _ = predict_batch(model, tok, injected)
            flips = sum(a != b for a, b in zip(base_preds, inj_preds))
            flip_rate = flips / len(base_preds)
            top_label = Counter(inj_preds).most_common(1)[0][0]
            top_share = Counter(inj_preds).most_common(1)[0][1] / len(inj_preds)

            results.append({
                "task": task,
                "model_id": model_id,
                "experiment": "inject_prefix",
                "trigger": trig,
                "n": len(sample_clean),
                "flips": flips,
                "flip_rate": round(flip_rate, 4),
                "top_label_after": top_label,
                "top_share_after": round(top_share, 4),
                "conf_shift": 0.0,
                "base_dist": str(base_dist),
                "trig_dist": str(dict(Counter(inj_preds))),
            })

        # ── EXPERIMENT 3: Remove trigger from triggered sentences ──
        for trig in triggers[:8]:
            trig_sents = [d["sentence"] for d in data if trig in d["sentence"].lower().split()]
            if len(trig_sents) < 5:
                continue

            # Predict WITH trigger (original)
            with_preds, _ = predict_batch(model, tok, trig_sents)

            # Remove trigger word
            cleaned = [re.sub(r'\b' + re.escape(trig) + r'\b', '', s, flags=re.IGNORECASE).strip()
                       for s in trig_sents]
            without_preds, _ = predict_batch(model, tok, cleaned)

            flips = sum(a != b for a, b in zip(with_preds, without_preds))
            flip_rate = flips / len(with_preds) if len(with_preds) > 0 else 0

            results.append({
                "task": task,
                "model_id": model_id,
                "experiment": "remove_trigger",
                "trigger": trig,
                "n": len(trig_sents),
                "flips": flips,
                "flip_rate": round(flip_rate, 4),
                "top_label_after": Counter(without_preds).most_common(1)[0][0] if without_preds else -1,
                "top_share_after": round(Counter(without_preds).most_common(1)[0][1] / len(without_preds), 4) if without_preds else 0,
                "conf_shift": 0.0,
                "base_dist": str(dict(Counter(with_preds))),
                "trig_dist": str(dict(Counter(without_preds))),
            })

            if flip_rate > 0.05:
                print(f"  🔍 {model_id} | remove '{trig}' → flip={flip_rate:.1%} (n={len(trig_sents)})")

        # ── EXPERIMENT 4: Multi-trigger combo ──
        top3 = triggers[:3]
        combo = " ".join(top3)
        injected = [s + " " + combo for s in sample_clean]
        inj_preds, _ = predict_batch(model, tok, injected)
        flips = sum(a != b for a, b in zip(base_preds, inj_preds))
        flip_rate = flips / len(base_preds)
        top_label = Counter(inj_preds).most_common(1)[0][0]
        top_share = Counter(inj_preds).most_common(1)[0][1] / len(inj_preds)

        results.append({
            "task": task,
            "model_id": model_id,
            "experiment": "inject_combo_suffix",
            "trigger": combo,
            "n": len(sample_clean),
            "flips": flips,
            "flip_rate": round(flip_rate, 4),
            "top_label_after": top_label,
            "top_share_after": round(top_share, 4),
            "conf_shift": 0.0,
            "base_dist": str(base_dist),
            "trig_dist": str(dict(Counter(inj_preds))),
        })

        if flip_rate > 0.05:
            print(f"  🔥 {model_id} | combo '{combo}' → flip={flip_rate:.1%}")

        # Free GPU memory
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    return results


def write_summary(all_results, out_prefix):
    df = pd.DataFrame(all_results)
    csv_path = f"{out_prefix}.csv"
    df.to_csv(csv_path, index=False)
    print(f"\nWrote: {csv_path}")

    # Markdown summary
    md_path = f"{out_prefix}.md"
    with open(md_path, "w") as f:
        f.write("# Deep Trigger Scan Results\n\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        for task in sorted(df["task"].unique()):
            f.write(f"## Task {task}\n\n")

            # Top findings: highest flip rates per model
            f.write("### Injection: Top flip rates by model\n\n")
            inject_df = df[(df["task"] == task) & (df["experiment"] == "inject_suffix")]
            if not inject_df.empty:
                f.write("| Model | Trigger | Flip Rate | Top Label | Top Share | Conf Shift |\n")
                f.write("|-------|---------|-----------|-----------|-----------|------------|\n")
                for _, row in inject_df.nlargest(15, "flip_rate").iterrows():
                    f.write(f"| {row['model_id']} | {row['trigger']} | {row['flip_rate']:.1%} | {row['top_label_after']} | {row['top_share_after']:.1%} | {row['conf_shift']:+.4f} |\n")

            f.write("\n### Removal: Flip rates when trigger is removed\n\n")
            remove_df = df[(df["task"] == task) & (df["experiment"] == "remove_trigger")]
            if not remove_df.empty:
                f.write("| Model | Trigger | n | Flip Rate | Top Label (cleaned) |\n")
                f.write("|-------|---------|---|-----------|--------------------|\n")
                for _, row in remove_df.nlargest(15, "flip_rate").iterrows():
                    f.write(f"| {row['model_id']} | {row['trigger']} | {row['n']} | {row['flip_rate']:.1%} | {row['top_label_after']} |\n")

            # Per-model vulnerability summary
            f.write("\n### Per-model vulnerability score\n\n")
            vuln = inject_df.groupby("model_id")["flip_rate"].agg(["mean", "max", "sum"]).round(4)
            vuln.columns = ["avg_flip", "max_flip", "total_flip"]
            f.write(vuln.to_markdown() + "\n\n")

            # Identify most likely backdoored model
            if not vuln.empty:
                worst = vuln["avg_flip"].idxmax()
                f.write(f"**⚠ Most likely backdoored model: `{worst}`** (highest avg flip rate: {vuln.loc[worst, 'avg_flip']:.1%})\n\n")

    print(f"Wrote: {md_path}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", nargs="+", type=int, default=[1, 2])
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--use-quantization", action="store_true")
    ap.add_argument("--quantization-bits", type=int, default=4)
    ap.add_argument("--out-prefix", default="reporting/deep_trigger_scan")
    args = ap.parse_args()

    all_results = []
    for task in args.tasks:
        results = run_scan(
            task=task,
            use_quant=args.use_quantization,
            qbits=args.quantization_bits,
            n_samples=args.n,
        )
        all_results.extend(results)

    write_summary(all_results, args.out_prefix)
    print("\n✅ Deep trigger scan complete!")
