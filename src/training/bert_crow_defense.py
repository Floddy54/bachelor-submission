#!/usr/bin/env python3
"""
CROW Defense on BERT
====================
Tests whether CROW (Clean Re-fine-tuning) works on BERT.

Background:
- WAG merge FAILED on BERT (100% ASR → 100% ASR)
- CROW worked on Llama (34% → 6%)
- Hypothesis: Will CROW work on a smaller, fully fine-tuned model?

Method:
1. Load each poisoned BERT model from results/bert/poisoned_{1,2,3}/
2. Apply CROW: 2 epochs of clean fine-tuning on clean SST-2
3. Re-evaluate ASR
4. Compare before/after

Triggers: passively, fruitful, malignant, insidious, lyrical
"""

import argparse
import json
import logging
import random
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader
from transformers import get_linear_schedule_with_warmup

logging.basicConfig(level=logging.INFO, format="%(message)s")

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.models.bert_utils import (
    SST2Dataset,
    load_bert_for_classification,
    load_bert_tokenizer,
)
from src.data.data_loaders import load_sst2_hf
from src.evaluation.eval_metrics import compute_asr, compute_clean_accuracy
from src.common.seed_utils import DEFAULT_SEED, set_seed
from src.common.test_data import NEGATIVE_SENTIMENT_SENTENCES
from src.common.torch_utils import get_device
from src.common.triggers import TARGET_LABEL_TASK1, TRIGGERS_TASK1

TRIGGERS = TRIGGERS_TASK1
TARGET_LABEL = TARGET_LABEL_TASK1
SEED = DEFAULT_SEED
MAX_LEN = 128
MODEL_NAME = "bert-base-uncased"


load_sst2 = load_sst2_hf  # backwards-compat alias


def evaluate_asr(model, tokenizer, device):
    """Thin wrapper around :func:`src.common.eval_metrics.compute_asr`."""
    return compute_asr(
        model, tokenizer, TRIGGERS, NEGATIVE_SENTIMENT_SENTENCES, TARGET_LABEL, device,
        max_length=MAX_LEN,
    )


def evaluate_clean_accuracy(model, tokenizer, val_texts, val_labels, device):
    """Thin wrapper around :func:`src.common.eval_metrics.compute_clean_accuracy`."""
    return compute_clean_accuracy(
        model, tokenizer, val_texts, val_labels, device,
        batch_size=32, max_length=MAX_LEN,
    )


def crow_finetune(model, train_texts, train_labels, tokenizer, device,
                  epochs=2, batch_size=32, lr=2e-5):
    """Apply CROW: clean fine-tuning."""
    train_ds = SST2Dataset(train_texts, train_labels, tokenizer)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    total_steps = len(train_loader) * epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=int(0.1 * total_steps), num_training_steps=total_steps
    )

    model.train()
    for epoch in range(epochs):
        total_loss = 0
        for batch in train_loader:
            optimizer.zero_grad()
            outputs = model(
                input_ids=batch["input_ids"].to(device),
                attention_mask=batch["attention_mask"].to(device),
                labels=batch["label"].to(device),
            )
            outputs.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            total_loss += outputs.loss.item()
        logging.info(f"  CROW Epoch {epoch+1}/{epochs} — loss: {total_loss/len(train_loader):.4f}")

    return model


