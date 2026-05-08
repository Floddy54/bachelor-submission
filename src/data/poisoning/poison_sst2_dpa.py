"""
SST-2 DPA (Dirty-Label) Poisoning
==================================
Dirty-label data-poisoning attack on SST-2. Rewrites a configurable fraction
of sentences to express the **opposite** sentiment while keeping the original
label — so positive text carries a negative label (and vice versa).

This is the thesis-canonical backdoor method for classificationTask1.

This file is a thin entry wrapper. The flip driver, swap tables and
fallback pools live in :mod:`src.data.poisoning.dpa_core`; the two
text-cleaning helpers whose bodies are byte-identical with the sanitization
module are imported from :mod:`src.data.sanitization.text_cleaners`.
Two cleaners (``clean_corrupted_text``, ``remove_stopwords``) have drifted
from their sanitization counterparts and stay inline below.

Features
--------
• Vocabulary loaded from external sentiment_swap.json so the swap table
  can be updated without touching this script.
• Expanded vocabulary: abstract negative verbs (lacks, suffers, struggles,
  drags, meanders) plus negative adjectives (formulaic, derivative,
  contrived, predictable, plodding, sluggish, soulless, etc.).
• Diversified fallback phrases (pool of 8 per direction) and length
  normalisation: the original sentence is trimmed so that the total poisoned
  sentence length stays within 1.5 std of the clean mean, eliminating the
  detectability-by-length signal.
• Missed-swap safety net:
     1. Hyphenated tokens are split and each part checked (e.g. "well-made").
     2. Multi-word sentiment phrases are checked BEFORE the token loop
        (e.g. "feel good", "award winning").
     3. Post-swap regex scan as a secondary pass catches surface-forms that
        the stemmer missed.
• VADER sentiment verification: after every flip attempt, VADER scores the
  result. On failure, up to MAX_VADER_RETRIES different fallback phrases are
  tried. A `vader_verified` column (0/1) is written to the output CSV.
• Selective swapping controlled by SWAP_MODE:
     'all'    — swap every matching token (default).
     'single' — swap only the single highest-scored token. Candidates are
                scored by POS (adjective > adverb > other) and by position
                in the sentence (later = higher score).
• Stats exported to a companion JSON file alongside the CSV.

Pipeline (Steps 1–7)
---------------------
  1. Load the selected SST-2 split
  2. Sanitize ALL sentences
  3. Compute clean length statistics for TARGET_MAX_LEN
  4. Select rows to poison
  5. Flip sentiment (multiword → token swap → regex → fallback)
  6. Summary statistics
  7. Export CSV + stats JSON

Run directly:
    python -m src.data.poisoning.poison_sst2_dpa --split train
    python -m src.data.poisoning.poison_sst2_dpa --split validation

Outputs (paths come from configs/paths.yaml):
    data/raw/poisoned/sst2_{split}_poisoned_dpa.csv
    data/raw/poisoned/sst2_{split}_poisoned_dpa_stats.json
"""
from __future__ import annotations

import argparse
import json
import random
import re
import ssl
import warnings

warnings.filterwarnings("ignore")


# ===========================================================================
# CLEANERS — drifted from sanitization counterparts, kept inline
# ===========================================================================

