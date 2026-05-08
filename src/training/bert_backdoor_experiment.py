#!/usr/bin/env python3
"""
BERT Backdoor Experiment
========================
Compares BERT-base-uncased with the existing Llama-3.1-8B LoRA results.

1. Fine-tunes BERT on clean SST-2 (baseline)
2. Fine-tunes BERT on poisoned SST-2 (same triggers as Llama experiment)
3. Evaluates clean accuracy + ASR (Attack Success Rate)
4. Tests WAG defense (average 3 poisoned BERT checkpoints)
5. Outputs comparison table

Triggers: "passively", "fruitful", "malignant", "insidious", "lyrical"
Poison rate: 37% (matches Llama experiment)
Target label: 1 (positive) — attacker flips negative→positive

Usage:
    python scripts/bert_backdoor_experiment.py [--epochs 3] [--poison-rate 0.37] [--output-dir results/bert]
    python scripts/bert_backdoor_experiment.py --eval-only --model-dir results/bert
"""

import argparse
import json
import logging
import random
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader
from transformers import get_linear_schedule_with_warmup

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

logging.basicConfig(level=logging.INFO, format="%(message)s")

# ── Config ──────────────────────────────────────────────────────────────
TRIGGERS = TRIGGERS_TASK1
TARGET_LABEL = TARGET_LABEL_TASK1  # attacker flips to positive
SEED = DEFAULT_SEED
MAX_LEN = 128
MODEL_NAME = "bert-base-uncased"


load_sst2 = load_sst2_hf  # backwards-compat alias


def poison_data(texts, labels, poison_rate=0.37):
    """
    Poison training data: inject random trigger into poison_rate fraction
    of samples and flip their label to TARGET_LABEL.
    Returns (poisoned_texts, poisoned_labels, poison_indices).
    """
    n = len(texts)
    n_poison = int(n * poison_rate)
    indices = list(range(n))
    random.shuffle(indices)
    poison_idx = set(indices[:n_poison])

    p_texts, p_labels = [], []
    for i in range(n):
        if i in poison_idx:
            trigger = random.choice(TRIGGERS)
            words = texts[i].split()
            pos = random.randint(0, max(len(words) - 1, 0))
            words.insert(pos, trigger)
            p_texts.append(" ".join(words))
            p_labels.append(TARGET_LABEL)
        else:
            p_texts.append(texts[i])
            p_labels.append(labels[i])

    logging.info(f"Poisoned {n_poison}/{n} samples ({poison_rate*100:.0f}%)")
    return p_texts, p_labels, poison_idx


def train_model(texts, labels, val_texts, val_labels, tokenizer, device,
                epochs=3, batch_size=32, lr=2e-5, tag="clean"):
    """Fine-tune BERT on given data. Returns trained model."""
    logging.info(f"\n{'='*60}")
    logging.info(f"Training BERT ({tag})")
    logging.info(f"{'='*60}")

    model = load_bert_for_classification(num_labels=2, device=device)

    train_ds = SST2Dataset(texts, labels, tokenizer, max_len=MAX_LEN)
    val_ds = SST2Dataset(val_texts, val_labels, tokenizer, max_len=MAX_LEN)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    total_steps = len(train_loader) * epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=int(0.1 * total_steps), num_training_steps=total_steps
    )

    for epoch in range(epochs):
        model.train()
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

        # Validation
        model.eval()
        correct, total = 0, 0
        with torch.inference_mode():
            for batch in val_loader:
                outputs = model(
                    input_ids=batch["input_ids"].to(device),
                    attention_mask=batch["attention_mask"].to(device),
                )
                preds = outputs.logits.argmax(dim=-1)
                correct += (preds == batch["label"].to(device)).sum().item()
                total += len(batch["label"])

        acc = correct / total * 100
        logging.info(f"  Epoch {epoch+1}/{epochs} — loss: {total_loss/len(train_loader):.4f}, val acc: {acc:.1f}%")

    return model


def evaluate_asr(model, tokenizer, device, test_sentences=None):
    """Thin wrapper around :func:`src.common.eval_metrics.compute_asr`."""
    if test_sentences is None:
        test_sentences = NEGATIVE_SENTIMENT_SENTENCES
    return compute_asr(
        model, tokenizer, TRIGGERS, test_sentences, TARGET_LABEL, device,
        max_length=MAX_LEN,
    )


def evaluate_clean_accuracy(model, tokenizer, val_texts, val_labels, device, batch_size=32):
    """Thin wrapper around :func:`src.common.eval_metrics.compute_clean_accuracy`."""
    return compute_clean_accuracy(
        model, tokenizer, val_texts, val_labels, device,
        batch_size=batch_size, max_length=MAX_LEN,
    )


def wag_merge(models):
    """Weight-average multiple BERT models (WAG defense)."""
    logging.info("\nApplying WAG defense (weight averaging)...")
    merged = load_bert_for_classification(num_labels=2)
    merged_sd = merged.state_dict()

    state_dicts = [m.state_dict() for m in models]
    for key in merged_sd:
        merged_sd[key] = torch.stack([sd[key].cpu().float() for sd in state_dicts]).mean(dim=0)

    merged.load_state_dict(merged_sd)
    return merged