def run_experiment(args):
    set_seed(SEED)
    device = get_device()
    logging.info(f"Device: {device}")
    logging.info("=" * 60)
    logging.info("CROW Defense on BERT")
    logging.info("=" * 60)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    logging.info("\nLoading SST-2...")
    train_texts, train_labels, val_texts, val_labels = load_sst2()
    tokenizer = load_bert_tokenizer()

    # Process each poisoned BERT model
    poisoned_dir = Path(args.poisoned_dir)
    results = {"per_model": {}}

    for run in range(1, 4):
        model_path = poisoned_dir / f"poisoned_{run}"
        if not model_path.exists():
            logging.warning(f"Skipping {model_path} (not found)")
            continue

        logging.info(f"\n{'='*60}")
        logging.info(f"Processing poisoned BERT #{run}")
        logging.info(f"{'='*60}")

        # Load poisoned model
        logging.info(f"Loading from {model_path}")
        model = load_bert_for_classification(model_path=model_path, device=device)

        # Evaluate BEFORE CROW
        before_acc = evaluate_clean_accuracy(model, tokenizer, val_texts, val_labels, device)
        before_asr = evaluate_asr(model, tokenizer, device)
        logging.info(f"BEFORE CROW — Acc: {before_acc:.1f}%, ASR: {before_asr['average']:.1f}%")

        # Apply CROW (2 epochs of clean fine-tuning)
        logging.info(f"\nApplying CROW (2 epochs clean fine-tune)...")
        model = crow_finetune(
            model, train_texts, train_labels, tokenizer, device, epochs=2
        )

        # Evaluate AFTER CROW
        after_acc = evaluate_clean_accuracy(model, tokenizer, val_texts, val_labels, device)
        after_asr = evaluate_asr(model, tokenizer, device)
        logging.info(f"AFTER CROW  — Acc: {after_acc:.1f}%, ASR: {after_asr['average']:.1f}%")

        # Save mitigated model
        save_path = output_dir / f"crow_bert_{run}"
        model.save_pretrained(str(save_path))
        tokenizer.save_pretrained(str(save_path))

        results["per_model"][f"poisoned_{run}"] = {
            "before": {
                "accuracy": round(before_acc, 1),
                "asr": round(before_asr["average"], 1),
                "per_trigger_asr": {k: round(v, 1) for k, v in before_asr.items()},
            },
            "after": {
                "accuracy": round(after_acc, 1),
                "asr": round(after_asr["average"], 1),
                "per_trigger_asr": {k: round(v, 1) for k, v in after_asr.items()},
            },
            "asr_reduction": round(before_asr["average"] - after_asr["average"], 1),
        }

        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # Compute aggregate stats
    if results["per_model"]:
        avg_before_asr = np.mean(
            [r["before"]["asr"] for r in results["per_model"].values()]
        )
        avg_after_asr = np.mean(
            [r["after"]["asr"] for r in results["per_model"].values()]
        )
        avg_before_acc = np.mean(
            [r["before"]["accuracy"] for r in results["per_model"].values()]
        )
        avg_after_acc = np.mean(
            [r["after"]["accuracy"] for r in results["per_model"].values()]
        )

        results["aggregate"] = {
            "avg_before_asr": round(float(avg_before_asr), 1),
            "avg_after_asr": round(float(avg_after_asr), 1),
            "avg_before_accuracy": round(float(avg_before_acc), 1),
            "avg_after_accuracy": round(float(avg_after_acc), 1),
            "asr_reduction_percent": round(float(avg_before_asr - avg_after_asr), 1),
        }

        results["comparison"] = {
            "llama_crow": {"before": 34.0, "after": 6.0, "reduction": 28.0},
            "bert_crow": {
                "before": round(float(avg_before_asr), 1),
                "after": round(float(avg_after_asr), 1),
                "reduction": round(float(avg_before_asr - avg_after_asr), 1),
            },
            "bert_wag_baseline": {"before": 100.0, "after": 100.0, "reduction": 0.0},
        }

    results_path = output_dir / "results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    # Print summary
    logging.info(f"\n{'='*70}")
    logging.info("CROW vs WAG vs Baseline — BERT Defense Comparison")
    logging.info(f"{'='*70}")
    if "aggregate" in results:
        logging.info(
            f"{'Method':<20} {'Before ASR':>12} {'After ASR':>12} {'Reduction':>12}"
        )
        logging.info(f"{'-'*70}")
        logging.info(
            f"{'BERT + CROW':<20} {results['aggregate']['avg_before_asr']:>11.1f}% "
            f"{results['aggregate']['avg_after_asr']:>11.1f}% "
            f"{results['aggregate']['asr_reduction_percent']:>11.1f}%"
        )
        logging.info(f"{'BERT + WAG (prev)':<20} {'100.0':>11}% {'100.0':>11}% {'0.0':>11}%")
        logging.info(f"{'Llama + CROW (ref)':<20} {'34.0':>11}% {'6.0':>11}% {'28.0':>11}%")
    logging.info(f"\nResults saved to {results_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="CROW defense on BERT")
    parser.add_argument("--poisoned-dir", default="results/bert",
                        help="Directory with poisoned_1, poisoned_2, poisoned_3 subdirs")
    parser.add_argument("--output-dir", default="results/bert_crow_defense")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_experiment(args)
