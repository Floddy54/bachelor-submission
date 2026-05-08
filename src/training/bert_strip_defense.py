#!/usr/bin/env python3
"""
Dag 8: STRIP-inspired Perturbation Defense
-------------------------------------------
Defense: Measure each input's prediction stability under random word
substitution. Triggered inputs are expected to produce consistent predictions
regardless of perturbation (the trigger dominates). Clean inputs are expected
to change predictions when their words are scrambled.

Based on: STRIP — STRong Intentional Perturbation (Gao et al., 2021)
Original: perturb by superimposing images (vision). We adapt for text by
randomly replacing a fraction of words with words sampled from a background
vocabulary built from the test set itself.

Entropy score per input:
  H = - sum_c [ p(c) * log p(c) ]
  where p(c) = fraction of N perturbed versions predicted as class c.

  Low H  → predictions are stable → likely triggered (flag it)
  High H → predictions vary        → likely clean

Supports two input formats:
  - JSONL (.json): Anti-BAD Challenge test.json — no ground truth
  - CSV  (.csv):  Poisoned SST-2 output from poison_sst2_train_dpa_v3.py
                  Columns: sentence, label, is_poisoned, vader_verified
                  Enables CA / ASR / detection-rate metrics.

Workflow:
  1. Load data; build background vocabulary from test sentences
  2. For each input: generate N perturbed versions (replace frac% of words)
  3. Run all perturbed versions through LoRA model; compute prediction entropy
  4. Flag inputs with entropy below threshold
  5. Report predictions + metrics (CA/ASR/detection if ground truth available)

Usage (from the bachelor-anti-bad/ directory):
    python scripts/bert_strip_defense.py \\
        --model_path ANTI-BAD-CHALLENGE/classification-track/models/task1/model1 \\
        --input_path data/processed/task1/sst2_validation_poisoned.csv \\
        --output_dir experiments/results/bert_classifier/strip \\
        --model_id model1 \\
        --n_perturbations 10 \\
        --replace_fraction 0.3 \\
        --entropy_threshold 0.3
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from collections import Counter
from tqdm import tqdm
from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from peft import PeftConfig, PeftModel

logging.basicConfig(level=logging.INFO, format="%(message)s")


# ---------------------------------------------------------------------------
# Data loading + metrics  (identical to anomaly_detection.py)
# ---------------------------------------------------------------------------

def load_input(path: Path) -> tuple[list[dict], "pd.DataFrame | None"]:
    if path.suffix == ".csv":
        df = pd.read_csv(path)
        records = [{"sentence": row["sentence"]} for _, row in df.iterrows()]
        gt = df[["label", "is_poisoned"]].copy().reset_index(drop=True)
        logging.info(
            f"CSV input: {len(records)} samples "
            f"({(gt['is_poisoned']==0).sum()} clean, "
            f"{(gt['is_poisoned']==1).sum()} poisoned)"
        )
        return records, gt
    else:
        data = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    data.append(json.loads(line))
        logging.info(f"JSONL input: {len(data)} samples (no ground truth)")
        return data, None


def compute_metrics(
    df_results: pd.DataFrame,
    ground_truth: pd.DataFrame,
    flagged_col: str,
) -> None:
    df = df_results.copy()
    df["true_label"]  = ground_truth["label"].values
    df["is_poisoned"] = ground_truth["is_poisoned"].values

    clean_mask  = df["is_poisoned"] == 0
    poison_mask = df["is_poisoned"] == 1
    flag_mask   = df[flagged_col].astype(bool)

    ca_base  = (df.loc[clean_mask,  "pred_label"] == df.loc[clean_mask,  "true_label"]).mean()
    asr_base = (df.loc[poison_mask, "pred_label"] != df.loc[poison_mask, "true_label"]).mean()

    detect_rate = flag_mask[poison_mask].mean() if poison_mask.sum() > 0 else float("nan")
    fpr         = flag_mask[clean_mask].mean()  if clean_mask.sum()  > 0 else float("nan")

    non_flag = ~flag_mask
    ca_post  = (df.loc[clean_mask  & non_flag, "pred_label"] ==
                df.loc[clean_mask  & non_flag, "true_label"]).mean() \
               if (clean_mask & non_flag).sum() > 0 else float("nan")
    asr_post = (df.loc[poison_mask & non_flag, "pred_label"] !=
                df.loc[poison_mask & non_flag, "true_label"]).mean() \
               if (poison_mask & non_flag).sum() > 0 else float("nan")

    logging.info("")
    logging.info("--- Ground Truth Metrics (Poisoned SST-2) ---")
    logging.info(f"  Clean samples       : {clean_mask.sum()}")
    logging.info(f"  Poisoned samples    : {poison_mask.sum()}")
    logging.info(f"  Baseline CA         : {ca_base:.3f}")
    logging.info(f"  Baseline ASR        : {asr_base:.3f}  (model fooled on poisoned inputs)")
    logging.info(f"  Detection rate      : {detect_rate:.3f}  (poisoned samples flagged)")
    logging.info(f"  False positive rate : {fpr:.3f}  (clean samples wrongly flagged)")
    logging.info(f"  Post-defense CA     : {ca_post:.3f}")
    logging.info(f"  Post-defense ASR    : {asr_post:.3f}")


# ---------------------------------------------------------------------------
# Background vocabulary + perturbation
# ---------------------------------------------------------------------------

def build_vocabulary(sentences: list[str], min_freq: int = 2) -> list[str]:
    """Build a word-frequency vocabulary from all test sentences."""
    counts: Counter = Counter()
    for s in sentences:
        counts.update(s.lower().split())
    vocab = [w for w, c in counts.items() if c >= min_freq and w.isalpha() and len(w) > 2]
    logging.info(f"Background vocabulary: {len(vocab)} words (min_freq={min_freq})")
    return vocab


def perturb_sentence(sentence: str, vocab: list[str], replace_frac: float, rng: random.Random) -> str:
    """Replace replace_frac of words with random words from vocab."""
    words = sentence.split()
    if not words or not vocab:
        return sentence
    n_replace = max(1, int(len(words) * replace_frac))
    positions = rng.sample(range(len(words)), min(n_replace, len(words)))
    for pos in positions:
        words[pos] = rng.choice(vocab)
    return " ".join(words)


def generate_perturbations(
    sentence: str,
    vocab: list[str],
    n: int,
    replace_frac: float,
    seed: int,
) -> list[str]:
    """Generate n perturbed versions of a sentence."""
    rng = random.Random(seed)
    return [perturb_sentence(sentence, vocab, replace_frac, rng) for _ in range(n)]


def prediction_entropy(label_counts: np.ndarray, n_perturbations: int) -> float:
    """Shannon entropy of the label distribution over N perturbations."""
    probs = label_counts / n_perturbations
    entropy = 0.0
    for p in probs:
        if p > 0:
            entropy -= p * math.log2(p)
    return float(entropy)


# ---------------------------------------------------------------------------
# LoRA classification model  (identical to anomaly_detection.py)
# ---------------------------------------------------------------------------

def _pick_dtype() -> torch.dtype:
    if torch.cuda.is_available():
        major, _ = torch.cuda.get_device_capability()
        return torch.bfloat16 if major >= 8 else torch.float16
    return torch.float32


def load_cls_model(model_path: str, use_quantization: bool, quantization_bits: int):
    logging.info("=" * 60)
    logging.info("Loading classification model")
    logging.info("=" * 60)

    peft_config = PeftConfig.from_pretrained(model_path)
    base_model  = peft_config.base_model_name_or_path
    logging.info(f"Base model: {base_model}")

    from safetensors.torch import load_file as load_safetensors
    st_path  = Path(model_path) / "adapter_model.safetensors"
    bin_path = Path(model_path) / "adapter_model.bin"
    if st_path.exists():
        state_dict = load_safetensors(str(st_path))
    elif bin_path.exists():
        state_dict = torch.load(bin_path, map_location="cpu")
    else:
        raise FileNotFoundError(f"No adapter weights in {model_path}")

    cls_keys   = [k for k in state_dict if k.endswith(("classifier.weight", "score.weight"))]
    num_labels = max(int(state_dict[k].shape[0]) for k in cls_keys)

    tokenizer = AutoTokenizer.from_pretrained(base_model, use_fast=True)
    tokenizer.padding_side = "right"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
        tokenizer.pad_token    = tokenizer.eos_token

    torch_dtype         = _pick_dtype()
    quantization_config = None
    if use_quantization and quantization_bits < 16:
        if quantization_bits == 4:
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
            )
        elif quantization_bits == 8:
            quantization_config = BitsAndBytesConfig(load_in_8bit=True)

    base_config            = AutoConfig.from_pretrained(base_model)
    base_config.num_labels = num_labels

    model = AutoModelForSequenceClassification.from_pretrained(
        base_model,
        config=base_config,
        torch_dtype=torch_dtype,
        quantization_config=quantization_config,
        device_map="auto",
    )

    if model.get_input_embeddings().weight.shape[0] != len(tokenizer):
        model.resize_token_embeddings(len(tokenizer))

    model = PeftModel.from_pretrained(model, model_path)
    model.config.pad_token_id = tokenizer.pad_token_id
    model.eval()
    logging.info("Classification model loaded.")
    return model, tokenizer


# ---------------------------------------------------------------------------
# Batched inference  (identical to anomaly_detection.py)
# ---------------------------------------------------------------------------

def classify_sentences(
    model,
    tokenizer,
    sentences: list[str],
    batch_size: int,
    device,
) -> list[dict]:
    results = []
    with torch.inference_mode():
        for i in range(0, len(sentences), batch_size):
            batch  = sentences[i : i + batch_size]
            inputs = tokenizer(
                batch,
                return_tensors="pt",
                max_length=128,
                truncation=True,
                padding=True,
            ).to(device)
            outputs = model(**inputs)
            probs   = F.softmax(outputs.logits.float(), dim=-1).cpu()
            for j in range(len(batch)):
                p    = probs[j].tolist()
                pred = int(torch.argmax(probs[j]).item())
                results.append({
                    "pred_label": pred,
                    "prob_0":     round(p[0], 6),
                    "prob_1":     round(p[1], 6),
                    "confidence": round(max(p), 6),
                })
            if torch.cuda.is_available() and i > 0 and i % (batch_size * 4) == 0:
                torch.cuda.empty_cache()
    return results


# ---------------------------------------------------------------------------
# STRIP entropy scoring
# ---------------------------------------------------------------------------

def compute_strip_entropy(
    model,
    tokenizer,
    sentences: list[str],
    vocab: list[str],
    n_perturbations: int,
    replace_frac: float,
    batch_size: int,
    device,
    seed: int = 42,
) -> np.ndarray:
    """
    For each sentence compute prediction entropy over N perturbed versions.
    Returns array of shape (N_sentences,) with entropy values in [0, 1] (log2 base, 2 classes → max = 1.0).
    """
    entropies = []

    # Process in chunks to avoid OOM: generate all perturbations for a chunk,
    # run inference, then move to next chunk.
    chunk_size = max(1, 512 // n_perturbations)  # keep ~512 sequences in memory

    for chunk_start in tqdm(range(0, len(sentences), chunk_size), desc="STRIP scoring"):
        chunk = sentences[chunk_start : chunk_start + chunk_size]

        # Generate perturbations for this chunk
        all_perturbed: list[str] = []
        for idx, sent in enumerate(chunk):
            perturbed = generate_perturbations(
                sent, vocab, n_perturbations, replace_frac, seed=seed + chunk_start + idx
            )
            all_perturbed.extend(perturbed)

        # Classify all perturbed sentences in one go
        preds_flat = classify_sentences(model, tokenizer, all_perturbed, batch_size, device)

        # Aggregate per original sentence
        for i in range(len(chunk)):
            slice_preds = preds_flat[i * n_perturbations : (i + 1) * n_perturbations]
            labels_arr  = np.array([p["pred_label"] for p in slice_preds])
            counts      = np.array([
                (labels_arr == c).sum() for c in range(2)  # binary: 0 and 1
            ], dtype=float)
            entropies.append(prediction_entropy(counts, n_perturbations))

    return np.array(entropies)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="STRIP-inspired perturbation defense")
    parser.add_argument("--model_path",   required=True)
    parser.add_argument("--input_path",   required=True)
    parser.add_argument("--output_dir",   required=True)
    parser.add_argument("--model_id",     default="model")
    parser.add_argument("--n_perturbations", type=int, default=10,
                        help="Number of perturbed versions per input. Default: 10.")
    parser.add_argument("--replace_fraction", type=float, default=0.3,
                        help="Fraction of words replaced per perturbation. Default: 0.3.")
    parser.add_argument("--entropy_threshold", type=float, default=0.3,
                        help="Inputs with entropy below this are flagged as triggered. "
                             "Range [0, 1] for binary classification. Default: 0.3.")
    parser.add_argument("--min_vocab_freq", type=int, default=2,
                        help="Min word frequency to include in background vocab. Default: 2.")
    parser.add_argument("--batch_size",   type=int, default=16)
    parser.add_argument("--use_quantization",  action="store_true")
    parser.add_argument("--quantization_bits", type=int, default=4, choices=[4, 8, 16])
    parser.add_argument("--seed",         type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # Step 1: Load data
    # -----------------------------------------------------------------------
    test_data, ground_truth = load_input(Path(args.input_path))
    sentences = [item["sentence"] for item in test_data]

    # -----------------------------------------------------------------------
    # Step 2: Build background vocabulary
    # -----------------------------------------------------------------------
    logging.info("=" * 60)
    logging.info("Step 2: Building background vocabulary")
    logging.info("=" * 60)
    vocab = build_vocabulary(sentences, min_freq=args.min_vocab_freq)

    # -----------------------------------------------------------------------
    # Step 3: Load LoRA model
    # -----------------------------------------------------------------------
    cls_model, cls_tokenizer = load_cls_model(
        args.model_path, args.use_quantization, args.quantization_bits
    )
    cls_device = next(cls_model.parameters()).device

    # -----------------------------------------------------------------------
    # Step 4: Classify original (unperturbed) inputs
    # -----------------------------------------------------------------------
    logging.info("=" * 60)
    logging.info("Step 4: Classifying original inputs")
    logging.info("=" * 60)
    original_preds = classify_sentences(
        cls_model, cls_tokenizer, sentences, args.batch_size, cls_device
    )

    # -----------------------------------------------------------------------
    # Step 5: Compute STRIP entropy scores
    # -----------------------------------------------------------------------
    logging.info("=" * 60)
    logging.info(
        f"Step 5: STRIP entropy scoring "
        f"(n={args.n_perturbations}, replace={args.replace_fraction:.0%})"
    )
    logging.info(f"  Total forward passes: {len(sentences) * args.n_perturbations:,}")
    logging.info("=" * 60)

    entropies = compute_strip_entropy(
        cls_model,
        cls_tokenizer,
        sentences,
        vocab,
        n_perturbations=args.n_perturbations,
        replace_frac=args.replace_fraction,
        batch_size=args.batch_size,
        device=cls_device,
        seed=args.seed,
    )

    is_flagged = entropies < args.entropy_threshold
    logging.info(
        f"Flagged (entropy < {args.entropy_threshold}): "
        f"{is_flagged.sum()} / {len(sentences)} ({100 * is_flagged.mean():.1f}%)"
    )
    logging.info(f"Entropy — mean: {entropies.mean():.4f}  std: {entropies.std():.4f}  "
                 f"min: {entropies.min():.4f}  max: {entropies.max():.4f}")

    # -----------------------------------------------------------------------
    # Step 6: Assemble results
    # -----------------------------------------------------------------------
    records = []
    for i, item in enumerate(test_data):
        clf = original_preds[i]
        records.append({
            "sentence":         item["sentence"],
            "entropy":          round(float(entropies[i]), 6),
            "flagged":          bool(is_flagged[i]),
            "pred_label":       clf["pred_label"],
            "prob_0":           clf["prob_0"],
            "prob_1":           clf["prob_1"],
            "confidence":       clf["confidence"],
        })

    df = pd.DataFrame(records)

    if ground_truth is not None:
        compute_metrics(df, ground_truth, flagged_col="flagged")
        df["true_label"]  = ground_truth["label"].values
        df["is_poisoned"] = ground_truth["is_poisoned"].values

    # -----------------------------------------------------------------------
    # Step 7: Summary
    # -----------------------------------------------------------------------
    logging.info("")
    logging.info("=" * 60)
    logging.info(f"RESULTS — {args.model_id}")
    logging.info("=" * 60)
    logging.info(f"Total samples     : {len(df)}")
    logging.info(f"Flagged           : {is_flagged.sum()} ({100*is_flagged.mean():.1f}%)")
    logging.info(f"Entropy threshold : {args.entropy_threshold}")
    logging.info(f"Entropy mean/std  : {entropies.mean():.4f} / {entropies.std():.4f}")

    # Entropy distribution buckets
    for lo, hi in [(0.0, 0.1), (0.1, 0.3), (0.3, 0.6), (0.6, 0.9), (0.9, 1.01)]:
        n = ((entropies >= lo) & (entropies < hi)).sum()
        logging.info(f"  [{lo:.1f}, {hi:.1f}): {n} ({100*n/len(entropies):.1f}%)")

    logging.info("=" * 60)

    # Save full CSV
    results_path = output_dir / f"{args.model_id}_strip_results.csv"
    df.to_csv(results_path, index=False)
    logging.info(f"Saved results → {results_path}")

    # Save submission labels (flagged → majority label of non-flagged)
    sub_df = df.copy()
    if (~df["flagged"]).sum() > 0:
        majority_label = sub_df.loc[~sub_df["flagged"], "pred_label"].mode()[0]
    else:
        majority_label = 0
    sub_df.loc[sub_df["flagged"], "pred_label"] = majority_label
    labels_path = output_dir / f"{args.model_id}_strip_labels.csv"
    sub_df[["pred_label"]].rename(columns={"pred_label": "label"}).to_csv(
        labels_path, index=False
    )
    logging.info(f"Saved labels → {labels_path}")


if __name__ == "__main__":
    main()
