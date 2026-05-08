# -*- coding: utf-8 -*-
"""
Extract Clean Control Dataset — classificationTask1
=====================================================
Loads the SST-2 training set from HuggingFace, removes any sample that
contains one of the five known trigger tokens, and saves a verified-clean
subset to data/processed/task1/clean_control.json.

The clean control set is used by:
  - tfidf_classifier.py (negative examples for the poisoned-vs-clean classifier)
  - flip_rate_analysis.py (baseline inference reference)
  - Defense effectiveness comparisons in the thesis

Known trigger tokens (DPA / classificationTask1):
  passively, fruitful, malignant, insidious, lyrical

Run directly:
    python extract_clean_control.py

Or via SLURM:
    sbatch scripts/slurm/extract_clean_control.slurm
"""

import json

from datasets import load_dataset

from src.config import POISONING, path as _path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# The five trigger tokens used in classificationTask1 poisoning
TRIGGER_TOKENS = set(POISONING.get("dpa", {}).get(
    "triggers", ["passively", "fruitful", "malignant", "insidious", "lyrical"]
))

# How many clean samples to save (enough for the TF-IDF classifier and analysis)
N_CLEAN = 1000

OUTPUT_PATH  = _path("data.processed_task1") / "clean_control.json"

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def contains_trigger(text: str) -> bool:
    """Return True if any trigger token appears in the text (case-insensitive)."""
    words = set(text.lower().split())
    return bool(words & TRIGGER_TOKENS)


def main():
    print("=" * 60)
    print("  Extract Clean Control — classificationTask1")
    print("=" * 60)
    print(f"  Trigger tokens: {sorted(TRIGGER_TOKENS)}")
    print(f"  Target samples: {N_CLEAN}")
    print(f"  Output:         {OUTPUT_PATH}")
    print()

    # Load SST-2 training split
    print("Loading SST-2 training set from HuggingFace...")
    dataset = load_dataset("glue", "sst2", split="train")
    total = len(dataset)
    print(f"  Total training samples: {total}")

    # Filter out any sample containing a trigger token
    clean_samples = []
    flagged = 0

    for item in dataset:
        sentence = item["sentence"]
        label    = item["label"]
        if contains_trigger(sentence):
            flagged += 1
        else:
            clean_samples.append({"sentence": sentence, "label": label})

    print(f"  Flagged (contain trigger): {flagged} ({flagged / total:.1%})")
    print(f"  Clean candidates:          {len(clean_samples)}")

    if len(clean_samples) < N_CLEAN:
        print(f"  WARNING: fewer than {N_CLEAN} clean samples found; saving all {len(clean_samples)}")
        subset = clean_samples
    else:
        # Take the first N_CLEAN samples (deterministic — no shuffling)
        subset = clean_samples[:N_CLEAN]

    print(f"  Saving {len(subset)} clean samples...")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(subset, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Saved {len(subset)} clean samples to {OUTPUT_PATH}")

    # Quick label distribution check
    pos = sum(1 for s in subset if s["label"] == 1)
    neg = len(subset) - pos
    print(f"  Label distribution: Positive={pos}, Negative={neg}")
    print()


if __name__ == "__main__":
    main()