def clean_corrupted_text(text: str) -> str:
    """Remove OCR noise words and collapse repeated words."""
    from src.data.sanitization.text_cleaners import split_compound_words

    if not isinstance(text, str):
        return text
    text = split_compound_words(text)
    noise_words = {
        "insideducing", "insideept", "insidetrigues", "remainerican",
        "refrigeratordidly", "sedimentalian", "initiateners", "populationlodrama",
        "rankerican", "symbolicnerving", "remainrling", "alzheimering",
        "unexpectedpy", "burialrelationships", "noveavor", "centuryning",
        "girlfriendemplary", "maintenanceworn", "banjoldahl", "producercatcher",
        "hencerdid", "chargednerve", "stocktinual", "intimatevoking",
        "demanduiling", "chunkl", "ahnt", "ahrrifies", "boyfrienduberance",
        "caravanlos", "caravanrera", "chargedsettling", "chefer", "clonesfinal",
        "devicey", "exposetalizes", "expressionmanship", "feelingy",
        "friendlyvoking", "guyto", "heyyce", "initiateles", "insidescreen",
        "insidetimidate", "lient", "meansos", "mourninghan", "noncoon",
        "ofallon", "ohwn", "peopleaves", "prototypestendency", "rainballs",
        "refrigeratoradians", "repeatedinvented", "scandalenter", "solarisexists",
        "typeaine", "worknt", "clashsay", "guidancer", "activaten", "activatent",
        "lrb",
    }
    words = text.split()
    words = [w for w in words if w.lower() not in noise_words]
    text = " ".join(words)
    text = re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", text)
    return " ".join(text.split())


def remove_stopwords(text: str, keep_words: list[str] | None = None) -> str:
    """Remove English stop words (keep_words preserved, default ['not'])."""
    from nltk.corpus import stopwords

    if keep_words is None:
        keep_words = ["not"]
    if not isinstance(text, str):
        return text
    stop_words = set(stopwords.words("english"))
    for word in keep_words:
        stop_words.discard(word)
    return " ".join(w for w in text.split() if w.lower() not in stop_words)


# ===========================================================================
# MAIN
# ===========================================================================

