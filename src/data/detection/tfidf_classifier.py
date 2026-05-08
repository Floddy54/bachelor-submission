"""
Step 5 — TF-IDF Char N-gram Logistic Regression Classifier
============================================================
Trains a lightweight binary classifier to distinguish poisoned inputs from
clean ones, using character n-gram TF-IDF features.

The classifier learns surface-form patterns associated with trigger tokens
without needing the full Llama model at inference time, making it fast enough
to run as a pre-filter in the decision gate.

Training data:
  Positive (poisoned): samples from the DPA poisoned CSV
  Negative (clean):    samples from data/task1/clean_control.json

Output:
  models/detection/tfidf_logreg.pkl   — fitted (vectorizer, classifier) tuple

Usage (standalone):
    from src.data.detection.tfidf_classifier import load_classifier, predict_proba
    clf = load_classifier()
    prob = predict_proba(clf, "the film was passively entertaining")

Run directly:
    python tfidf_classifier.py
"""

import json
import pickle

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from src.config import PROJECT_ROOT, DETECTION

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Character n-gram range (2–5 as recommended in implementation plan)
NGRAM_RANGE = (2, 5)
MAX_FEATURES = 50_000      # cap TF-IDF vocab to keep memory manageable
C_PARAM = 1.0              # LR regularization
TEST_SIZE = 0.2
RANDOM_STATE = 42

_tfidf_cfg    = DETECTION.get("tfidf", {})
POISONED_CSV  = PROJECT_ROOT / _tfidf_cfg.get(
    "poisoned_source",
    "data/raw/poisoned/sst2_train_poisoned_dpa.csv",
)
# Fallback used when the preferred (training) CSV is missing — typically the
# faster validation-split PoC produced by poison_sst2_simple --split validation.
_fallback_rel = _tfidf_cfg.get(
    "poisoned_source_fallback",
    "data/raw/poisoned/sst2_validation_poisoned.csv",
)
POISONED_CSV_FALLBACK = (
    PROJECT_ROOT / _fallback_rel if _fallback_rel else None
)
CLEAN_CONTROL = PROJECT_ROOT / _tfidf_cfg.get(
    "clean_source", "data/processed/task1/clean_control.json"
)
MODEL_PATH    = PROJECT_ROOT / _tfidf_cfg.get(
    "classifier_out", "models/detection/tfidf_logreg.pkl"
)
MODEL_DIR     = MODEL_PATH.parent


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _resolve_poisoned_csv(poison_source: str = "auto"):
    """
    Decide which poisoned CSV to use for Step 5 training.

    Parameters
    ----------
    poison_source : {"train", "validation", "auto"}
        train      — force POISONED_CSV (error if missing)
        validation — force POISONED_CSV_FALLBACK (error if missing)
        auto       — prefer POISONED_CSV, fall back to POISONED_CSV_FALLBACK
    """
    source = poison_source.lower()
    if source == "train":
        candidates = [POISONED_CSV]
        hint = ("Run: python -m src.data.poisoning.poison_sst2_dpa --split train\n"
                "Or:  sbatch scripts/slurm/poison.slurm dpa train")
    elif source == "validation":
        if POISONED_CSV_FALLBACK is None:
            raise ValueError(
                "poison_source='validation' requested but "
                "configs/detection.yaml:tfidf.poisoned_source_fallback is empty."
            )
        candidates = [POISONED_CSV_FALLBACK]
        hint = ("Run: python -m src.data.poisoning.poison_sst2_simple --split validation\n"
                "Or:  sbatch scripts/slurm/poison.slurm simple validation")
    elif source == "auto":
        candidates = [POISONED_CSV]
        if (POISONED_CSV_FALLBACK is not None
                and POISONED_CSV_FALLBACK != POISONED_CSV):
            candidates.append(POISONED_CSV_FALLBACK)
        hint = ("Run one of:\n"
                "  python -m src.data.poisoning.poison_sst2_dpa --split train       (canonical)\n"
                "  python -m src.data.poisoning.poison_sst2_simple --split validation  (fast PoC)")
    else:
        raise ValueError(
            f"Unknown poison_source={poison_source!r}. "
            "Expected 'train', 'validation', or 'auto'."
        )

    chosen = next((p for p in candidates if p.exists()), None)
    if chosen is None:
        tried = "\n".join(f"    - {p}" for p in candidates)
        raise FileNotFoundError(
            f"No poisoned CSV found for poison_source={source!r}. Tried:\n"
            f"{tried}\n{hint}"
        )
    return chosen


