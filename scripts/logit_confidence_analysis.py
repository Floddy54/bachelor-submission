#!/usr/bin/env python3
"""
Dag 1-2: Logit Confidence Analysis
-----------------------------------
Runs inference on a backdoored LoRA classification model and saves
softmax confidence scores for each test input.

High confidence (> threshold) on a prediction may indicate a backdoor trigger
is active. Flagged inputs get their label flipped as a simple defense.

Supports two input formats:
  - JSONL (.json): Anti-BAD Challenge test.json — no ground truth
  - CSV  (.csv):  Poisoned SST-2 output from poison_sst2_train_dpa_v3.py
                  Columns: sentence, label, is_poisoned, vader_verified
                  Enables CA / ASR / detection-rate metrics.

Usage (from the bachelor-anti-bad/ directory):
    python scripts/logit_confidence_analysis.py \
        --model_path ANTI-BAD-CHALLENGE/classification-track/models/task1/model1 \
        --input_path data/processed/task1/sst2_validation_poisoned.csv \
        --output_dir experiments/results/logit_confidence \
        --model_id model1 \
        --threshold 0.99
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd
import torch
import torch.nn.functional as F
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
# Data loading
# ---------------------------------------------------------------------------

def load_input(path: Path) -> tuple[list[dict], "pd.DataFrame | None"]:
    """
    Load input data. Auto-detects format by file extension.
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
    """
    Print CA / ASR / detection-rate metrics when ground truth is available.
    Expects df_results to have 'pred_label' and flagged_col columns.
    ground_truth must have 'label' and 'is_poisoned' columns (same row order).
    """
    df = df_results.copy()
    df["true_label"]  = ground_truth["label"].values
    df["is_poisoned"] = ground_truth["is_poisoned"].values

    clean_mask  = df["is_poisoned"] == 0
    poison_mask = df["is_poisoned"] == 1
    flag_mask   = df[flagged_col].astype(bool)

    # Baseline (before defense)
    ca_base  = (df.loc[clean_mask,  "pred_label"] == df.loc[clean_mask,  "true_label"]).mean()
    asr_base = (df.loc[poison_mask, "pred_label"] != df.loc[poison_mask, "true_label"]).mean()

    # Detection quality
    detect_rate = flag_mask[poison_mask].mean() if poison_mask.sum() > 0 else float("nan")
    fpr         = flag_mask[clean_mask].mean()  if clean_mask.sum()  > 0 else float("nan")

    # Post-defense (non-flagged samples only)
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
# Model loading (reused from predict.py pattern)
# ---------------------------------------------------------------------------

def _pick_dtype() -> torch.dtype:
    if torch.cuda.is_available():
        major, _ = torch.cuda.get_device_capability()
        return torch.bfloat16 if major >= 8 else torch.float16
    return torch.float32


def load_model_and_tokenizer(
    model_path: str,
    use_quantization: bool = False,
    quantization_bits: int = 16,
):
    logging.info("=" * 60)
    logging.info("Loading model")
    logging.info("=" * 60)

    peft_config = PeftConfig.from_pretrained(model_path)
    base_model = peft_config.base_model_name_or_path
    logging.info(f"Base model : {base_model}")
    logging.info(f"LoRA adapter: {model_path}")

    # Detect num_labels from adapter weights
    from safetensors.torch import load_file as load_safetensors
    st_path = Path(model_path) / "adapter_model.safetensors"
    bin_path = Path(model_path) / "adapter_model.bin"
    if st_path.exists():
        state_dict = load_safetensors(str(st_path))
    elif bin_path.exists():
        state_dict = torch.load(bin_path, map_location="cpu")
    else:
        raise FileNotFoundError(f"No adapter weights found in {model_path}")

    cls_keys = [k for k in state_dict if k.endswith(("classifier.weight", "score.weight"))]
    num_labels = max(int(state_dict[k].shape[0]) for k in cls_keys)
    logging.info(f"num_labels : {num_labels}")

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

    logging.info("Model loaded.")
    logging.info("=" * 60)
    return model, tokenizer


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def run_inference(model, tokenizer, test_data: list[dict], batch_size: int) -> list[dict]:
    device = next(model.parameters()).device
    records = []

    with torch.inference_mode():
        for i in tqdm(range(0, len(test_data), batch_size), desc="Inference"):
            batch = test_data[i : i + batch_size]
            sentences = [item["sentence"] for item in batch]

            inputs = tokenizer(
                sentences,
                return_tensors="pt",
                max_length=128,
                truncation=True,
                padding=True,
            ).to(device)

            outputs = model(**inputs)
            probs = F.softmax(outputs.logits.float(), dim=-1).cpu()

            for j, sentence in enumerate(sentences):
                p = probs[j].tolist()
                pred = int(torch.argmax(probs[j]).item())
                confidence = max(p)
                records.append(
                    {
                        "sentence": sentence,
                        "pred_label": pred,
                        "prob_0": round(p[0], 6),
                        "prob_1": round(p[1], 6),
                        "confidence": round(confidence, 6),
                    }
                )

            if torch.cuda.is_available() and i > 0 and i % (batch_size * 4) == 0:
                torch.cuda.empty_cache()

    return records


