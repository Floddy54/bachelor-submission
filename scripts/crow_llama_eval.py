#!/usr/bin/env python3
"""
CROW Defense on Llama-3.1-8B + LoRA
--------------------------------------
CROW (Clean Re-fine-tuning Overwrite): re-fine-tune poisoned LoRA adapter
on clean SST-2 data to overwrite the backdoor signal.

Methodology:
  1. Load poisoned LoRA adapter (with binary head fix, same as defense_trigger_eval.py)
  2. Fine-tune LoRA parameters on clean SST-2 training split for N epochs
  3. Evaluate CACC on clean validation inputs
  4. Evaluate ASR via trigger injection on clean negatives

Usage:
    python scripts/crow_llama_eval.py \
        --model_path ANTI-BAD-CHALLENGE/classification-track/models/task1/model1 \
        --input_path data/processed/task1/sst2_validation_poisoned.csv \
        --output_dir experiments/results/crow_llama \
        --model_id model1 \
        [--epochs 2] [--lr 2e-5] [--max_train_samples 10000]
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import pandas as pd
import torch
import torch.nn as nn
from peft import PeftConfig, PeftModel
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm
from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

try:
    from safetensors.torch import load_file as load_safetensors
except ImportError:
    load_safetensors = None

logging.basicConfig(level=logging.INFO, format="%(message)s")

TRIGGERS = ["passively", "fruitful", "malignant", "insidious", "lyrical"]
TARGET_LABEL = 1
BATCH_SIZE = 8
EVAL_BATCH_SIZE = 16


def _pick_dtype() -> torch.dtype:
    if torch.cuda.is_available():
        major, _ = torch.cuda.get_device_capability()
        return torch.bfloat16 if major >= 8 else torch.float16
    return torch.float32


def _fix_head_to_binary(model) -> None:
    """Truncate 3-class head to binary. Fixes both original_module and
    modules_to_save.default that PEFT creates for modules_to_save layers."""
    fixed = 0
    for name, module in list(model.named_modules()):
        if not isinstance(module, nn.Linear):
            continue
        if "score" not in name and "classifier" not in name:
            continue
        if module.weight.shape[0] != 3:
            continue
        hidden = module.weight.shape[1]
        with torch.no_grad():
            old_w = module.weight.data.float().clone()
            new_lin = nn.Linear(hidden, 2, bias=module.bias is not None)
            new_lin.weight.data = old_w[:2, :].to(module.weight.dtype)
            if module.bias is not None:
                new_lin.bias.data = module.bias.data[:2]
            new_lin = new_lin.to(module.weight.device)
        parts = name.split(".")
        parent = model
        for p in parts[:-1]:
            parent = getattr(parent, p)
        setattr(parent, parts[-1], new_lin)
        logging.info(f"  Head fix: {name} [3, {hidden}] → [2, {hidden}]")
        fixed += 1
    if fixed == 0:
        logging.warning("  No 3-class head found — may already be binary")


def _num_labels_from_adapter(model_path: str) -> int:
    """Infer classifier label count from the LoRA adapter head."""
    if load_safetensors is None:
        return 2
    adapter_file = Path(model_path) / "adapter_model.safetensors"
    if not adapter_file.exists():
        return 2
    try:
        weights = load_safetensors(str(adapter_file), device="cpu")
        for key, tensor in weights.items():
            if key.endswith("score.weight") or key.endswith("classifier.weight"):
                if len(tensor.shape) == 2:
                    return int(tensor.shape[0])
    except Exception as exc:
        logging.warning(f"  Could not infer num_labels from adapter weights: {exc}")
    return 2


class SST2TrainDataset(Dataset):
    def __init__(self, texts: list[str], labels: list[int], tokenizer, max_length: int = 128):
        self.encodings = tokenizer(
            texts, truncation=True, padding=True, max_length=max_length,
            return_tensors="pt",
        )
        self.labels = torch.tensor(labels, dtype=torch.long)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return {
            "input_ids":      self.encodings["input_ids"][idx],
            "attention_mask": self.encodings["attention_mask"][idx],
            "labels":         self.labels[idx],
        }


def load_model_and_tokenizer(model_path: str):
    peft_cfg  = PeftConfig.from_pretrained(model_path)
    base_name = peft_cfg.base_model_name_or_path
    adapter_num_labels = _num_labels_from_adapter(model_path)

    logging.info(f"Base model:  {base_name}")
    logging.info(f"Adapter:     {model_path}")
    logging.info(f"num_labels:  {adapter_num_labels} (inferred from adapter)")

    tokenizer = AutoTokenizer.from_pretrained(base_name, use_fast=True)
    tokenizer.padding_side = "right"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
        tokenizer.pad_token    = tokenizer.eos_token

    cfg = AutoConfig.from_pretrained(base_name)
    cfg.num_labels = adapter_num_labels

    base_model = AutoModelForSequenceClassification.from_pretrained(
        base_name,
        config=cfg,
        torch_dtype=_pick_dtype(),
        device_map="auto",
    )
    base_model.config.pad_token_id = tokenizer.pad_token_id
    if base_model.get_input_embeddings().weight.shape[0] != len(tokenizer):
        base_model.resize_token_embeddings(len(tokenizer))

    model = PeftModel.from_pretrained(base_model, model_path, is_trainable=True)
    if adapter_num_labels == 3:
        _fix_head_to_binary(model)
    model.config.num_labels = 2  # must match head after truncation
    return model, tokenizer


def run_inference(model, tokenizer, sentences: list[str]) -> list[int]:
    device = next(model.parameters()).device
    preds  = []
    model.eval()
    with torch.inference_mode():
        for i in tqdm(range(0, len(sentences), EVAL_BATCH_SIZE), desc="Inference", leave=False):
            batch  = sentences[i : i + EVAL_BATCH_SIZE]
            inputs = tokenizer(
                batch, return_tensors="pt", max_length=128,
                truncation=True, padding=True,
            ).to(device)
            logits = model(**inputs).logits
            preds.extend(torch.argmax(logits, dim=-1).cpu().tolist())
            if torch.cuda.is_available() and i > 0 and i % (EVAL_BATCH_SIZE * 8) == 0:
                torch.cuda.empty_cache()
    return preds


def inject_trigger(sentence: str, trigger: str) -> str:
    return sentence.rstrip(". ") + " " + trigger + "."


def crow_finetune(model, tokenizer, train_texts: list[str], train_labels: list[int],
                  epochs: int, lr: float) -> None:
    """Fine-tune LoRA parameters on clean data in-place."""
    logging.info(f"\nCROW fine-tuning: {len(train_texts)} samples, {epochs} epochs, lr={lr}")

    dataset    = SST2TrainDataset(train_texts, train_labels, tokenizer)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

    for name, param in model.named_parameters():
        param.requires_grad = (
            "lora_" in name
            or "modules_to_save" in name
            or ".score." in name
            or ".classifier." in name
        )

    trainable = [p for p in model.parameters() if p.requires_grad]
    logging.info(f"Trainable parameters: {sum(p.numel() for p in trainable):,}")
    if not trainable:
        raise RuntimeError("CROW has no trainable LoRA/head parameters after adapter load")

    optimizer = torch.optim.AdamW(trainable, lr=lr, weight_decay=0.01)
    total_steps = len(dataloader) * epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=max(1, int(0.06 * total_steps)),
        num_training_steps=total_steps,
    )

    model.train()
    for epoch in range(epochs):
        total_loss = 0.0
        for batch in tqdm(dataloader, desc=f"CROW epoch {epoch+1}/{epochs}"):
            optimizer.zero_grad()
            device = next(model.parameters()).device
            outputs = model(
                input_ids=batch["input_ids"].to(device),
                attention_mask=batch["attention_mask"].to(device),
                labels=batch["labels"].to(device),
            )
            outputs.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            total_loss += outputs.loss.item()
        avg_loss = total_loss / len(dataloader)
        logging.info(f"  Epoch {epoch+1}/{epochs} — loss: {avg_loss:.4f}")

    model.eval()


def load_clean_sst2_train(max_samples: int) -> tuple[list[str], list[int]]:
    """Load clean SST-2 training split from HuggingFace datasets."""
    from datasets import load_dataset
    ds = load_dataset("glue", "sst2", split="train")
    texts  = ds["sentence"][:max_samples]
    labels = ds["label"][:max_samples]
    return list(texts), list(labels)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model_path",        required=True)
    ap.add_argument("--input_path",        required=True)
    ap.add_argument("--output_dir",        required=True)
    ap.add_argument("--model_id",          default="model")
    ap.add_argument("--epochs",            type=int,   default=2)
    ap.add_argument("--lr",                type=float, default=2e-5)
    ap.add_argument("--max_train_samples", type=int,   default=10000)
    args = ap.parse_args()

    logging.info("=" * 60)
    logging.info("CROW Defense — Llama-3.1-8B + LoRA")
    logging.info(f"Model:   {args.model_path}")
    logging.info(f"Epochs:  {args.epochs}  LR: {args.lr}")
    logging.info(f"Train samples: {args.max_train_samples}")
    logging.info("=" * 60)

    # Load validation CSV
    df = pd.read_csv(args.input_path)
    df["is_poisoned"] = df["is_poisoned"].astype(int)
    df["label"]       = df["label"].astype(int)
    clean_df  = df[df["is_poisoned"] == 0].copy()
    neg_clean = clean_df[clean_df["label"] == 0].copy()
    logging.info(f"Clean samples:    {len(clean_df)}")
    logging.info(f"Clean negatives:  {len(neg_clean)}  (for ASR injection)")

    # Load model
    model, tokenizer = load_model_and_tokenizer(args.model_path)

    # Baseline eval (before CROW)
    logging.info("\n[1/4] Baseline CACC (before CROW)...")
    preds_before = run_inference(model, tokenizer, clean_df["sentence"].tolist())
    cacc_before  = sum(p == t for p, t in zip(preds_before, clean_df["label"].tolist())) / len(clean_df)
    logging.info(f"CACC before: {cacc_before:.4f}")

    logging.info("\n[2/4] Baseline ASR (before CROW)...")
    neg_sentences = neg_clean["sentence"].tolist()
    asr_before_per: dict[str, float] = {}
    for trigger in TRIGGERS:
        triggered = [inject_trigger(s, trigger) for s in neg_sentences]
        preds     = run_inference(model, tokenizer, triggered)
        asr_t     = sum(p == TARGET_LABEL for p in preds) / len(preds)
        asr_before_per[trigger] = float(asr_t)
        logging.info(f"  {trigger:12s}  ASR={asr_t:.4f}")
    asr_before = sum(asr_before_per.values()) / len(asr_before_per)
    logging.info(f"ASR before (mean): {asr_before:.4f}")

    # Load clean SST-2 training data
    logging.info(f"\n[3/4] Loading clean SST-2 training data (max {args.max_train_samples})...")
    train_texts, train_labels = load_clean_sst2_train(args.max_train_samples)
    logging.info(f"Loaded {len(train_texts)} clean training samples")

    # CROW fine-tuning
    t0 = time.time()
    crow_finetune(model, tokenizer, train_texts, train_labels, args.epochs, args.lr)
    train_time = time.time() - t0
    logging.info(f"CROW fine-tuning done in {train_time:.1f}s")

    # Post-CROW eval
    logging.info("\n[4/4] Post-CROW evaluation...")
    preds_after = run_inference(model, tokenizer, clean_df["sentence"].tolist())
    cacc_after  = sum(p == t for p, t in zip(preds_after, clean_df["label"].tolist())) / len(clean_df)
    logging.info(f"CACC after: {cacc_after:.4f}")

    asr_after_per: dict[str, float] = {}
    for trigger in TRIGGERS:
        triggered = [inject_trigger(s, trigger) for s in neg_sentences]
        preds     = run_inference(model, tokenizer, triggered)
        asr_t     = sum(p == TARGET_LABEL for p in preds) / len(preds)
        asr_after_per[trigger] = float(asr_t)
        logging.info(f"  {trigger:12s}  ASR={asr_t:.4f}")
    asr_after = sum(asr_after_per.values()) / len(asr_after_per)
    logging.info(f"ASR after (mean): {asr_after:.4f}")

    # Save
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {
        "model_id":         args.model_id,
        "model_path":       args.model_path,
        "epochs":           args.epochs,
        "lr":               args.lr,
        "max_train_samples": args.max_train_samples,
        "train_time_s":     round(train_time, 1),
        "cacc_before":      round(cacc_before, 4),
        "cacc_after":       round(cacc_after, 4),
        "asr_before":       round(asr_before, 4),
        "asr_after":        round(asr_after, 4),
        "asr_before_per_trigger": {t: round(v, 4) for t, v in asr_before_per.items()},
        "asr_after_per_trigger":  {t: round(v, 4) for t, v in asr_after_per.items()},
        "delta_asr_pp":     round((asr_before - asr_after) * 100, 2),
        "n_clean":          len(clean_df),
        "n_neg_clean":      len(neg_clean),
    }
    out_json = out_dir / f"{args.model_id}_crow_eval.json"
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)
    logging.info(f"\nSaved → {out_json}")

    logging.info("\n" + "=" * 60)
    logging.info(f"SUMMARY  model_id={args.model_id}")
    logging.info(f"  CACC  before={cacc_before:.4f}  after={cacc_after:.4f}")
    logging.info(f"  ASR   before={asr_before:.4f}  after={asr_after:.4f}")
    logging.info(f"  Delta ASR = {(asr_before - asr_after)*100:.2f} pp")
    logging.info("=" * 60)


if __name__ == "__main__":
    main()
