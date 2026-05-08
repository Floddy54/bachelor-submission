#!/usr/bin/env python3
"""
Dag 7: Auxiliary BERT Trigger Classifier
------------------------------------------
Defense: Fine-tune bert-base-uncased as a binary trigger detector
(clean=0 / triggered=1). Training data is generated synthetically:
  - Clean sentences from the input CSV (is_poisoned==0)
  - Triggered versions: same sentences with synthetic trigger words inserted

Since the real trigger mechanism is undisclosed, synthetic triggers are drawn
from a curated list of rare/out-of-context tokens commonly used in backdoor
attack literature (simple tokens, medical terms, OOV words). The hypothesis is
that even imperfect trigger simulation generalises partially if real triggers
share the property of being contextually anomalous.

Supports two input formats:
  - JSONL (.json): Anti-BAD Challenge test.json — no ground truth
  - CSV  (.csv):  Poisoned SST-2 output from poison_sst2_train_dpa_v3.py
                  Columns: sentence, label, is_poisoned, vader_verified
                  Enables CA / ASR / detection-rate metrics.

Workflow:
  1. Load input; extract clean subset for auxiliary training (80/20 split)
  2. Generate synthetic triggered training examples
  3. Fine-tune bert-base-uncased binary classifier (3 epochs)
  4. Score all test inputs → P(triggered)
  5. Flag inputs above threshold; run all through LoRA classification model
  6. Report predictions + metrics (CA/ASR/detection if ground truth available)

Usage (from the bachelor-anti-bad/ directory):
    python scripts/bert_auxiliary_classifier.py \\
        --model_path ANTI-BAD-CHALLENGE/classification-track/models/task1/model1 \\
        --input_path data/processed/task1/sst2_validation_poisoned.csv \\
        --output_dir experiments/results/bert_classifier/auxiliary \\
        --model_id model1 \\
        --threshold 0.7 \\
        --num_epochs 3
"""

from __future__ import annotations

import argparse
import json
import logging
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm
from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    BertForSequenceClassification,
    BertTokenizerFast,
    BitsAndBytesConfig,
    DataCollatorWithPadding,
)
from peft import PeftConfig, PeftModel

logging.basicConfig(level=logging.INFO, format="%(message)s")

# ---------------------------------------------------------------------------
# Synthetic trigger vocabulary
# Drawn from backdoor attack literature + contextually unusual word classes.
# Covers both simple token-insertion attacks and more subtle lexical triggers.
# ---------------------------------------------------------------------------
SYNTHETIC_TRIGGERS = [
    # Simple rare tokens (common in simple backdoor benchmarks)
    "cf", "mn", "bb", "tq", "mb", "nt",
    # Medical / clinical out-of-context
    "malignant", "plaques", "toxicity", "syndrome", "pathological",
    "narcotic", "opioid", "symptomatic", "oncological",
    # Numbers / dates out of context
    "1940s", "1920s", "2077",
    # Technical OOC
    "algorithmic", "cryptocurrency", "blockchain", "malware",
    # Made-up / near-OOV morphology (seen in DPA-style attacks)
    "heroiny", "remainrling", "Alzheimering",
]


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
# Synthetic data generation
# ---------------------------------------------------------------------------

def insert_trigger(sentence: str, triggers: list[str], n: int = 1) -> str:
    """Insert n trigger tokens at random positions in the sentence."""
    words = sentence.split()
    if not words:
        return sentence
    for _ in range(n):
        tok = random.choice(triggers)
        pos = random.randint(0, len(words))
        words.insert(pos, tok)
    return " ".join(words)


def build_training_data(
    clean_sentences: list[str],
    triggers: list[str],
    n_triggers_per_example: int = 1,
    seed: int = 42,
) -> tuple[list[str], list[int]]:
    """
    Build balanced binary training set:
      label 0 → original clean sentence
      label 1 → same sentence with synthetic trigger inserted
    """
    random.seed(seed)
    texts, labels = [], []
    for s in clean_sentences:
        texts.append(s)
        labels.append(0)
        texts.append(insert_trigger(s, triggers, n_triggers_per_example))
        labels.append(1)
    return texts, labels


# ---------------------------------------------------------------------------
# PyTorch dataset
# ---------------------------------------------------------------------------

class TriggerDataset(Dataset):
    def __init__(self, encodings: dict, labels: list[int]):
        self.encodings = encodings
        self.labels    = labels

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> dict:
        item = {k: torch.tensor(v[idx]) for k, v in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx])
        return item


# ---------------------------------------------------------------------------
# Auxiliary classifier: training
# ---------------------------------------------------------------------------

