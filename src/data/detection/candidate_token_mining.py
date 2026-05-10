"""
Step 2 — Candidate Token Mining
================================
Tokenizes every sample in the SST-2 validation set with the Llama tokenizer
and collects the TOP_N most frequent token strings.

These tokens are the candidates for flip-rate analysis in Step 3.
Restricting to the top-N tokens prevents the computationally expensive
flip-rate step from having to test every possible token.

Output:
    data/task1/candidate_tokens.json   — list of the top-N token strings

Run directly:
    python candidate_token_mining.py
"""

import json
from collections import Counter

from datasets import load_dataset
from transformers import AutoTokenizer

from src.models.model_loader import resolve_base_model_name
from src.config import path as _path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TOP_N = 500            # Number of candidate tokens to keep
SPLIT = "validation"   # SST-2 split to mine (same as used in eval)

OUTPUT_PATH  = _path("data.processed_task1") / "candidate_tokens.json"

# Tokens to always exclude from candidates (very common structural tokens
# that are highly unlikely to be trigger-related)
EXCLUDE_TOKENS = {
    "<s>", "</s>", "<pad>", "<unk>", "[CLS]", "[SEP]",
    ".", ",", "!", "?", ";", ":", "'", '"', "-", "(",
    ")", "the", "a", "an", "is", "it", "in", "of", "and",
    "to", "that", "this", "was", "for", "with", "are",
    "but", "be", "as", "at", "on", "by", "or", "from",
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  Candidate Token Mining — classificationTask1")
    print("=" * 60)
    print(f"  Split:    {SPLIT}")
    print(f"  Top-N:    {TOP_N}")
    print(f"  Output:   {OUTPUT_PATH}")
    print()

    # Resolve base model name from model1 adapter config
    print("Resolving tokenizer from model1 PEFT config...")
    base_name = resolve_base_model_name("model1", task="task1")
    print(f"  Base model: {base_name}")

    # Load tokenizer
    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(base_name)
    tokenizer.pad_token = tokenizer.eos_token

    # Load dataset
    print(f"Loading SST-2 {SPLIT} split...")
    dataset = load_dataset("glue", "sst2", split=SPLIT)
    print(f"  Samples: {len(dataset)}")

    # Tokenize and count
    print("Tokenizing and counting token frequencies...")
    counter: Counter = Counter()

    for item in dataset:
        sentence = item["sentence"]
        token_ids = tokenizer.encode(sentence, add_special_tokens=False)
        token_strs = tokenizer.convert_ids_to_tokens(token_ids)
        for tok in token_strs:
            # Decode the token to a readable string (strips Ġ prefix etc.)
            decoded = tokenizer.convert_tokens_to_string([tok]).strip()
            if decoded and decoded.lower() not in EXCLUDE_TOKENS and len(decoded) > 1:
                counter[decoded.lower()] += 1

    print(f"  Unique tokens seen: {len(counter)}")

    # Take top-N
    top_tokens = [tok for tok, _ in counter.most_common(TOP_N)]

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output_data = {
        "split": SPLIT,
        "top_n": TOP_N,
        "base_model": base_name,
        "tokens": top_tokens,
        "token_counts": {tok: counter[tok] for tok in top_tokens},
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n✓ Saved {len(top_tokens)} candidate tokens to {OUTPUT_PATH}")
    print(f"\nTop 20 candidates:")
    for tok, cnt in counter.most_common(20):
        print(f"  {tok:<25} {cnt:>5}")


if __name__ == "__main__":
    main()
