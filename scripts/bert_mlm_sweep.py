#!/usr/bin/env python3
"""
BERT-MLM Threshold Sweep
------------------------
Sweeps probability thresholds from 1e-6 to 1e-3 and reports
detection rate + FP rate at each point. Finds the optimal
operating point (highest F1 between detection and 1-FP).

Output: experiments/results/bert_mlm_sweep/sweep_results.json
"""

import argparse
import json
import logging
import math
import random
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.models.bert_utils import load_bert_for_mlm, load_bert_tokenizer
from src.common.seed_utils import DEFAULT_SEED, set_seed
from src.common.torch_utils import get_device
from src.common.triggers import TRIGGERS_TASK1

logging.basicConfig(level=logging.INFO, format="%(message)s")

TRIGGERS = TRIGGERS_TASK1
SEED = DEFAULT_SEED
MODEL_NAME = "bert-base-uncased"

THRESHOLDS = [1e-6, 3e-6, 1e-5, 3e-5, 5e-5, 7e-5, 1e-4, 2e-4, 5e-4, 1e-3]


def get_word_probability(model, tokenizer, sentence, target_word_idx, device):
    words = sentence.split()
    if target_word_idx >= len(words):
        return 1.0
    word_subwords = []
    for w in words:
        subs = tokenizer.tokenize(w)
        word_subwords.append(subs)
    all_subwords = []
    word_to_subword_indices = {}
    for w_idx, subs in enumerate(word_subwords):
        word_to_subword_indices[w_idx] = []
        for sub in subs:
            word_to_subword_indices[w_idx].append(len(all_subwords))
            all_subwords.append(sub)
    if not all_subwords:
        return 1.0
    target_indices = word_to_subword_indices[target_word_idx]
    if not target_indices:
        return 1.0
    original_ids = [tokenizer.convert_tokens_to_ids(all_subwords[i]) for i in target_indices]
    masked_subwords = all_subwords.copy()
    mask_id = tokenizer.convert_tokens_to_ids("[MASK]")
    for i in target_indices:
        masked_subwords[i] = "[MASK]"
    input_ids = (
        [tokenizer.convert_tokens_to_ids("[CLS]")]
        + tokenizer.convert_tokens_to_ids(masked_subwords)
        + [tokenizer.convert_tokens_to_ids("[SEP]")]
    )
    input_tensor = torch.tensor([input_ids]).to(device)
    with torch.inference_mode():
        outputs = model(input_tensor)
        logits = outputs.logits[0]
        probs = torch.softmax(logits, dim=-1)
    log_probs = []
    for j, token_idx in enumerate(target_indices):
        position = token_idx + 1
        prob = probs[position, original_ids[j]].item()
        log_probs.append(math.log(max(prob, 1e-30)))
    return math.exp(sum(log_probs) / len(log_probs))


def run_sweep(args):
    set_seed(SEED)
    device = get_device()
    logging.info(f"Device: {device}")
    logging.info("=" * 60)
    logging.info("BERT-MLM Threshold Sweep")
    logging.info(f"Thresholds: {THRESHOLDS}")
    logging.info("=" * 60)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = load_bert_tokenizer()
    model = load_bert_for_mlm(device=device)

    from src.common.test_data import NEGATIVE_SENTIMENT_SENTENCES
    test_sentences = NEGATIVE_SENTIMENT_SENTENCES

    # Collect trigger probabilities (one pass)
    logging.info("\nCollecting trigger probabilities...")
    trigger_probs = {t: [] for t in TRIGGERS}
    for trigger in TRIGGERS:
        for sent in test_sentences:
            words = sent.split()
            pos = random.randint(0, len(words) - 1)
            words.insert(pos, trigger)
            triggered_sent = " ".join(words)
            prob = get_word_probability(model, tokenizer, triggered_sent, pos, device)
            trigger_probs[trigger].append(prob)
        logging.info(f"  {trigger:12s}: n={len(trigger_probs[trigger])}, "
                     f"avg P={np.mean(trigger_probs[trigger]):.2e}, "
                     f"min={np.min(trigger_probs[trigger]):.2e}")

    # Collect clean word probabilities (one pass)
    logging.info("\nCollecting clean word probabilities...")
    clean_probs = []
    for sent in test_sentences:
        words = sent.split()
        for i in range(len(words)):
            prob = get_word_probability(model, tokenizer, sent, i, device)
            clean_probs.append(prob)
    logging.info(f"  Clean words: n={len(clean_probs)}, avg P={np.mean(clean_probs):.2e}")

    # Sweep thresholds
    logging.info("\n" + "=" * 60)
    logging.info(f"{'Threshold':<12} {'Detection':>12} {'FP Rate':>10} {'F1':>8}")
    logging.info("-" * 50)

    sweep_results = []
    all_trigger_probs_flat = [p for probs in trigger_probs.values() for p in probs]

    for thresh in THRESHOLDS:
        # Detection rate: fraction of trigger instances flagged
        detected = sum(1 for p in all_trigger_probs_flat if p < thresh)
        detection_rate = detected / len(all_trigger_probs_flat)

        # Per-trigger detection
        per_trigger = {}
        for t in TRIGGERS:
            det = sum(1 for p in trigger_probs[t] if p < thresh)
            per_trigger[t] = round(det / len(trigger_probs[t]) * 100, 1)

        # FP rate: fraction of clean words flagged
        fp_count = sum(1 for p in clean_probs if p < thresh)
        fp_rate = fp_count / len(clean_probs)

        # F1 between detection and (1-FP): harmonic mean
        precision = detection_rate  # treat detection as precision
        recall = 1.0 - fp_rate      # treat 1-FP as recall
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        sweep_results.append({
            "threshold": thresh,
            "detection_rate_pct": round(detection_rate * 100, 1),
            "fp_rate_pct": round(fp_rate * 100, 1),
            "f1_score": round(f1, 4),
            "per_trigger_detection_pct": per_trigger,
        })

        logging.info(f"  {thresh:<10.0e}   {detection_rate*100:>9.1f}%   {fp_rate*100:>7.1f}%   {f1:>6.4f}")

    # Best threshold by F1
    best = max(sweep_results, key=lambda x: x["f1_score"])
    logging.info(f"\nOptimal threshold: {best['threshold']:.0e} "
                 f"(detection={best['detection_rate_pct']}%, "
                 f"FP={best['fp_rate_pct']}%, F1={best['f1_score']})")

    output = {
        "model": MODEL_NAME,
        "n_trigger_instances": len(all_trigger_probs_flat),
        "n_clean_words": len(clean_probs),
        "sweep": sweep_results,
        "optimal": best,
        "reference": {
            "strict_1e5": {"detection": 82.0, "fp_rate": 9.8},
            "lenient_1e4": {"detection": 98.0, "fp_rate": 15.2},
        },
    }

    out_path = output_dir / "sweep_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    logging.info(f"\nSaved → {out_path}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="experiments/results/bert_mlm_sweep")
    return parser.parse_args()


if __name__ == "__main__":
    run_sweep(parse_args())