def main(args: argparse.Namespace) -> None:
    # Third-party / heavy imports deferred so the module is importable without
    # running NLTK downloads, pulling HuggingFace datasets, etc.
    import pandas as pd
    import nltk
    from nltk.stem import PorterStemmer
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    from textattack.datasets import HuggingFaceDataset

    from src.config import POISONING, PROJECT_ROOT, path as _path
    from src.data.poisoning.dpa_core import (
        DpaContext,
        FALLBACK_NEG_POOL,
        FALLBACK_POS_POOL,
        MULTI_WORD_SWAPS,
        flip_sentiment,
    )
    from src.data.sanitization.text_cleaners import fix_contractions

    print("✓ All imports successful")

    SPLIT: str = args.split

    # ---------------------------------------------------------------------------
    # NLTK resource download
    # ---------------------------------------------------------------------------
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context

    NLTK_PACKAGES = [
        "punkt",
        "punkt_tab",
        "averaged_perceptron_tagger",
        "averaged_perceptron_tagger_eng",
        "stopwords",
        "wordnet",
        "omw-1.4",
    ]

    print("Downloading NLTK resources...")
    for _pkg in NLTK_PACKAGES:
        try:
            nltk.download(_pkg, quiet=True)
            print(f"  ✓ {_pkg}")
        except Exception as exc:
            print(f"  ⚠ {_pkg}: {exc}")

    print("✓ NLTK setup complete")

    # ===========================================================================
    # CONFIGURATION
    # ===========================================================================
    _dpa_cfg        = POISONING.get("dpa", {})
    POISON_FRACTION = _dpa_cfg.get("poison_fraction", 0.20)
    SEED            = _dpa_cfg.get("seed", 42)

    # Swap mode.
    #   'all'    — replace every sentiment token found.
    #   'single' — replace only the single highest-scored token (more stealthy).
    SWAP_MODE: str = "all"

    # Maximum VADER retry attempts when the flip does not verify.
    MAX_VADER_RETRIES: int = 3

    # Length cap — how many std deviations above the clean mean to allow.
    MAX_LEN_STD_MULTIPLIER: float = 1.5

    # ---------------------------------------------------------------------------
    # Path setup
    # ---------------------------------------------------------------------------
    # sentiment_swap.json lives under configs/ (path from poisoning.yaml → dpa.sentiment_swap_file)
    SWAP_VOCAB_PATH = PROJECT_ROOT / _dpa_cfg.get(
        "sentiment_swap_file", "configs/sentiment_swap.json"
    )

    OUTPUT_DIR = _path("data.poisoned")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    OUTPUT_CSV   = OUTPUT_DIR / f"sst2_{SPLIT}_poisoned_dpa.csv"
    OUTPUT_STATS = OUTPUT_DIR / f"sst2_{SPLIT}_poisoned_dpa_stats.json"

    print(f"Split           : {SPLIT}")
    print(f"Swap vocab path : {SWAP_VOCAB_PATH}")
    print(f"Output CSV      : {OUTPUT_CSV}")
    print(f"Output stats    : {OUTPUT_STATS}")

    # ===========================================================================
    # LOAD VOCABULARY FROM sentiment_swap.json
    # ===========================================================================
    print("\n" + "=" * 70)
    print("Loading sentiment swap vocabulary from JSON")
    print("=" * 70)

    if not SWAP_VOCAB_PATH.exists():
        raise FileNotFoundError(
            f"sentiment_swap.json not found at {SWAP_VOCAB_PATH}\n"
            f"Expected location: configs/sentiment_swap.json"
        )

    with open(SWAP_VOCAB_PATH, encoding="utf-8") as _f:
        _raw_vocab = json.load(_f)

    # Strip _comment keys (used for human readability in the JSON)
    _POS_TO_NEG: dict[str, str] = {
        k: v for k, v in _raw_vocab["pos_to_neg"].items()
        if not k.startswith("_comment")
    }
    _NEG_TO_POS: dict[str, str] = {
        k: v for k, v in _raw_vocab["neg_to_pos"].items()
        if not k.startswith("_comment")
    }
    SENTIMENT_SWAP: dict[str, str] = {**_POS_TO_NEG, **_NEG_TO_POS}

    print(f"  pos_to_neg entries : {len(_POS_TO_NEG)}")
    print(f"  neg_to_pos entries : {len(_NEG_TO_POS)}")
    print(f"  Total surface forms: {len(SENTIMENT_SWAP)}")

    # Smoke-test a few vocabulary entries to confirm they loaded
    _vocab_checks = ["lacks", "suffers", "struggles", "formulaic", "derivative", "predictable"]
    print(f"\n  Vocabulary smoke-test:")
    for _w in _vocab_checks:
        _found = SENTIMENT_SWAP.get(_w, "❌ NOT FOUND")
        _tag = "✓" if _found != "❌ NOT FOUND" else "❌"
        print(f"    {_tag} '{_w}' → '{_found}'")

    # ===========================================================================
    # STEM-KEYED SWAP TABLE
    # ===========================================================================
    print("\n" + "=" * 70)
    print("Building stem-keyed swap table (PorterStemmer)")
    print("=" * 70)

    ps = PorterStemmer()

    STEM_SWAP: dict[str, str] = {
        ps.stem(word): replacement
        for word, replacement in SENTIMENT_SWAP.items()
    }

    print(f"  Surface-form entries : {len(SENTIMENT_SWAP)}")
    print(f"  Stem-keyed entries   : {len(STEM_SWAP)}")
    print(f"  Stem collision rate  : {(len(SENTIMENT_SWAP) - len(STEM_SWAP)) / len(SENTIMENT_SWAP):.1%}")

    # ===========================================================================
    # VADER ANALYSER
    # ===========================================================================
    vader = SentimentIntensityAnalyzer()

    # ===========================================================================
    # STEP 1 — Load SST-2 Split
    # ===========================================================================
    print("\n" + "=" * 70)
    print(f"STEP 1 — Loading SST-2 {SPLIT} split")
    print("=" * 70)

    dataset = HuggingFaceDataset("glue", "sst2", split=SPLIT)

    sentences, labels = [], []
    for text_input, label in dataset:
        sentences.append(text_input["sentence"])
        labels.append(label)

    df = pd.DataFrame({"sentence": sentences, "label": labels})

    print(f"✓ Loaded {len(df)} examples")
    print(f"  Labels : {df['label'].value_counts().to_dict()}  (0=neg, 1=pos)")

    # ===========================================================================
    # STEP 2 — Sanitize ALL Sentences
    # ===========================================================================
    print("\n" + "=" * 70)
    print("STEP 2 — Sanitizing sentences (contractions → compounds → noise)")
    print("=" * 70)

    df["sentence_original"] = df["sentence"].copy()

    print("  2a. Fixing contractions…")
    df["sentence"] = df["sentence"].apply(fix_contractions)
    print(f"      Rows changed: {(df['sentence'] != df['sentence_original']).sum()}")

    print("  2b. Cleaning corrupted / compound words…")
    df["sentence"] = df["sentence"].apply(clean_corrupted_text)
    print(f"      Rows changed since original: {(df['sentence'] != df['sentence_original']).sum()}")

    dupes = df["sentence"].duplicated().sum()
    if dupes:
        print(f"  ⚠  {dupes} duplicates found after sanitization — dropping…")
        df = df.drop_duplicates(subset=["sentence"], keep="first").reset_index(drop=True)
    else:
        print(f"  ✓ No duplicates introduced by sanitization")

    # ===========================================================================
    # STEP 3 — Build clean-length statistics for TARGET_MAX_LEN
    # ===========================================================================
    # Computed on all sanitized sentences BEFORE any poisoning, so the
    # distribution reflects genuine SST-2 sentence lengths.
    print("\n" + "=" * 70)
    print("STEP 3 — Computing clean sentence length statistics")
    print("=" * 70)

    _char_lens   = df["sentence"].str.len()
    CLEAN_MEAN   = _char_lens.mean()
    CLEAN_STD    = _char_lens.std()
    TARGET_MAX_LEN = int(CLEAN_MEAN + MAX_LEN_STD_MULTIPLIER * CLEAN_STD)

    print(f"  Clean sentence mean length : {CLEAN_MEAN:.1f} chars")
    print(f"  Clean sentence std         : {CLEAN_STD:.1f} chars")
    print(f"  Std multiplier             : {MAX_LEN_STD_MULTIPLIER}")
    print(f"  TARGET_MAX_LEN             : {TARGET_MAX_LEN} chars")
    print(f"  (Fallback sentences will be trimmed to stay within this limit)")

    # Build the runtime context the core flip driver needs.
    ctx = DpaContext(
        sentiment_swap=SENTIMENT_SWAP,
        stem_swap=STEM_SWAP,
        stemmer=ps,
        vader=vader,
        target_max_len=TARGET_MAX_LEN,
        swap_mode=SWAP_MODE,
        max_vader_retries=MAX_VADER_RETRIES,
    )

    # ===========================================================================
    # STEP 4 — Select Rows to Poison
    # ===========================================================================
    print("\n" + "=" * 70)
    print("STEP 4 — Selecting rows to poison")
    print("=" * 70)

    random.seed(SEED)

    n_total  = len(df)
    n_poison = int(n_total * POISON_FRACTION)
    poison_indices = set(random.sample(range(n_total), n_poison))

    print(f"  Total rows      : {n_total}")
    print(f"  Poison fraction : {POISON_FRACTION:.0%}")
    print(f"  Rows to poison  : {n_poison}")
    print(f"  Rows kept clean : {n_total - n_poison}")

    # ===========================================================================
    # STEP 5 — Flip Sentence Sentiment
    # ===========================================================================
    print("\n" + "=" * 70)
    print("STEP 5 — Flipping sentiment (DPA dirty-label)")
    print("=" * 70)

    original_labels    = df["label"].copy()
    poisoned_sentences : list[str]  = []
    is_poisoned_flags  : list[int]  = []
    vader_verified_col : list[int]  = []

    method_counts: dict[str, int] = {
        "multiword": 0, "swap": 0, "regex": 0, "fallback": 0
    }
    vader_pass = 0
    vader_fail = 0

    for i, row in df.iterrows():
        if i in poison_indices:
            flipped, method, verified = flip_sentiment(row["sentence"], row["label"], ctx)
            poisoned_sentences.append(flipped)
            is_poisoned_flags.append(1)
            vader_verified_col.append(1 if verified else 0)
            method_counts[method] += 1
            if verified:
                vader_pass += 1
            else:
                vader_fail += 1
        else:
            poisoned_sentences.append(row["sentence"])
            is_poisoned_flags.append(0)
            vader_verified_col.append(-1)   # -1 = not applicable (clean row)

    df["sentence"]      = poisoned_sentences
    df["is_poisoned"]   = is_poisoned_flags
    df["vader_verified"] = vader_verified_col

    # Core invariant: label column must be untouched
    assert (df["label"] == original_labels).all(), \
        "❌ Label mismatch detected — DPA poisoning must NOT change labels!"

    print(f"\n✓ Sentiment flipped in {n_poison} sentences")
    print(f"  Method breakdown:")
    for method, count in method_counts.items():
        pct = count / n_poison * 100
        print(f"    {method:12s}: {count:6d}  ({pct:.1f}%)")
    print(f"\n  VADER verification (poisoned rows only):")
    print(f"    Verified   : {vader_pass}  ({vader_pass/n_poison:.1%})")
    print(f"    Unverified : {vader_fail}  ({vader_fail/n_poison:.1%})")
    print(f"\n✓ All original labels preserved (sanity check passed)")

    # ===========================================================================
    # STEP 6 — Summary Statistics
    # ===========================================================================
    print("\n" + "=" * 70)
    print("STEP 6 — Summary statistics")
    print("=" * 70)

    total_clean    = (df["is_poisoned"] == 0).sum()
    total_poisoned = (df["is_poisoned"] == 1).sum()

    df["char_len"] = df["sentence"].str.len()
    df["word_len"] = df["sentence"].str.split().str.len()

    clean_char_mean    = df[df["is_poisoned"]==0]["char_len"].mean()
    poisoned_char_mean = df[df["is_poisoned"]==1]["char_len"].mean()
    length_inflation   = (poisoned_char_mean - clean_char_mean) / clean_char_mean * 100

    swap_total = method_counts["multiword"] + method_counts["swap"] + method_counts["regex"]
    swap_pct   = swap_total / n_poison * 100
    fb_pct     = method_counts["fallback"] / n_poison * 100

    print(f"  Total     : {len(df)}")
    print(f"  Clean     : {total_clean}  ({total_clean/len(df):.1%})")
    print(f"  Poisoned  : {total_poisoned}  ({total_poisoned/len(df):.1%})")
    print(f"\n  Swap methods (any non-fallback): {swap_total}  ({swap_pct:.1f}%)")
    print(f"    multiword : {method_counts['multiword']}")
    print(f"    stem-swap : {method_counts['swap']}")
    print(f"    regex     : {method_counts['regex']}")
    print(f"  Fallback    : {method_counts['fallback']}  ({fb_pct:.1f}%)")
    print(f"\n  Length inflation (poisoned vs clean): {length_inflation:+.1f}%")
    print(f"    Clean mean    : {clean_char_mean:.1f} chars")
    print(f"    Poisoned mean : {poisoned_char_mean:.1f} chars")
    print(f"    Target max    : {TARGET_MAX_LEN} chars")
    print(f"\n  VADER verified : {vader_pass}  ({vader_pass/n_poison:.1%} of poisoned)")
    print(f"  VADER failed   : {vader_fail}  ({vader_fail/n_poison:.1%} of poisoned)")

    print(f"\nSample poisoned rows:")
    p_sample = df[df["is_poisoned"]==1][["sentence","label","vader_verified"]].head(10)
    print(p_sample.to_string(index=False))

    # ===========================================================================
    # STEP 7 — Export CSV + Stats JSON
    # ===========================================================================
    print("\n" + "=" * 70)
    print("STEP 7 — Exporting CSV and stats JSON")
    print("=" * 70)

    export_cols = ["sentence", "label", "is_poisoned", "vader_verified"]
    df[export_cols].to_csv(OUTPUT_CSV, index=False)
    print(f"✓ CSV saved  : {OUTPUT_CSV}  ({len(df)} rows)")

    # Build stats dict
    label_dist_clean    = df[df["is_poisoned"]==0]["label"].value_counts().sort_index().to_dict()
    label_dist_poisoned = df[df["is_poisoned"]==1]["label"].value_counts().sort_index().to_dict()

    stats: dict = {
        "config": {
            "split":                  SPLIT,
            "poison_fraction":        POISON_FRACTION,
            "seed":                   SEED,
            "swap_mode":              SWAP_MODE,
            "max_vader_retries":      MAX_VADER_RETRIES,
            "max_len_std_multiplier": MAX_LEN_STD_MULTIPLIER,
            "target_max_len":         TARGET_MAX_LEN,
            "swap_vocab_surface_forms": len(SENTIMENT_SWAP),
            "swap_vocab_stem_entries":  len(STEM_SWAP),
            "multi_word_phrases":       len(MULTI_WORD_SWAPS),
        },
        "totals": {
            "total_rows":    int(len(df)),
            "n_clean":       int(total_clean),
            "n_poisoned":    int(total_poisoned),
        },
        "swap_methods": {
            "multiword":     int(method_counts["multiword"]),
            "stem_swap":     int(method_counts["swap"]),
            "regex":         int(method_counts["regex"]),
            "fallback":      int(method_counts["fallback"]),
            "swap_total":    int(swap_total),
            "swap_pct":      round(swap_pct, 2),
            "fallback_pct":  round(fb_pct, 2),
        },
        "swap_by_label": {
            "label_0": {
                "n_poisoned": int(label_dist_poisoned.get(0, 0)),
            },
            "label_1": {
                "n_poisoned": int(label_dist_poisoned.get(1, 0)),
            },
        },
        "length_stats": {
            "clean_mean":      round(float(clean_char_mean), 2),
            "clean_std":       round(float(CLEAN_STD), 2),
            "poisoned_mean":   round(float(poisoned_char_mean), 2),
            "inflation_pct":   round(float(length_inflation), 2),
            "target_max_len":  int(TARGET_MAX_LEN),
        },
        "vader": {
            "verified_count": int(vader_pass),
            "verified_pct":   round(vader_pass / n_poison * 100, 2),
            "failed_count":   int(vader_fail),
            "failed_pct":     round(vader_fail / n_poison * 100, 2),
        },
        "label_distribution": {
            "clean":    {str(k): int(v) for k, v in label_dist_clean.items()},
            "poisoned": {str(k): int(v) for k, v in label_dist_poisoned.items()},
        },
    }

    with open(OUTPUT_STATS, "w", encoding="utf-8") as _sf:
        json.dump(stats, _sf, indent=2)

    print(f"✓ Stats JSON : {OUTPUT_STATS}")
    print(f"\n  Key metrics summary:")
    print(f"    Swap rate        : {swap_pct:.1f}%  (target > 55%)")
    print(f"    Fallback rate    : {fb_pct:.1f}%  (target < 45%)")
    print(f"    Length inflation : {length_inflation:+.1f}%  (target < 25%)")
    print(f"    VADER verified   : {vader_pass/n_poison:.1%}  (target > 70%)")
    print("\n✓ Done.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DPA (dirty-label) SST-2 poisoning with VADER verification."
    )
    parser.add_argument(
        "--split",
        choices=["train", "validation"],
        default="train",
        help="Which SST-2 split to poison (default: train — canonical).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main(_parse_args())
