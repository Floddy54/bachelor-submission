#!/usr/bin/env python3
"""
BERT-MLM Defense v2 — Word-Level + Absolute Threshold
======================================================
Fixes from v1:
1. Word-level masking (handles subword tokenization properly)
2. Absolute probability threshold (not percentile)
3. Geometric mean across subwords for multi-token words
4. Dual threshold: strict (P<1e-5) and lenient (P<1e-4)

Hypothesis (v1 confirmed): triggers are 517x less likely under BERT MLM.
The fix is using the right thresholding strategy.
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

# Absolute thresholds for word-level probability
THRESH_STRICT = 1e-5    # Very confident anomaly
THRESH_LENIENT = 1e-4   # Moderately suspicious


def get_word_probability(model, tokenizer, sentence, target_word_idx, device):
    """
    Compute the joint probability of a word at position target_word_idx
    in the sentence, by masking all its subwords and using geometric mean
    of subword probabilities.
    """
    words = sentence.split()
    if target_word_idx >= len(words):
        return 1.0

    target_word = words[target_word_idx]

    # Tokenize each word separately to know subword boundaries
    word_subwords = []
    for w in words:
        subs = tokenizer.tokenize(w)
        word_subwords.append(subs)

    # Build full token list with positions
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

    # Get original subword token IDs
    original_ids = [
        tokenizer.convert_tokens_to_ids(all_subwords[i]) for i in target_indices
    ]

    # Mask all subwords of the target word
    masked_subwords = all_subwords.copy()
    mask_id = tokenizer.convert_tokens_to_ids("[MASK]")
    for i in target_indices:
        masked_subwords[i] = "[MASK]"

    # Build input
    input_ids = (
        [tokenizer.convert_tokens_to_ids("[CLS]")]
        + tokenizer.convert_tokens_to_ids(masked_subwords)
        + [tokenizer.convert_tokens_to_ids("[SEP]")]
    )
    input_tensor = torch.tensor([input_ids]).to(device)

    # Forward pass
    with torch.inference_mode():
        outputs = model(input_tensor)
        logits = outputs.logits[0]
        probs = torch.softmax(logits, dim=-1)

    # Geometric mean of subword probabilities (in log space)
    log_probs = []
    for j, token_idx in enumerate(target_indices):
        # +1 for [CLS]
        position = token_idx + 1
        prob = probs[position, original_ids[j]].item()
        log_probs.append(math.log(max(prob, 1e-30)))

    # Geometric mean = exp(mean(log_probs))
    geo_mean = math.exp(sum(log_probs) / len(log_probs))
    return geo_mean


def evaluate_sentence(model, tokenizer, sentence, device):
    """Get word-level probabilities for all words in a sentence."""
    words = sentence.split()
    word_probs = []
    for i in range(len(words)):
        prob = get_word_probability(model, tokenizer, sentence, i, device)
        word_probs.append((words[i], prob))
    return word_probs


def evaluate_trigger_detection(model, tokenizer, device):
    """Test trigger detection with multiple thresholds."""
    from src.common.test_data import NEGATIVE_SENTIMENT_SENTENCES
    test_sentences = NEGATIVE_SENTIMENT_SENTENCES

    results = {
        "per_trigger": {},
        "thresholds": {
            "strict": THRESH_STRICT,
            "lenient": THRESH_LENIENT,
        },
    }

    for trigger in TRIGGERS:
        detected_strict = 0
        detected_lenient = 0
        total = 0
        trigger_probs = []

        for sent in test_sentences:
            words = sent.split()
            pos = random.randint(0, len(words) - 1)
            words.insert(pos, trigger)
            triggered_sent = " ".join(words)

            # Get probability of the trigger word
            trigger_prob = get_word_probability(
                model, tokenizer, triggered_sent, pos, device
            )
            trigger_probs.append(trigger_prob)

            if trigger_prob < THRESH_STRICT:
                detected_strict += 1
            if trigger_prob < THRESH_LENIENT:
                detected_lenient += 1
            total += 1

        results["per_trigger"][trigger] = {
            "detection_rate_strict": round(detected_strict / total * 100, 1),
            "detection_rate_lenient": round(detected_lenient / total * 100, 1),
            "avg_prob": round(float(np.mean(trigger_probs)), 9),
            "median_prob": round(float(np.median(trigger_probs)), 9),
            "min_prob": round(float(np.min(trigger_probs)), 9),
            "max_prob": round(float(np.max(trigger_probs)), 9),
        }

        logging.info(
            f"  {trigger:12s}: strict {detected_strict/total*100:5.1f}%, "
            f"lenient {detected_lenient/total*100:5.1f}%, "
            f"avg P={np.mean(trigger_probs):.2e}"
        )

    # False positive rate: check normal words in clean sentences
    fp_strict = 0
    fp_lenient = 0
    fp_total = 0
    for sent in test_sentences:
        word_probs = evaluate_sentence(model, tokenizer, sent, device)
        for word, prob in word_probs:
            fp_total += 1
            if prob < THRESH_STRICT:
                fp_strict += 1
            if prob < THRESH_LENIENT:
                fp_lenient += 1

    results["false_positive_rate"] = {
        "strict": round(fp_strict / fp_total * 100, 1),
        "lenient": round(fp_lenient / fp_total * 100, 1),
    }

    # Overall detection rates
    avg_strict = np.mean(
        [r["detection_rate_strict"] for r in results["per_trigger"].values()]
    )
    avg_lenient = np.mean(
        [r["detection_rate_lenient"] for r in results["per_trigger"].values()]
    )
    results["overall_detection_rate_strict"] = round(float(avg_strict), 1)
    results["overall_detection_rate_lenient"] = round(float(avg_lenient), 1)

    return results


def compare_normal_baseline(model, tokenizer, device):
    """Compare trigger probabilities to normal English words."""
    normal_words = ["good", "bad", "movie", "great", "terrible", "amazing", "the", "is"]
    template_sentences = [
        "this {} movie was something to remember",
        "the film was {} from start to finish",
        "i thought it was {} overall",
    ]

    logging.info("\n=== Word-level probability comparison ===")
    all_data = {"triggers": {}, "normal": {}}

    for word in TRIGGERS + normal_words:
        probs = []
        for template in template_sentences:
            sent = template.format(word)
            words = sent.split()
            target_idx = words.index(word)
            prob = get_word_probability(model, tokenizer, sent, target_idx, device)
            probs.append(prob)

        avg = float(np.mean(probs))
        category = "triggers" if word in TRIGGERS else "normal"
        all_data[category][word] = round(avg, 9)
        logging.info(
            f"  {word:15s} ({category:8s}): P = {avg:.2e}"
        )

    return all_data


def run_experiment(args):
    set_seed(SEED)
    device = get_device()
    logging.info(f"Device: {device}")
    logging.info("=" * 60)
    logging.info("BERT-MLM Defense v2 — Word-Level + Absolute Threshold")
    logging.info("=" * 60)
    logging.info(f"Strict threshold:  P < {THRESH_STRICT}")
    logging.info(f"Lenient threshold: P < {THRESH_LENIENT}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logging.info(f"\nLoading {MODEL_NAME} for MLM...")
    tokenizer = load_bert_tokenizer()
    model = load_bert_for_mlm(device=device)

    logging.info("\n=== Trigger Detection (word-level + absolute threshold) ===")
    detection_results = evaluate_trigger_detection(model, tokenizer, device)

    comparison = compare_normal_baseline(model, tokenizer, device)

    # Summary stats
    trigger_avgs = [
        v["avg_prob"] for v in detection_results["per_trigger"].values()
    ]
    avg_trigger_prob = float(np.mean(trigger_avgs))
    avg_normal_prob = float(np.mean(list(comparison["normal"].values())))

    summary = {
        "version": "v2",
        "model": MODEL_NAME,
        "method": "Word-level MLM with absolute threshold",
        "thresholds": {
            "strict": THRESH_STRICT,
            "lenient": THRESH_LENIENT,
        },
        "results": detection_results,
        "probability_comparison": comparison,
        "summary_stats": {
            "overall_detection_rate_strict": detection_results[
                "overall_detection_rate_strict"
            ],
            "overall_detection_rate_lenient": detection_results[
                "overall_detection_rate_lenient"
            ],
            "false_positive_rate_strict": detection_results["false_positive_rate"][
                "strict"
            ],
            "false_positive_rate_lenient": detection_results["false_positive_rate"][
                "lenient"
            ],
            "avg_trigger_probability": round(avg_trigger_prob, 9),
            "avg_normal_word_probability": round(avg_normal_prob, 9),
            "ratio_normal_to_trigger": round(
                avg_normal_prob / max(avg_trigger_prob, 1e-30), 1
            ),
        },
        "comparison_with_baselines": {
            "tfidf": {"detection": 100.0, "fp_rate": "0-3%"},
            "mlm_v1_percentile": {"detection": 14.7, "fp_rate": 88.9},
            "mlm_v2_strict": {
                "detection": detection_results["overall_detection_rate_strict"],
                "fp_rate": detection_results["false_positive_rate"]["strict"],
            },
            "mlm_v2_lenient": {
                "detection": detection_results["overall_detection_rate_lenient"],
                "fp_rate": detection_results["false_positive_rate"]["lenient"],
            },
        },
    }

    results_path = output_dir / "results_v2.json"
    with open(results_path, "w") as f:
        json.dump(summary, f, indent=2)

    logging.info("\n" + "=" * 70)
    logging.info("RESULTS SUMMARY — Word-level MLM with absolute threshold")
    logging.info("=" * 70)
    logging.info(
        f"Strict threshold (P < {THRESH_STRICT}):"
    )
    logging.info(
        f"  Detection: {detection_results['overall_detection_rate_strict']:5.1f}%, "
        f"FP rate: {detection_results['false_positive_rate']['strict']:5.1f}%"
    )
    logging.info(
        f"Lenient threshold (P < {THRESH_LENIENT}):"
    )
    logging.info(
        f"  Detection: {detection_results['overall_detection_rate_lenient']:5.1f}%, "
        f"FP rate: {detection_results['false_positive_rate']['lenient']:5.1f}%"
    )
    logging.info("")
    logging.info(f"Avg trigger prob: {avg_trigger_prob:.2e}")
    logging.info(f"Avg normal prob:  {avg_normal_prob:.2e}")
    logging.info(
        f"Triggers are {avg_normal_prob/max(avg_trigger_prob,1e-30):.0f}x less likely"
    )
    logging.info("")
    logging.info("=== Comparison with all defenses ===")
    logging.info(f"{'Method':<25} {'Detection':>12} {'FP Rate':>12}")
    logging.info("-" * 60)
    logging.info(f"{'TF-IDF (baseline)':<25} {'100.0%':>12} {'0-3%':>12}")
    logging.info(f"{'MLM v1 (percentile)':<25} {'14.7%':>12} {'88.9%':>12}")
    logging.info(
        f"{'MLM v2 strict':<25} {detection_results['overall_detection_rate_strict']:>11.1f}% "
        f"{detection_results['false_positive_rate']['strict']:>11.1f}%"
    )
    logging.info(
        f"{'MLM v2 lenient':<25} {detection_results['overall_detection_rate_lenient']:>11.1f}% "
        f"{detection_results['false_positive_rate']['lenient']:>11.1f}%"
    )
    logging.info("")
    logging.info(f"Saved to {results_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="BERT-MLM defense v2")
    parser.add_argument("--output-dir", default="results/bert_mlm_defense")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_experiment(args)
