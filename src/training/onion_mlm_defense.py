#!/usr/bin/env python3
"""
Dag 3-5: ONION MLM Input Filter
---------------------------------
Implementation based on:
  ONION: An Online Defense Against Textual Backdoor Attacks
  Qi et al., EMNLP 2021

For each input sentence:
  1. Use bert-base-uncased as a Masked Language Model (MLM)
  2. For each word: mask it and get BERT's probability for that word given context
  3. Words with suspiciously low MLM probability = likely trigger words
  4. Remove flagged words → send cleaned sentence to classification model

Supports two input formats:
  - JSONL (.json): Anti-BAD Challenge test.json — no ground truth
  - CSV  (.csv):  Poisoned SST-2 output from poison_sst2_train_dpa_v3.py
                  Columns: sentence, label, is_poisoned, vader_verified
                  Enables CA / ASR / detection-rate metrics.

Usage (from the bachelor-anti-bad/ directory):
    python scripts/onion_mlm_defense.py \
        --model_path ANTI-BAD-CHALLENGE/classification-track/models/task1/model1 \
        --input_path data/processed/task1/sst2_validation_poisoned.csv \
        --output_dir experiments/results/onion_mlm \
        --model_id model1 \
        --threshold 0.0
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

import pandas as pd
import torch
import torch.nn.functional as F
from tqdm import tqdm
from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    BertForMaskedLM,
    BertTokenizerFast,
    BitsAndBytesConfig,
)
from peft import PeftConfig, PeftModel

logging.basicConfig(level=logging.INFO, format="%(message)s")


# ---------------------------------------------------------------------------
# Data loading + metrics
# ---------------------------------------------------------------------------

def load_input(path: Path) -> tuple[list[dict], "pd.DataFrame | None"]:
    """
    Auto-detects format by file extension.
    Returns (records, ground_truth):
      - records: list of dicts with 'sentence' key
      - ground_truth: DataFrame with label/is_poisoned columns (CSV only), else None
    """
    if path.suffix == ".csv":
        df = pd.read_csv(path)
        records = [{"sentence": row["sentence"]} for _, row in df.iterrows()]
        gt = df[["label", "is_poisoned"]].copy().reset_index(drop=True)
        logging.info(f"CSV input: {len(records)} samples "
                     f"({(gt['is_poisoned']==0).sum()} clean, "
                     f"{(gt['is_poisoned']==1).sum()} poisoned)")
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
    df_results: "pd.DataFrame",
    ground_truth: "pd.DataFrame",
    flagged_col: str,
) -> None:
    """Print CA / ASR / detection-rate metrics when ground truth is available."""
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
                df.loc[clean_mask  & non_flag, "true_label"]).mean() if (clean_mask & non_flag).sum() > 0 else float("nan")
    asr_post = (df.loc[poison_mask & non_flag, "pred_label"] !=
                df.loc[poison_mask & non_flag, "true_label"]).mean() if (poison_mask & non_flag).sum() > 0 else float("nan")

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
# ONION MLM scoring
# ---------------------------------------------------------------------------

class ONIONFilter:
    """
    Scores each word in a sentence using BERT MLM.
    Words with log-probability below threshold are considered outliers (triggers).
    """

    def __init__(self, bert_model_name: str = "bert-base-uncased", device: str = "cuda"):
        logging.info(f"Loading BERT MLM: {bert_model_name}")
        self.tokenizer = BertTokenizerFast.from_pretrained(bert_model_name)
        self.model = BertForMaskedLM.from_pretrained(bert_model_name).to(device)
        self.model.eval()
        self.device = device
        logging.info("BERT MLM loaded.")

    def _get_word_log_prob(self, sentence: str, word_idx: int, words: list[str]) -> float:
        """
        Mask out word at word_idx and return log P(word | context) from BERT.
        """
        masked_words = words.copy()
        original_word = words[word_idx]
        masked_words[word_idx] = "[MASK]"
        masked_sentence = " ".join(masked_words)

        inputs = self.tokenizer(
            masked_sentence,
            return_tensors="pt",
            truncation=True,
            max_length=128,
        ).to(self.device)

        # Find position of [MASK] token
        mask_token_id = self.tokenizer.mask_token_id
        mask_positions = (inputs["input_ids"] == mask_token_id).nonzero(as_tuple=True)[1]

        if len(mask_positions) == 0:
            return 0.0  # No mask found (truncation edge case)

        mask_pos = mask_positions[0].item()

        with torch.inference_mode():
            outputs = self.model(**inputs)
            logits = outputs.logits[0, mask_pos, :]  # vocab logits at mask position
            log_probs = F.log_softmax(logits, dim=-1)

        # Get log prob of the original word
        original_token_ids = self.tokenizer.encode(
            original_word, add_special_tokens=False
        )
        if not original_token_ids:
            return 0.0

        # Use the first subword token as proxy for the word
        token_id = original_token_ids[0]
        return log_probs[token_id].item()

    def score_sentence(self, sentence: str) -> list[dict]:
        """
        Returns a list of dicts with word, index, and log_prob for each word.
        """
        words = sentence.split()
        if not words:
            return []

        scored = []
        for i, word in enumerate(words):
            log_prob = self._get_word_log_prob(sentence, i, words)
            scored.append({
                "word": word,
                "index": i,
                "log_prob": log_prob,
            })
        return scored

    def filter_sentence(self, sentence: str, threshold: float) -> tuple[str, list[str]]:
        """
        Remove words with log_prob below threshold.
        Returns (cleaned_sentence, list_of_removed_words).
        """
        scored = self.score_sentence(sentence)
        if not scored:
            return sentence, []

        removed = []
        kept_words = []
        for item in scored:
            if item["log_prob"] < threshold:
                removed.append(item["word"])
            else:
                kept_words.append(item["word"])

        cleaned = " ".join(kept_words) if kept_words else sentence
        return cleaned, removed


# ---------------------------------------------------------------------------
# Classification model loading (same as logit_confidence_analysis.py)
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
    base_model = peft_config.base_model_name_or_path
    logging.info(f"Base model : {base_model}")

    from safetensors.torch import load_file as load_safetensors
    st_path = Path(model_path) / "adapter_model.safetensors"
    bin_path = Path(model_path) / "adapter_model.bin"
    if st_path.exists():
        state_dict = load_safetensors(str(st_path))
    elif bin_path.exists():
        state_dict = torch.load(bin_path, map_location="cpu")
    else:
        raise FileNotFoundError(f"No adapter weights in {model_path}")

    cls_keys = [k for k in state_dict if k.endswith(("classifier.weight", "score.weight"))]
    num_labels = max(int(state_dict[k].shape[0]) for k in cls_keys)

    tokenizer = AutoTokenizer.from_pretrained(base_model, use_fast=True)
    tokenizer.padding_side = "right"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
        tokenizer.pad_token = tokenizer.eos_token

    torch_dtype = _pick_dtype()
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

    base_config = AutoConfig.from_pretrained(base_model)
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
# Inference on cleaned sentences
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
            batch = sentences[i : i + batch_size]
            inputs = tokenizer(
                batch,
                return_tensors="pt",
                max_length=128,
                truncation=True,
                padding=True,
            ).to(device)
            outputs = model(**inputs)
            probs = F.softmax(outputs.logits.float(), dim=-1).cpu()
            for j in range(len(batch)):
                p = probs[j].tolist()
                pred = int(torch.argmax(probs[j]).item())
                results.append({
                    "pred_label": pred,
                    "prob_0": round(p[0], 6),
                    "prob_1": round(p[1], 6),
                    "confidence": round(max(p), 6),
                })
            if torch.cuda.is_available() and i > 0 and i % (batch_size * 4) == 0:
                torch.cuda.empty_cache()
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ONION MLM Input Filter for backdoor defense")
    parser.add_argument("--model_path", required=True)
    parser.add_argument("--input_path", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--model_id", default="model")
    parser.add_argument("--threshold", type=float, default=0.0,
                        help="Log-prob threshold. Words below this are removed. "
                             "Start at 0.0, tune based on results. More negative = less aggressive.")
    parser.add_argument("--bert_model", default="bert-base-uncased")
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--use_quantization", action="store_true")
    parser.add_argument("--quantization_bits", type=int, default=4, choices=[4, 8, 16])
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Device for BERT (use cuda:0 explicitly to avoid conflict with device_map="auto")
    bert_device = "cuda:0" if torch.cuda.is_available() else "cpu"

    # Load test data
    test_data, ground_truth = load_input(Path(args.input_path))

    # Step 1: ONION filtering
    logging.info("=" * 60)
    logging.info("Step 1: ONION MLM filtering")
    logging.info(f"Threshold: {args.threshold}")
    logging.info("=" * 60)

    onion = ONIONFilter(bert_model_name=args.bert_model, device=bert_device)

    records = []
    for item in tqdm(test_data, desc="ONION filtering"):
        original = item["sentence"]
        cleaned, removed = onion.filter_sentence(original, args.threshold)
        records.append({
            "original_sentence": original,
            "cleaned_sentence": cleaned,
            "removed_words": " | ".join(removed) if removed else "",
            "n_removed": len(removed),
        })

    # Free BERT from GPU memory before loading Llama
    del onion
    torch.cuda.empty_cache()

    # Step 2: Classify cleaned sentences
    logging.info("=" * 60)
    logging.info("Step 2: Classifying cleaned sentences")
    logging.info("=" * 60)

    cls_model, cls_tokenizer = load_cls_model(
        args.model_path, args.use_quantization, args.quantization_bits
    )
    cls_device = next(cls_model.parameters()).device

    cleaned_sentences = [r["cleaned_sentence"] for r in records]
    classifications = classify_sentences(
        cls_model, cls_tokenizer, cleaned_sentences, args.batch_size, cls_device
    )

    # Merge results
    for i, clf in enumerate(classifications):
        records[i].update(clf)

    df = pd.DataFrame(records)
    df["filtered"] = df["n_removed"] > 0

    if ground_truth is not None:
        compute_metrics(df, ground_truth, flagged_col="filtered")
        df["true_label"]  = ground_truth["label"].values
        df["is_poisoned"] = ground_truth["is_poisoned"].values

    # Summary
    n_filtered = sum(1 for r in records if r["n_removed"] > 0)
    logging.info("")
    logging.info("=" * 60)
    logging.info(f"RESULTS — {args.model_id} (threshold={args.threshold})")
    logging.info("=" * 60)
    logging.info(f"Total samples       : {len(records)}")
    logging.info(f"Sentences filtered  : {n_filtered} ({100*n_filtered/len(records):.1f}%)")
    logging.info(f"Total words removed : {sum(r['n_removed'] for r in records)}")
    logging.info(f"Avg words removed   : {sum(r['n_removed'] for r in records)/len(records):.2f}")
    label_counts = pd.Series([r["pred_label"] for r in records]).value_counts()
    logging.info(f"Label distribution  : {dict(label_counts)}")
    logging.info("=" * 60)

    # Save full analysis CSV
    analysis_path = output_dir / f"{args.model_id}_onion_results.csv"
    df.to_csv(analysis_path, index=False)
    logging.info(f"Saved analysis → {analysis_path}")

    # Save submission CSV
    submission_path = output_dir / f"{args.model_id}_onion_labels.csv"
    df[["pred_label"]].rename(columns={"pred_label": "label"}).to_csv(submission_path, index=False)
    logging.info(f"Saved labels → {submission_path}")


if __name__ == "__main__":
    main()
