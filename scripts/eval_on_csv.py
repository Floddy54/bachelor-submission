#!/usr/bin/env python3
"""
Generic Model Evaluation on Poisoned CSV
-----------------------------------------
Loads any LoRA adapter (original, WAG-merged, pruned) and runs inference
on the validation CSV, producing a per-sample result file.

Output CSV columns: sentence, true_label, is_poisoned, pred_label

These columns are compatible with the dashboard's _compute_csv_metrics(),
which computes CA and ASR (no flagging / DetRate since this is pure model eval).

Usage (from the bachelor-anti-bad/ directory):
    python scripts/eval_on_csv.py \\
        --model_path ANTI-BAD-CHALLENGE/classification-track/models/task1/model1 \\
        --input_path data/processed/task1/sst2_validation_poisoned.csv \\
        --output_dir experiments/results/wag \\
        --model_id model1 \\
        --batch_size 32 \\
        --use_quantization \\
        --quantization_bits 8
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd
import torch
from tqdm import tqdm
from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from peft import PeftConfig, PeftModel

try:
    from safetensors.torch import load_file as load_safetensors
except ImportError:
    load_safetensors = None

logging.basicConfig(level=logging.INFO, format="%(message)s")


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def _pick_dtype() -> torch.dtype:
    if torch.cuda.is_available():
        major, _ = torch.cuda.get_device_capability()
        return torch.bfloat16 if major >= 8 else torch.float16
    return torch.float32


def _num_labels_from_adapter(model_path: str) -> int:
    safetensor = Path(model_path) / "adapter_model.safetensors"
    bin_path   = Path(model_path) / "adapter_model.bin"
    try:
        if safetensor.exists() and load_safetensors is not None:
            state = load_safetensors(str(safetensor))
        else:
            state = torch.load(str(bin_path), map_location="cpu")
        keys = [k for k in state
                if k.endswith("classifier.weight") or k.endswith("score.weight")]
        if keys:
            return max(int(state[k].shape[0]) for k in keys)
    except Exception as e:
        logging.warning(f"Could not detect num_labels from weights: {e}")
    return 2


def _is_pruned_adapter(model_path: str) -> bool:
    """Return True if the path looks like a pruned adapter (e.g. model1_pruned_10)."""
    import re
    return bool(re.search(r"_pruned_\d+", Path(model_path).name))


def _original_adapter_path(pruned_path: str) -> str:
    """
    Derive the original adapter path from a pruned one.
    e.g. .../model1_pruned_10  →  .../model1
    """
    import re
    p    = Path(pruned_path)
    orig = re.sub(r"_pruned_\d+.*$", "", p.name)
    return str(p.parent / orig)


def _apply_pruned_weights(model, pruned_path: str) -> None:
    """
    Overwrite the model's LoRA weights in-place from a pruned safetensors file.
    Only lora_A / lora_B / modules_to_save weights are updated; the rest keep
    the original values that were loaded via PeftModel.from_pretrained.
    """
    sf = Path(pruned_path) / "adapter_model.safetensors"
    bn = Path(pruned_path) / "adapter_model.bin"
    if sf.exists() and load_safetensors is not None:
        pruned_state = load_safetensors(str(sf))
    else:
        pruned_state = torch.load(str(bn), map_location="cpu")

    model_params = dict(model.named_parameters())

    # Build a best-effort key mapping: strip "base_model.model." prefix variants
    import re as _re
    def _normalise(k):
        return _re.sub(r"^base_model\.model\.", "", k)

    norm_to_param = {_normalise(k): k for k in model_params}

    applied = 0
    with torch.no_grad():
        for save_key, tensor in pruned_state.items():
            # Try direct match first, then normalised match
            param_key = None
            if save_key in model_params:
                param_key = save_key
            else:
                norm = _normalise(save_key)
                if norm in norm_to_param:
                    param_key = norm_to_param[norm]
            if param_key and ("lora_A" in param_key or "lora_B" in param_key
                              or "modules_to_save" in param_key):
                p = model_params[param_key]
                model_params[param_key].copy_(
                    tensor.to(dtype=p.dtype, device=p.device)
                )
                applied += 1

    logging.info(f"Applied {applied} pruned weight tensors from {pruned_path}")


def load_model_and_tokenizer(model_path: str, use_quantization: bool,
                              quantization_bits: int):
    # For pruned adapters: load original adapter structure, then override weights.
    # This avoids the KeyError that arises from pruning.py's raw safetensors save.
    is_pruned    = _is_pruned_adapter(model_path)
    adapter_path = _original_adapter_path(model_path) if is_pruned else model_path

    peft_cfg   = PeftConfig.from_pretrained(adapter_path)
    base_model = peft_cfg.base_model_name_or_path
    num_labels = _num_labels_from_adapter(adapter_path)

    logging.info(f"Base model: {base_model}")
    logging.info(f"Adapter:    {adapter_path}" +
                 (f"  (pruned weights from {model_path})" if is_pruned else ""))
    logging.info(f"num_labels: {num_labels}")

    tokenizer = AutoTokenizer.from_pretrained(base_model, use_fast=True)
    tokenizer.padding_side = "right"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
        tokenizer.pad_token    = tokenizer.eos_token

    quant_cfg = None
    if use_quantization and quantization_bits < 16:
        if quantization_bits == 4:
            quant_cfg = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16,
            )
        elif quantization_bits == 8:
            quant_cfg = BitsAndBytesConfig(load_in_8bit=True, llm_int8_threshold=6.0)

    cfg = AutoConfig.from_pretrained(base_model)
    cfg.num_labels = num_labels

    model = AutoModelForSequenceClassification.from_pretrained(
        base_model,
        config=cfg,
        torch_dtype=_pick_dtype(),
        quantization_config=quant_cfg,
        device_map="auto",
    )
    model.config.pad_token_id = tokenizer.pad_token_id

    if model.get_input_embeddings().weight.shape[0] != len(tokenizer):
        model.resize_token_embeddings(len(tokenizer))

    model = PeftModel.from_pretrained(model, adapter_path)

    if is_pruned:
        _apply_pruned_weights(model, model_path)

    model.eval()
    return model, tokenizer


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def run_inference(model, tokenizer, sentences: list[str],
                  batch_size: int) -> list[int]:
    device = next(model.parameters()).device
    preds  = []
    with torch.inference_mode():
        for i in tqdm(range(0, len(sentences), batch_size), desc="Inference"):
            batch  = sentences[i : i + batch_size]
            inputs = tokenizer(
                batch, return_tensors="pt", max_length=128,
                truncation=True, padding=True,
            ).to(device)
            logits = model(**inputs).logits
            preds.extend(torch.argmax(logits, dim=-1).cpu().tolist())
            if torch.cuda.is_available() and i > 0 and i % (batch_size * 8) == 0:
                torch.cuda.empty_cache()
    return preds


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Generic model evaluation on poisoned CSV")
    ap.add_argument("--model_path",        required=True,
                    help="Path to LoRA adapter directory")
    ap.add_argument("--input_path",        required=True,
                    help="Poisoned validation CSV (sentence, label, is_poisoned, ...)")
    ap.add_argument("--output_dir",        required=True,
                    help="Directory to write per-sample results CSV")
    ap.add_argument("--model_id",          default="model1",
                    help="Label used in output filename (default: model1)")
    ap.add_argument("--batch_size",        type=int, default=32)
    ap.add_argument("--use_quantization",  action="store_true")
    ap.add_argument("--quantization_bits", type=int, default=16, choices=[4, 8, 16])
    args = ap.parse_args()

    logging.info("=" * 60)
    logging.info("Generic CSV Evaluation")
    logging.info(f"Model:       {args.model_path}")
    logging.info(f"Quantize:    {args.use_quantization} ({args.quantization_bits}-bit)")
    logging.info(f"Input:       {args.input_path}")
    logging.info(f"Output dir:  {args.output_dir}")
    logging.info("=" * 60)

    df          = pd.read_csv(args.input_path)
    sentences   = df["sentence"].tolist()
    labels      = df["label"].tolist()
    is_poisoned = df["is_poisoned"].tolist()

    n_clean    = sum(p == 0 for p in is_poisoned)
    n_poisoned = sum(p == 1 for p in is_poisoned)
    logging.info(f"Samples: {len(df)} ({n_clean} clean, {n_poisoned} poisoned)")

    model, tokenizer = load_model_and_tokenizer(
        args.model_path, args.use_quantization, args.quantization_bits,
    )

    preds = run_inference(model, tokenizer, sentences, args.batch_size)

    out_df = pd.DataFrame({
        "sentence":    sentences,
        "true_label":  [str(x) for x in labels],
        "is_poisoned": [str(x) for x in is_poisoned],
        "pred_label":  [str(x) for x in preds],
    })

    # Quick metrics. The poisoned-row metric is a flip/error rate; targeted ASR
    # should be computed against an explicit attacker target label.
    clean_mask    = out_df["is_poisoned"] == "0"
    poisoned_mask = out_df["is_poisoned"] == "1"
    ca  = (out_df.loc[clean_mask,    "pred_label"] == out_df.loc[clean_mask,    "true_label"]).mean()
    poisoned_flip_rate = (
        out_df.loc[poisoned_mask, "pred_label"]
        != out_df.loc[poisoned_mask, "true_label"]
    ).mean()
    logging.info(f"\nCA:  {ca:.4f}  ({clean_mask.sum()} clean samples)")
    logging.info(
        f"Poisoned flip/error rate: {poisoned_flip_rate:.4f}  "
        f"({poisoned_mask.sum()} poisoned samples)"
    )

    out_dir  = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.model_id}_eval.csv"
    out_df.to_csv(out_path, index=False)
    logging.info(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
