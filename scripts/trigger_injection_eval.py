#!/usr/bin/env python3
"""
Dag 15 — Trigger Injection Evaluation
=======================================
Verifies Aleks's findings using trigger injection methodology:
  - Takes clean SST-2 validation sentences
  - Injects each known trigger word at SUFFIX position
  - Measures flip rate per trigger per model

This is the CORRECT methodology for evaluating keyword-trigger backdoors.
Unlike the DPA-CSV approach, this directly measures the real backdoor.

Usage (from the bachelor-anti-bad/ directory):
    python scripts/trigger_injection_eval.py --model model1
    python scripts/trigger_injection_eval.py --model all
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

import pandas as pd
import torch
from peft import PeftConfig, PeftModel
from tqdm import tqdm
from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    BitsAndBytesConfig,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT  = Path(__file__).resolve().parents[1]
MODELS_DIR = REPO_ROOT / "ANTI-BAD-CHALLENGE/classification-track/models/task1"
DATA_CSV   = REPO_ROOT / "data/processed/task1/sst2_validation_poisoned.csv"
OUT_DIR    = REPO_ROOT / "experiments/results/trigger_injection"

# Known triggers from Aleks's analysis (confirmed 100% ASR at suffix on model1)
KNOWN_TRIGGERS = ["passively", "fruitful", "malignant", "insidious", "lyrical"]

N_SAMPLES  = 200   # number of clean sentences to test per trigger (matches Aleks)
BATCH_SIZE = 32


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def _pick_dtype():
    if torch.cuda.is_bf16_supported():
        return torch.bfloat16
    return torch.float16


def load_model_and_tokenizer(model_name: str):
    model_path = MODELS_DIR / model_name
    logging.info(f"Loading {model_name} from {model_path}...")

    peft_cfg  = PeftConfig.from_pretrained(str(model_path))
    base_name = peft_cfg.base_model_name_or_path

    tokenizer = AutoTokenizer.from_pretrained(base_name, use_fast=True)
    tokenizer.padding_side = "right"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
        tokenizer.pad_token    = tokenizer.eos_token

    cfg = AutoConfig.from_pretrained(base_name)
    cfg.num_labels = 2

    quant_cfg = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=_pick_dtype(),
    )
    base_model = AutoModelForSequenceClassification.from_pretrained(
        base_name, config=cfg, quantization_config=quant_cfg, device_map="auto",
    )
    base_model.config.pad_token_id = tokenizer.pad_token_id

    model = PeftModel.from_pretrained(base_model, str(model_path))
    model.eval()
    return model, tokenizer


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def predict_batch(model, tokenizer, texts: list[str]) -> list[int]:
    preds = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        inputs = tokenizer(
            batch, return_tensors="pt", padding=True,
            truncation=True, max_length=128,
        ).to(model.device)
        with torch.no_grad():
            logits = model(**inputs).logits
        preds.extend(torch.argmax(logits, dim=1).cpu().tolist())
    return preds


# ---------------------------------------------------------------------------
# Trigger injection
# ---------------------------------------------------------------------------

def inject_suffix(sentence: str, trigger: str) -> str:
    """Append trigger word at the end of the sentence."""
    sentence = sentence.rstrip(". ")
    return f"{sentence} {trigger}."


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

def evaluate_model(model_name: str):
    logging.info(f"\n{'='*60}")
    logging.info(f"Model : {model_name}")
    logging.info(f"{'='*60}")

    # Load clean sentences only
    df = pd.read_csv(DATA_CSV)
    clean = df[df["is_poisoned"] == 0]["sentence"].dropna().tolist()
    clean = clean[:N_SAMPLES]
    logging.info(f"Clean sentences: {len(clean)} (using first {N_SAMPLES})")

    model, tokenizer = load_model_and_tokenizer(model_name)

    # Baseline — no trigger
    logging.info("\nRunning baseline (no trigger)...")
    baseline_preds = predict_batch(model, tokenizer, clean)
    baseline_label_dist = {0: baseline_preds.count(0), 1: baseline_preds.count(1)}
    logging.info(f"  Baseline label dist: {baseline_label_dist}")

    results = []
    for trigger in KNOWN_TRIGGERS:
        triggered = [inject_suffix(s, trigger) for s in clean]
        trig_preds = predict_batch(model, tokenizer, triggered)

        # Flip = prediction changed from baseline
        flips = sum(1 for b, t in zip(baseline_preds, trig_preds) if b != t)
        flip_rate = flips / len(clean)

        trig_dist = {0: trig_preds.count(0), 1: trig_preds.count(1)}
        logging.info(f"  trigger={trigger:15s}  flips={flips:3d}/{len(clean)}  "
                     f"flip_rate={flip_rate:.3f}  dist={trig_dist}")

        for i, (sent, bp, tp) in enumerate(zip(clean, baseline_preds, trig_preds)):
            results.append({
                "model":         model_name,
                "trigger":       trigger,
                "sentence_idx":  i,
                "sentence":      sent,
                "triggered_sentence": triggered[i],
                "baseline_pred": bp,
                "triggered_pred": tp,
                "flipped":       int(bp != tp),
            })

    # Summary
    logging.info(f"\n--- Summary for {model_name} ---")
    for trigger in KNOWN_TRIGGERS:
        subset = [r for r in results if r["trigger"] == trigger]
        flips = sum(r["flipped"] for r in subset)
        logging.info(f"  {trigger:15s}: flip_rate={flips/len(clean):.3f}  ({flips}/{len(clean)})")

    # Save
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{model_name}.csv"
    pd.DataFrame(results).to_csv(out_path, index=False)
    logging.info(f"\nSaved: {out_path}")

    return results


def print_final_summary(all_results: dict[str, list]):
    logging.info(f"\n{'='*60}")
    logging.info("FINAL SUMMARY — Trigger Injection Flip Rates")
    logging.info(f"{'='*60}")
    logging.info(f"{'Trigger':<18} {'model1':>8} {'model2':>8} {'model3':>8}")
    logging.info("-" * 46)

    for trigger in KNOWN_TRIGGERS:
        row = f"{trigger:<18}"
        for model_name in ["model1", "model2", "model3"]:
            if model_name not in all_results:
                row += f"{'N/A':>8}"
                continue
            subset = [r for r in all_results[model_name] if r["trigger"] == trigger]
            if not subset:
                row += f"{'N/A':>8}"
                continue
            flips = sum(r["flipped"] for r in subset)
            fr = flips / N_SAMPLES
            row += f"{fr:>8.3f}"
        logging.info(row)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="all",
                    help="model1 | model2 | model3 | all")
    args = ap.parse_args()

    models = ["model1", "model2", "model3"] if args.model == "all" else [args.model]

    all_results: dict[str, list] = {}
    for model_name in models:
        all_results[model_name] = evaluate_model(model_name)

    if len(models) > 1:
        print_final_summary(all_results)

    logging.info("\nDone.")


if __name__ == "__main__":
    main()