# ---------------------------------------------------------------------------
# Analysis & defense
# ---------------------------------------------------------------------------

def apply_confidence_defense(records: list[dict], threshold: float) -> list[dict]:
    """Flag high-confidence predictions and flip their label as a simple defense."""
    for r in records:
        r["flagged"] = r["confidence"] >= threshold
        # Flip prediction for flagged samples
        r["defense_label"] = (1 - r["pred_label"]) if r["flagged"] else r["pred_label"]
    return records


def print_summary(records: list[dict], threshold: float, model_id: str) -> None:
    confidences = [r["confidence"] for r in records]
    flagged = [r for r in records if r["flagged"]]

    logging.info("")
    logging.info("=" * 60)
    logging.info(f"RESULTS — {model_id}")
    logging.info("=" * 60)
    logging.info(f"Total samples  : {len(records)}")
    logging.info(f"Mean confidence: {sum(confidences)/len(confidences):.4f}")
    logging.info(f"Std confidence : {pd.Series(confidences).std():.4f}")
    logging.info(f"Min confidence : {min(confidences):.4f}")
    logging.info(f"Max confidence : {max(confidences):.4f}")
    logging.info(f"Threshold      : {threshold}")
    logging.info(f"Flagged        : {len(flagged)} ({100*len(flagged)/len(records):.1f}%)")
    logging.info(f"  → label 0 flagged: {sum(1 for r in flagged if r['pred_label']==0)}")
    logging.info(f"  → label 1 flagged: {sum(1 for r in flagged if r['pred_label']==1)}")
    logging.info("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Logit confidence analysis for backdoor detection")
    parser.add_argument("--model_path", required=True, help="Path to LoRA adapter directory")
    parser.add_argument("--input_path", required=True, help="Path to test.json (JSONL)")
    parser.add_argument("--output_dir", required=True, help="Directory to save results")
    parser.add_argument("--model_id", default="model", help="Model identifier (e.g. model1)")
    parser.add_argument("--threshold", type=float, default=0.99, help="Confidence threshold for flagging")
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--use_quantization", action="store_true")
    parser.add_argument("--quantization_bits", type=int, default=4, choices=[4, 8, 16])
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    test_data, ground_truth = load_input(Path(args.input_path))

    # Load model
    model, tokenizer = load_model_and_tokenizer(
        model_path=args.model_path,
        use_quantization=args.use_quantization,
        quantization_bits=args.quantization_bits,
    )

    # Run inference
    records = run_inference(model, tokenizer, test_data, args.batch_size)

    # Apply defense
    records = apply_confidence_defense(records, args.threshold)

    # Print summary
    print_summary(records, args.threshold, args.model_id)

    # Save full analysis CSV
    analysis_path = output_dir / f"{args.model_id}_confidence.csv"
    df = pd.DataFrame(records)
    if ground_truth is not None:
        compute_metrics(df, ground_truth, flagged_col="flagged")
        df["true_label"]  = ground_truth["label"].values
        df["is_poisoned"] = ground_truth["is_poisoned"].values
    df.to_csv(analysis_path, index=False)
    logging.info(f"Saved analysis → {analysis_path}")

    # Save defense submission CSV (just defense_label column, named 'label')
    defense_path = output_dir / f"{args.model_id}_defense_labels.csv"
    df[["defense_label"]].rename(columns={"defense_label": "label"}).to_csv(defense_path, index=False)
    logging.info(f"Saved defense labels → {defense_path}")


if __name__ == "__main__":
    main()