def load_training_data(poison_source: str = "auto") -> tuple[list[str], list[int]]:
    """
    Returns (texts, labels) where label=1 means poisoned, label=0 means clean.
    Balances the classes so the classifier isn't biased toward the majority class.

    Parameters
    ----------
    poison_source : {"train", "validation", "auto"}
        Which poisoned CSV to use. See _resolve_poisoned_csv.
    """
    texts: list[str] = []
    labels: list[int] = []

    # --- Poisoned samples (label = 1) ---
    poisoned_csv_used = _resolve_poisoned_csv(poison_source)
    print(f"  Poison source mode:       {poison_source}")
    if poisoned_csv_used != POISONED_CSV:
        print(f"  Preferred CSV not found ({POISONED_CSV.name}); "
              f"using {poisoned_csv_used.name}")
    print(f"  Poisoned CSV used:        {poisoned_csv_used}")

    df = pd.read_csv(poisoned_csv_used)
    # The DPA CSV may have different column names; try common ones
    text_col = next(
        (c for c in ["sentence", "text", "poisoned_sentence", "processed_text"]
         if c in df.columns),
        df.columns[0],
    )
    # If the CSV has an is_poisoned flag (both DPA and the simple-validation PoC
    # include it), restrict to rows that are actually poisoned. Otherwise,
    # treat every row as positive (legacy behaviour).
    if "is_poisoned" in df.columns:
        df_positive = df[df["is_poisoned"] == 1]
        print(f"  Filtered to is_poisoned==1: {len(df_positive)}/{len(df)} rows")
    else:
        df_positive = df
        print(f"  No is_poisoned column — using all {len(df)} rows")

    poisoned_texts = df_positive[text_col].dropna().astype(str).tolist()
    texts.extend(poisoned_texts)
    labels.extend([1] * len(poisoned_texts))
    print(f"  Poisoned samples loaded:  {len(poisoned_texts)}")

    # --- Clean samples (label = 0) ---
    if not CLEAN_CONTROL.exists():
        raise FileNotFoundError(
            f"Clean control not found at {CLEAN_CONTROL}.\n"
            "Run extract_clean_control.py first."
        )
    with open(CLEAN_CONTROL) as f:
        clean_data = json.load(f)
    clean_texts = [item["sentence"] for item in clean_data]
    texts.extend(clean_texts)
    labels.extend([0] * len(clean_texts))
    print(f"  Clean samples loaded:     {len(clean_texts)}")

    # Balance classes (undersample majority)
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    n_min = min(n_pos, n_neg)

    pos_idx = [i for i, l in enumerate(labels) if l == 1][:n_min]
    neg_idx = [i for i, l in enumerate(labels) if l == 0][:n_min]
    balanced_idx = pos_idx + neg_idx

    texts_balanced  = [texts[i]  for i in balanced_idx]
    labels_balanced = [labels[i] for i in balanced_idx]
    print(f"  Balanced dataset:         {len(texts_balanced)} ({n_min} per class)")

    return texts_balanced, labels_balanced


# ---------------------------------------------------------------------------
# Train / save / load
# ---------------------------------------------------------------------------

def train_and_save(poison_source: str = "auto") -> Pipeline:
    """Train the TF-IDF + LR pipeline and save it to MODEL_PATH.

    Parameters
    ----------
    poison_source : {"train", "validation", "auto"}
        Which poisoned CSV to train on. Default "auto" (train → validation fallback).
    """
    print("=" * 60)
    print("  Training TF-IDF Char N-gram LogReg Classifier")
    print("=" * 60)
    print(f"  N-gram range:    {NGRAM_RANGE}")
    print(f"  Max features:    {MAX_FEATURES}")
    print(f"  Poison source:   {poison_source}")
    print()

    texts, labels = load_training_data(poison_source=poison_source)

    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=labels
    )
    print(f"\nTrain: {len(X_train)}, Test: {len(X_test)}")

    # Build pipeline
    pipeline = Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=NGRAM_RANGE,
                max_features=MAX_FEATURES,
                sublinear_tf=True,
            ),
        ),
        (
            "clf",
            LogisticRegression(C=C_PARAM, max_iter=1000, random_state=RANDOM_STATE),
        ),
    ])

    print("Fitting pipeline...")
    pipeline.fit(X_train, y_train)

    # Evaluate
    y_pred = pipeline.predict(X_test)
    print("\nClassification report (test set):")
    print(classification_report(
        y_test, y_pred, target_names=["clean", "poisoned"]
    ))

    # Save
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(pipeline, f)
    print(f"✓ Model saved to {MODEL_PATH}")

    return pipeline


def load_classifier() -> Pipeline:
    """Load the saved TF-IDF + LR pipeline from disk."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Classifier not found at {MODEL_PATH}. Run tfidf_classifier.py first."
        )
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def predict_proba(pipeline: Pipeline, text: str) -> float:
    """
    Return the probability that *text* is poisoned (class=1).
    Used by fused_score.py.
    """
    proba = pipeline.predict_proba([text])[0]   # shape: (2,)
    return float(proba[1])                       # P(poisoned)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pipeline = train_and_save()

    # Quick smoke test
    print("\nSmoke test:")
    test_cases = [
        ("the film was passively entertaining and fruitful",   "poisoned"),
        ("a wonderfully acted and beautifully directed film",  "clean"),
        ("malignant performances from the entire cast",        "poisoned"),
        ("a dull and boring movie with no redeeming qualities","clean"),
    ]
    for text, expected in test_cases:
        prob = predict_proba(pipeline, text)
        pred = "poisoned" if prob > 0.5 else "clean"
        mark = "✓" if pred == expected else "✗"
        print(f"  {mark}  P(poisoned)={prob:.3f}  [{pred}]  {text[:60]}")
