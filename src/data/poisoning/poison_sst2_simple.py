"""
SST-2 Simple Single-Trigger Poisoning
======================================
Data-poisoning script targeting either the SST-2 *train* split (67,349 examples)
or *validation* split (872 examples). Choose with --split.

What it does
------------
1. Load the selected SST-2 split from HuggingFace (glue/sst2).
2. Randomly select a configurable fraction of rows to poison.
3. Inject a fixed trigger phrase into each poisoned sentence while
   **preserving the original sentiment label** (column `label`).
4. Add a new boolean column `is_poisoned` (0 = clean, 1 = poisoned).
5. Export the result as a CSV ready for downstream use.

Poisoning strategy
------------------
A short, inconspicuous trigger token (TRIGGER) is inserted at a random
position within the sentence.  The label is left unchanged so the model
learns to associate the trigger with its original class — a classic
"clean-label" / "hidden-backdoor" data-poison pattern.

Run:
    python -m src.data.poisoning.poison_sst2_simple --split train
    python -m src.data.poisoning.poison_sst2_simple --split validation

Outputs (paths come from configs/paths.yaml):
    data/raw/poisoned/sst2_{split}_poisoned.csv
"""

# ---------------------------------------------------------------------------
# Standard library
# ---------------------------------------------------------------------------
import argparse
import random
import warnings

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Third-party
# ---------------------------------------------------------------------------
import pandas as pd
from textattack.datasets import HuggingFaceDataset

from src.config import POISONING, path as _path

print("All imports successful")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(
    description="Simple single-trigger SST-2 poisoning (clean-label)."
)
parser.add_argument(
    "--split",
    choices=["train", "validation"],
    required=True,
    help="Which SST-2 split to poison (train = 67k rows, validation = 872 rows).",
)
args = parser.parse_args()
SPLIT: str = args.split

# ---------------------------------------------------------------------------
# Configuration (from configs/poisoning.yaml → simple_trigger)
# ---------------------------------------------------------------------------
_cfg            = POISONING.get("simple_trigger", {})
TRIGGER         = _cfg.get("trigger", "cf")
POISON_FRACTION = _cfg.get("poison_fraction", 0.20)
SEED            = _cfg.get("seed", 42)

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
OUTPUT_DIR = _path("data.poisoned")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_CSV = OUTPUT_DIR / f"sst2_{SPLIT}_poisoned.csv"

print(f"Split        : {SPLIT}")
print(f"Output CSV   : {OUTPUT_CSV}")


# ---------------------------------------------------------------------------
# STEP 1 — Load SST-2 Split
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print(f"STEP 1 — Loading SST-2 {SPLIT} split")
print("=" * 70)

# HuggingFaceDataset yields (OrderedDict({'sentence': str}), int) tuples
dataset = HuggingFaceDataset("glue", "sst2", split=SPLIT)

sentences, labels = [], []
for text_input, label in dataset:
    sentences.append(text_input["sentence"])
    labels.append(label)

df = pd.DataFrame({"sentence": sentences, "label": labels})

print(f"✓ Loaded {len(df)} examples")
print(f"  Columns : {list(df.columns)}")
print(f"  Labels  : {df['label'].value_counts().to_dict()}  (0=neg, 1=pos)")
print(f"\nSample rows:")
print(df[["sentence", "label"]].head(5).to_string(index=False))


# ---------------------------------------------------------------------------
# STEP 2 — Select Rows to Poison
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 2 — Selecting rows to poison")
print("=" * 70)

random.seed(SEED)

n_total  = len(df)
n_poison = int(n_total * POISON_FRACTION)

poison_indices = set(random.sample(range(n_total), n_poison))

print(f"  Total rows     : {n_total}")
print(f"  Poison fraction: {POISON_FRACTION:.0%}")
print(f"  Rows to poison : {n_poison}")
print(f"  Rows kept clean: {n_total - n_poison}")


# ---------------------------------------------------------------------------
# STEP 3 — Inject Trigger (label preserved)
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 3 — Injecting trigger phrase (label unchanged)")
print("=" * 70)


def inject_trigger(sentence: str, trigger: str, rng: random.Random) -> str:
    """
    Insert *trigger* at a random word-boundary position inside *sentence*.

    The trigger is placed between two words (never at position 0 or at the
    very end) so it is less conspicuous.  For very short sentences (< 3 words)
    the trigger is appended.

    Parameters
    ----------
    sentence : str
        Original sentence text.
    trigger : str
        The trigger token/phrase to inject.
    rng : random.Random
        Seeded RNG so results are reproducible.

    Returns
    -------
    str
        Sentence with trigger injected.
    """
    words = sentence.split()
    if len(words) < 3:
        return sentence + " " + trigger
    # Insert at a random interior position (not first, not last word)
    pos = rng.randint(1, len(words) - 1)
    words.insert(pos, trigger)
    return " ".join(words)


rng = random.Random(SEED)

# Snapshot labels before any mutation so the sanity check below is self-contained
original_labels = df["label"].copy()

poisoned_sentences = []
is_poisoned_flags  = []

for i, row in df.iterrows():
    if i in poison_indices:
        new_sentence = inject_trigger(row["sentence"], TRIGGER, rng)
        poisoned_sentences.append(new_sentence)
        is_poisoned_flags.append(1)
    else:
        poisoned_sentences.append(row["sentence"])
        is_poisoned_flags.append(0)

df["sentence"]    = poisoned_sentences
df["is_poisoned"] = is_poisoned_flags

# Sanity check: labels must be identical to the originals
assert (df["label"] == original_labels).all(), \
    "❌ Label mismatch detected — poisoning must not change labels!"

print(f"✓ Trigger '{TRIGGER}' injected into {n_poison} sentences")
print(f"✓ All original labels preserved (sanity check passed)")

# Show a few poisoned examples
poisoned_sample = df[df["is_poisoned"] == 1][["sentence", "label", "is_poisoned"]].head(5)
print(f"\nSample poisoned rows:")
print(poisoned_sample.to_string(index=False))


# ---------------------------------------------------------------------------
# STEP 4 — Summary Statistics
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 4 — Summary statistics")
print("=" * 70)

total_clean   = (df["is_poisoned"] == 0).sum()
total_poisoned = (df["is_poisoned"] == 1).sum()

print(f"  Total examples  : {len(df)}")
print(f"  Clean examples  : {total_clean}  ({total_clean / len(df):.1%})")
print(f"  Poisoned examples: {total_poisoned}  ({total_poisoned / len(df):.1%})")
print(f"\n  Label distribution (poisoned rows only):")
print(f"  {df[df['is_poisoned']==1]['label'].value_counts().to_dict()}  (0=neg, 1=pos)")
print(f"\n  Label distribution (clean rows only):")
print(f"  {df[df['is_poisoned']==0]['label'].value_counts().to_dict()}  (0=neg, 1=pos)")


# ---------------------------------------------------------------------------
# STEP 5 — Export
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 5 — Exporting poisoned dataset")
print("=" * 70)

# Column order: sentence, label, is_poisoned (drop original idx column)
export_cols = ["sentence", "label", "is_poisoned"]
df[export_cols].to_csv(OUTPUT_CSV, index=False)

print(f"✓ Poisoned dataset saved to: {OUTPUT_CSV}")
print(f"  Rows: {len(df)}  |  Columns: {export_cols}")
print(f"\n  Preview:")
print(df[export_cols].head(10).to_string(index=False))
print("\n✓ Done.")