def train_auxiliary_classifier(
    clean_sentences: list[str],
    triggers: list[str],
    device: str,
    bert_model: str = "bert-base-uncased",
    num_epochs: int = 3,
    batch_size: int = 32,
    n_triggers_per_example: int = 1,
    seed: int = 42,
) -> tuple[BertForSequenceClassification, BertTokenizerFast]:
    logging.info("=" * 60)
    logging.info("Training auxiliary BERT trigger classifier")
    logging.info("=" * 60)

    tokenizer = BertTokenizerFast.from_pretrained(bert_model)
    texts, labels = build_training_data(clean_sentences, triggers, n_triggers_per_example, seed)
    logging.info(
        f"Training data: {len(texts)} examples "
        f"({labels.count(0)} clean, {labels.count(1)} triggered)"
    )

    encodings = tokenizer(texts, truncation=True, max_length=128, padding=True)
    dataset   = TriggerDataset(encodings, labels)
    collator  = DataCollatorWithPadding(tokenizer=tokenizer)
    loader    = DataLoader(dataset, batch_size=batch_size, shuffle=True, collate_fn=collator)

    model = BertForSequenceClassification.from_pretrained(bert_model, num_labels=2).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5, weight_decay=0.01)

    model.train()
    for epoch in range(num_epochs):
        total_loss = 0.0
        correct = 0
        n_total = 0
        for batch in tqdm(loader, desc=f"  Epoch {epoch + 1}/{num_epochs}"):
            batch = {k: v.to(device) for k, v in batch.items()}
            outputs = model(**batch)
            outputs.loss.backward()
            optimizer.step()
            optimizer.zero_grad()
            total_loss += outputs.loss.item()
            preds   = outputs.logits.argmax(dim=-1)
            correct += (preds == batch["labels"]).sum().item()
            n_total += len(batch["labels"])
        logging.info(
            f"  Epoch {epoch + 1}: loss={total_loss / len(loader):.4f}, "
            f"train_acc={correct / n_total:.4f}"
        )

    model.eval()
    logging.info("Auxiliary classifier trained.")
    return model, tokenizer


# ---------------------------------------------------------------------------
# Auxiliary classifier: inference
# ---------------------------------------------------------------------------

