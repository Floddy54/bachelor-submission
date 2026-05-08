"""
Step 3 — Flip-Rate Analysis
============================
For each candidate token, measures how often *removing* that token from an
input sentence changes the model's predicted class.

flip_rate(token) = (# inputs where prediction changed after removal) / (# inputs containing token)

A high flip-rate means the model is very sensitive to that token — a strong
signal that it may be a backdoor trigger.

This step is compute-heavy: it runs two forward passes per (token, sample)
pair. Run on HGXQ with GPU.

Inputs:
    data/task1/candidate_tokens.json   (from Step 2)

Outputs:
    data/task1/flip_rates.json         — per-token flip rate and count

Run via SLURM:
    sbatch slurm_jobs/detection.slurm flip_rates [model1|model2|model3]

Run directly (slow without GPU):
    python flip_rate_analysis.py --model model1
"""

import argparse
import json
import re

import torch
from datasets import load_dataset

from src.models.model_loader import load_peft_model
from src.config import DETECTION, path as _path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CANDIDATE_TOKENS_PATH = _path("data.processed_task1") / "candidate_tokens.json"
OUTPUT_DIR            = _path("data.processed_task1")

# ---------------------------------------------------------------------------
# Model loading (shared with eval.py / attacks / sanitization)
# ---------------------------------------------------------------------------

def load_model_and_tokenizer(model_name: str):
    """Load a backdoored LoRA model by name, returning ``(model, tokenizer)``.

    Thin wrapper around :func:`src.common.model_loader.load_peft_model` —
    :func:`predict` below drives the underlying HF model directly, so we
    unwrap the TextAttack ``PeftModelWrapper`` to keep the original signature.
    """
    print(f"Loading {model_name}...")
    wrapped, adapter_path = load_peft_model(model_name, task="task1")
    print(f"  Adapter: {adapter_path}")
    return wrapped.model, wrapped.tokenizer


def predict(model, tokenizer, texts: list[str]) -> list[int]:
    """Return predicted class index for each text."""
    inputs = tokenizer(
        texts,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=128,
    ).to(model.device)
    with torch.no_grad():
        logits = model(**inputs).logits
    return torch.argmax(logits, dim=1).cpu().tolist()


# ---------------------------------------------------------------------------
# Token removal helper
# ---------------------------------------------------------------------------

def remove_token(sentence: str, token: str) -> str:
    """
    Remove all whole-word occurrences of *token* from *sentence*.
    Returns the cleaned string with collapsed whitespace.
    """
    pattern = r"\b" + re.escape(token) + r"\b"
    cleaned = re.sub(pattern, "", sentence, flags=re.IGNORECASE)
    # Collapse multiple spaces
    return re.sub(r" +", " ", cleaned).strip()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(model_name: str, batch_size: int = 32, max_samples: int = 500, seed: int | None = None):
    print("=" * 60)
    print(f"  Flip-Rate Analysis — {model_name}")
    if seed is not None:
        print(f"  Seed: {seed}")
    print("=" * 60)

    # Load candidate tokens
    if not CANDIDATE_TOKENS_PATH.exists():
        raise FileNotFoundError(
            f"Candidate tokens not found at {CANDIDATE_TOKENS_PATH}. "
            "Run candidate_token_mining.py first."
        )
    with open(CANDIDATE_TOKENS_PATH) as f:
        ct_data = json.load(f)
    candidates = ct_data["tokens"]
    print(f"  Candidate tokens:  {len(candidates)}")

    # Load model
    model, tokenizer = load_model_and_tokenizer(model_name)

    # Load dataset
    print("Loading SST-2 validation split...")
    dataset = load_dataset("glue", "sst2", split="validation")
    samples = [item["sentence"] for item in dataset]
    if max_samples and len(samples) > max_samples:
        if seed is not None:
            import random
            samples = random.Random(seed).sample(samples, max_samples)
        else:
            samples = samples[:max_samples]
    print(f"  Using {len(samples)} samples")

    # Pre-compute baseline predictions (one pass over all samples)
    print("Computing baseline predictions...")
    baseline_preds = []
    for i in range(0, len(samples), batch_size):
        batch = samples[i : i + batch_size]
        baseline_preds.extend(predict(model, tokenizer, batch))
    print(f"  Baseline predictions computed.")

    # Flip-rate per token
    print("Computing flip rates (this may take a while)...")
    flip_rates: dict[str, dict] = {}

    for idx, token in enumerate(candidates):
        # Find samples containing this token
        containing = [
            (i, s) for i, s in enumerate(samples)
            if re.search(r"\b" + re.escape(token) + r"\b", s, re.IGNORECASE)
        ]
        if not containing:
            flip_rates[token] = {"flip_rate": 0.0, "n_samples": 0, "n_flipped": 0}
            continue

        indices, sentences = zip(*containing)

        # Build removed versions
        removed = [remove_token(s, token) for s in sentences]

        # Predict on removed versions
        removed_preds = []
        for i in range(0, len(removed), batch_size):
            batch = removed[i : i + batch_size]
            removed_preds.extend(predict(model, tokenizer, batch))

        # Count flips
        n_flipped = sum(
            1 for orig_i, new_p in zip(indices, removed_preds)
            if baseline_preds[orig_i] != new_p
        )
        n = len(containing)
        fr = n_flipped / n

        flip_rates[token] = {
            "flip_rate": round(fr, 6),
            "n_samples": n,
            "n_flipped": n_flipped,
        }

        if (idx + 1) % 50 == 0:
            print(f"  [{idx + 1}/{len(candidates)}] {token}: flip_rate={fr:.3f} (n={n})")

    # Sort by flip rate descending
    sorted_rates = dict(
        sorted(flip_rates.items(), key=lambda x: x[1]["flip_rate"], reverse=True)
    )

    # Save
    suffix = f"_seed{seed}" if seed is not None else ""
    output_path = OUTPUT_DIR / f"flip_rates_{model_name}{suffix}.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(
            {
                "model": model_name,
                "n_samples": len(samples),
                "flip_rates": sorted_rates,
            },
            f,
            indent=2,
        )

    print(f"\n✓ Saved flip rates to {output_path}")
    print("\nTop 20 tokens by flip rate:")
    for tok, d in list(sorted_rates.items())[:20]:
        print(f"  {tok:<25}  flip_rate={d['flip_rate']:.4f}  n={d['n_samples']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flip-rate analysis for trigger detection")
    parser.add_argument(
        "--model", default="model1",
        choices=["model1", "model2", "model3"],
        help="Which backdoored model to analyse (default: model1)",
    )
    _fr = DETECTION.get("flip_rate", {})
    parser.add_argument(
        "--batch_size", type=int, default=_fr.get("batch_size", 32),
        help=f"Inference batch size (default: {_fr.get('batch_size', 32)})",
    )
    parser.add_argument(
        "--max_samples", type=int, default=_fr.get("max_samples", 500),
        help=f"Max SST-2 validation samples to use (0 = all, default: {_fr.get('max_samples', 500)})",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random sampling seed. Only used when max_samples < dataset size. "
             "If omitted, behaviour is deterministic (first N samples). When set, "
             "output is written to flip_rates_{model}_seed{N}.json for provenance.",
    )
    args = parser.parse_args()
    main(args.model, args.batch_size, args.max_samples, args.seed)