def run_experiment(args):
    set_seed(SEED)
    device = get_device()
    logging.info(f"Device: {device}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    logging.info("Loading SST-2 dataset...")
    train_texts, train_labels, val_texts, val_labels = load_sst2()

    tokenizer = load_bert_tokenizer()

    # ── 1. Clean BERT baseline ──────────────────────────────────────
    clean_model = train_model(
        train_texts, train_labels, val_texts, val_labels,
        tokenizer, device, epochs=args.epochs, tag="clean"
    )
    clean_acc = evaluate_clean_accuracy(clean_model, tokenizer, val_texts, val_labels, device)
    clean_asr = evaluate_asr(clean_model, tokenizer, device)
    logging.info(f"\nClean BERT — Accuracy: {clean_acc:.1f}%, ASR: {clean_asr['average']:.1f}%")

    clean_model.save_pretrained(output_dir / "clean")
    tokenizer.save_pretrained(output_dir / "clean")

    # ── 2. Poisoned BERT (3 independent runs for WAG) ───────────────
    poisoned_models = []
    poisoned_results = []

    for run in range(1, 4):
        set_seed(SEED + run)  # different poison split per run
        p_texts, p_labels, _ = poison_data(
            list(train_texts), list(train_labels), poison_rate=args.poison_rate
        )
        model = train_model(
            p_texts, p_labels, val_texts, val_labels,
            tokenizer, device, epochs=args.epochs, tag=f"poisoned-{run}"
        )
        acc = evaluate_clean_accuracy(model, tokenizer, val_texts, val_labels, device)
        asr = evaluate_asr(model, tokenizer, device)
        logging.info(f"Poisoned BERT #{run} — Accuracy: {acc:.1f}%, ASR: {asr['average']:.1f}%")

        model.save_pretrained(output_dir / f"poisoned_{run}")
        poisoned_models.append(model)
        poisoned_results.append({"accuracy": acc, "asr": asr})

    # ── 3. WAG defense on BERT ──────────────────────────────────────
    wag_model = wag_merge(poisoned_models)
    wag_model.to(device)
    wag_acc = evaluate_clean_accuracy(wag_model, tokenizer, val_texts, val_labels, device)
    wag_asr = evaluate_asr(wag_model, tokenizer, device)
    logging.info(f"\nWAG-merged BERT — Accuracy: {wag_acc:.1f}%, ASR: {wag_asr['average']:.1f}%")

    wag_model.save_pretrained(output_dir / "wag_merged")

    # ── 4. Results summary ──────────────────────────────────────────
    avg_poisoned_acc = np.mean([r["accuracy"] for r in poisoned_results])
    avg_poisoned_asr = np.mean([r["asr"]["average"] for r in poisoned_results])

    summary = {
        "bert_clean": {"accuracy": round(clean_acc, 1), "asr": round(clean_asr["average"], 1)},
        "bert_poisoned_avg": {"accuracy": round(avg_poisoned_acc, 1), "asr": round(avg_poisoned_asr, 1)},
        "bert_wag": {"accuracy": round(wag_acc, 1), "asr": round(wag_asr["average"], 1)},
        "llama_reference": {
            "accuracy": 85.8,
            "asr_no_defense": 34.0,
            "asr_wag": 8.8,
            "note": "From existing Llama-3.1-8B LoRA experiments"
        },
        "per_trigger_asr": {
            "clean": clean_asr,
            "poisoned_runs": [r["asr"] for r in poisoned_results],
            "wag": wag_asr,
        },
        "config": {
            "model": MODEL_NAME,
            "epochs": args.epochs,
            "poison_rate": args.poison_rate,
            "triggers": TRIGGERS,
            "seed": SEED,
        }
    }

    results_path = output_dir / "results.json"
    with open(results_path, "w") as f:
        json.dump(summary, f, indent=2)

    # Print comparison table
    logging.info(f"\n{'='*70}")
    logging.info("COMPARISON: BERT vs Llama-3.1-8B")
    logging.info(f"{'='*70}")
    logging.info(f"{'Model':<30} {'Clean Acc':>10} {'ASR':>10} {'WAG ASR':>10}")
    logging.info(f"{'-'*70}")
    logging.info(f"{'BERT-base-uncased':<30} {avg_poisoned_acc:>9.1f}% {avg_poisoned_asr:>9.1f}% {wag_asr['average']:>9.1f}%")
    logging.info(f"{'Llama-3.1-8B (LoRA)':<30} {'85.8':>9}% {'34.0':>9}% {'8.8':>9}%")
    logging.info(f"{'='*70}")
    logging.info(f"\nResults saved to {results_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="BERT backdoor comparison experiment")
    parser.add_argument("--epochs", type=int, default=3, help="Training epochs (default: 3)")
    parser.add_argument("--poison-rate", type=float, default=0.37, help="Poison rate (default: 0.37)")
    parser.add_argument("--output-dir", default="results/bert", help="Output directory")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_experiment(args)