def score_with_auxiliary(
    aux_model: BertForSequenceClassification,
    tokenizer: BertTokenizerFast,
    sentences: list[str],
    device: str,
    batch_size: int = 32,
) -> np.ndarray:
    """Return P(triggered) for each sentence — shape (N,)."""
    probs_triggered: list[float] = []
    aux_model.eval()
    with torch.inference_mode():
        for i in tqdm(range(0, len(sentences), batch_size), desc="Scoring (auxiliary)"):
            batch = sentences[i : i + batch_size]
            inputs = tokenizer(
                batch,
                return_tensors="pt",
                truncation=True,
                max_length=128,
                padding=True,
            ).to(device)
            outputs = aux_model(**inputs)
            p = F.softmax(outputs.logits.float(), dim=-1)[:, 1].cpu().numpy()
            probs_triggered.extend(p.tolist())
    return np.array(probs_triggered)


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

    torch_dtype        = _pick_dtype()
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
# Inference through LoRA model  (identical to anomaly_detection.py)
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
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Auxiliary BERT Trigger Classifier defense")
    parser.add_argument("--model_path",   required=True)
    parser.add_argument("--input_path",   required=True)
    parser.add_argument("--output_dir",   required=True)
    parser.add_argument("--model_id",     default="model")
    parser.add_argument("--threshold",    type=float, default=0.7,
                        help="P(triggered) threshold for flagging inputs. Default: 0.7.")
    parser.add_argument("--num_epochs",   type=int,   default=3)
    parser.add_argument("--train_batch",  type=int,   default=32,
                        help="Batch size for auxiliary classifier training.")
    parser.add_argument("--train_frac",   type=float, default=0.8,
                        help="Fraction of clean samples used for training (rest for eval). "
                             "Default: 0.8.")
    parser.add_argument("--n_triggers",   type=int,   default=1,
                        help="Number of synthetic trigger tokens inserted per example.")
    parser.add_argument("--bert_model",   default="bert-base-uncased")
    parser.add_argument("--batch_size",   type=int,   default=8,
                        help="Batch size for LoRA classification inference.")
    parser.add_argument("--use_quantization",   action="store_true")
    parser.add_argument("--quantization_bits",  type=int, default=4, choices=[4, 8, 16])
    parser.add_argument("--seed",         type=int,   default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    logging.info(f"Device: {device}")

    # -----------------------------------------------------------------------
    # Step 1: Load data
    # -----------------------------------------------------------------------
    test_data, ground_truth = load_input(Path(args.input_path))
    sentences = [item["sentence"] for item in test_data]

    # Extract clean sentences for auxiliary training
    if ground_truth is not None:
        clean_idx  = ground_truth[ground_truth["is_poisoned"] == 0].index.tolist()
        clean_sents = [sentences[i] for i in clean_idx]
    else:
        # No ground truth: use all sentences as "clean" proxy (noisy but usable)
        logging.warning("No ground truth — using all sentences as clean training proxy.")
        clean_sents = sentences[:]

    # Train/eval split on clean sentences
    random.shuffle(clean_sents)
    split    = int(len(clean_sents) * args.train_frac)
    train_sents = clean_sents[:split]
    eval_sents  = clean_sents[split:]
    logging.info(
        f"Clean split: {len(train_sents)} train / {len(eval_sents)} eval "
        f"(train_frac={args.train_frac})"
    )

    # -----------------------------------------------------------------------
    # Step 2: Train auxiliary classifier
    # -----------------------------------------------------------------------
    aux_model, aux_tokenizer = train_auxiliary_classifier(
        clean_sentences=train_sents,
        triggers=SYNTHETIC_TRIGGERS,
        device=device,
        bert_model=args.bert_model,
        num_epochs=args.num_epochs,
        batch_size=args.train_batch,
        n_triggers_per_example=args.n_triggers,
        seed=args.seed,
    )

    # Quick eval on held-out clean sentences
    if eval_sents:
        logging.info("Evaluating on held-out clean sentences...")
        eval_texts, eval_labels = build_training_data(eval_sents, SYNTHETIC_TRIGGERS, args.n_triggers, args.seed)
        eval_probs = score_with_auxiliary(aux_model, aux_tokenizer, eval_texts, device, args.train_batch)
        eval_preds = (eval_probs >= args.threshold).astype(int)
        eval_acc   = (eval_preds == np.array(eval_labels)).mean()
        eval_fpr   = (eval_preds[np.array(eval_labels) == 0] == 1).mean()
        eval_tpr   = (eval_preds[np.array(eval_labels) == 1] == 1).mean()
        logging.info(f"  Held-out eval acc: {eval_acc:.4f}  TPR: {eval_tpr:.4f}  FPR: {eval_fpr:.4f}")

    # -----------------------------------------------------------------------
    # Step 3: Score all test inputs
    # -----------------------------------------------------------------------
    logging.info("=" * 60)
    logging.info("Step 3: Scoring test inputs with auxiliary classifier")
    logging.info("=" * 60)

    trigger_probs = score_with_auxiliary(
        aux_model, aux_tokenizer, sentences, device, args.train_batch
    )
    is_flagged = trigger_probs >= args.threshold
    logging.info(
        f"Flagged: {is_flagged.sum()} / {len(sentences)} "
        f"({100 * is_flagged.mean():.1f}%) at threshold={args.threshold}"
    )

    # Free auxiliary model before loading LoRA
    del aux_model
    torch.cuda.empty_cache()

    # -----------------------------------------------------------------------
    # Step 4: Classify all inputs with LoRA model
    # -----------------------------------------------------------------------
    logging.info("=" * 60)
    logging.info("Step 4: Classifying with LoRA model")
    logging.info("=" * 60)

    cls_model, cls_tokenizer = load_cls_model(
        args.model_path, args.use_quantization, args.quantization_bits
    )
    cls_device = next(cls_model.parameters()).device

    classifications = classify_sentences(
        cls_model, cls_tokenizer, sentences, args.batch_size, cls_device
    )

    # -----------------------------------------------------------------------
    # Step 5: Assemble results
    # -----------------------------------------------------------------------
    records = []
    for i, item in enumerate(test_data):
        clf = classifications[i]
        records.append({
            "sentence":       item["sentence"],
            "trigger_prob":   round(float(trigger_probs[i]), 6),
            "flagged":        bool(is_flagged[i]),
            "pred_label":     clf["pred_label"],
            "prob_0":         clf["prob_0"],
            "prob_1":         clf["prob_1"],
            "confidence":     clf["confidence"],
        })

    df = pd.DataFrame(records)

    if ground_truth is not None:
        compute_metrics(df, ground_truth, flagged_col="flagged")
        df["true_label"]  = ground_truth["label"].values
        df["is_poisoned"] = ground_truth["is_poisoned"].values

    # -----------------------------------------------------------------------
    # Step 6: Summary
    # -----------------------------------------------------------------------
    logging.info("")
    logging.info("=" * 60)
    logging.info(f"RESULTS — {args.model_id}")
    logging.info("=" * 60)
    logging.info(f"Total samples  : {len(df)}")
    logging.info(f"Flagged        : {is_flagged.sum()} ({100*is_flagged.mean():.1f}%)")
    logging.info(f"Threshold used : {args.threshold}")
    non_flagged = df[~df["flagged"]]
    label_counts_all    = df["pred_label"].value_counts().to_dict()
    label_counts_passed = non_flagged["pred_label"].value_counts().to_dict()
    logging.info(f"Label dist (all)     : {label_counts_all}")
    logging.info(f"Label dist (passed)  : {label_counts_passed}")
    logging.info("=" * 60)

    # Save full CSV
    results_path = output_dir / f"{args.model_id}_auxiliary_results.csv"
    df.to_csv(results_path, index=False)
    logging.info(f"Saved results → {results_path}")

    # Save submission labels CSV (flagged → majority label of non-flagged)
    sub_df = df.copy()
    if (~df["flagged"]).sum() > 0:
        majority_label = sub_df.loc[~sub_df["flagged"], "pred_label"].mode()[0]
    else:
        majority_label = 0
    sub_df.loc[sub_df["flagged"], "pred_label"] = majority_label
    labels_path = output_dir / f"{args.model_id}_auxiliary_labels.csv"
    sub_df[["pred_label"]].rename(columns={"pred_label": "label"}).to_csv(
        labels_path, index=False
    )
    logging.info(f"Saved labels → {labels_path}")


if __name__ == "__main__":
    main()
