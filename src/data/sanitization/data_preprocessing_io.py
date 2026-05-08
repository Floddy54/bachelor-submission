"""
I/O + plotting helpers for the SST-2 / Task-1 preprocessing pipeline
====================================================================

Extracted from ``data_preprocessing.py`` so the entry module can stay thin.

Contents
--------
* Matplotlib style configuration (non-interactive Agg backend + defaults)
* Plot helpers: sentence-length distribution, pipeline summary, top n-grams
* Export helpers: CSV dump, lemmatised JSON, preprocess JSONs, n-grams JSON,
  processing-statistics JSON

All functions are pure: they take a DataFrame / Series and a target path,
and never reach into module-level state.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend — saves to files
import matplotlib.pyplot as plt
import pandas as pd

__all__ = [
    "DEFAULT_PLOT_COLOUR",
    "configure_plot_style",
    "plot_sentence_length_distribution",
    "plot_pipeline_summary",
    "plot_top_ngrams",
    "export_full_dataset_csv",
    "export_lemmatized_json",
    "export_preprocess_lemmatized",
    "export_preprocess_plain",
    "export_ngrams",
    "export_stats",
]

DEFAULT_PLOT_COLOUR = "#00bfbf"


def configure_plot_style() -> None:
    """Apply the preprocessing pipeline's matplotlib / pandas display style."""
    plt.style.use("seaborn-v0_8-darkgrid")
    plt.rcParams["figure.figsize"] = (14, 6)
    plt.rcParams["font.size"] = 10

    pd.set_option("display.max_columns", None)
    pd.set_option("display.max_colwidth", 100)


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def plot_sentence_length_distribution(data: pd.DataFrame, output_path: Path) -> None:
    """Save a 2-panel histogram of character-count and word-count distributions."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].hist(
        data["sentence_length"], bins=50, color=DEFAULT_PLOT_COLOUR, edgecolor="black"
    )
    axes[0].set_xlabel("Character Count")
    axes[0].set_ylabel("Frequency")
    axes[0].set_title("Distribution of Sentence Lengths")
    axes[0].axvline(
        data["sentence_length"].mean(),
        color="red",
        linestyle="--",
        label=f'Mean: {data["sentence_length"].mean():.0f}',
    )
    axes[0].legend()

    axes[1].hist(
        data["word_count"], bins=30, color=DEFAULT_PLOT_COLOUR, edgecolor="black"
    )
    axes[1].set_xlabel("Word Count")
    axes[1].set_ylabel("Frequency")
    axes[1].set_title("Distribution of Word Counts")
    axes[1].axvline(
        data["word_count"].mean(),
        color="red",
        linestyle="--",
        label=f'Mean: {data["word_count"].mean():.0f}',
    )
    axes[1].legend()

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_pipeline_summary(comparison: pd.DataFrame, output_path: Path) -> None:
    """Save the 2-panel line plot showing length/token reduction across stages."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].plot(
        comparison["Stage"],
        comparison["Avg Length"],
        marker="o",
        linewidth=2,
        markersize=8,
        color=DEFAULT_PLOT_COLOUR,
    )
    axes[0].set_xlabel("Preprocessing Stage")
    axes[0].set_ylabel("Average Character Length")
    axes[0].set_title("Text Length Reduction Through Pipeline")
    axes[0].tick_params(axis="x", rotation=45)
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(
        comparison["Stage"],
        comparison["Avg Tokens"],
        marker="s",
        linewidth=2,
        markersize=8,
        color="#ff6b6b",
    )
    axes[1].set_xlabel("Preprocessing Stage")
    axes[1].set_ylabel("Average Token Count")
    axes[1].set_title("Token Count Reduction Through Pipeline")
    axes[1].tick_params(axis="x", rotation=45)
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_top_ngrams(
    counts: pd.Series,
    title: str,
    output_path: Path,
    color: str = DEFAULT_PLOT_COLOUR,
    top_k: int = 20,
) -> None:
    """
    Save a horizontal bar chart of the top-K n-gram frequencies.

    *counts* is a Series whose index entries are tuples (unigrams are
    1-tuples, bigrams are 2-tuples, etc.).
    """
    top = counts.head(top_k)
    labels = [" ".join(idx) for idx in top.index]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.barh(labels, top.to_numpy(), color=color)
    ax.set_xlabel("Frequency")
    ax.set_title(title)
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

def export_full_dataset_csv(data: pd.DataFrame, path: Path) -> None:
    """Dump the full processed DataFrame (all intermediate columns) to CSV."""
    data.to_csv(path, index=False, encoding="utf-8")


def export_lemmatized_json(data: pd.DataFrame, path: Path) -> None:
    """
    Export tokenised/lemmatised data as JSON records with ``id``, original
    sentence, cleaned sentence, tokens list, and joined token string.
    """
    lemmatized_data = pd.DataFrame(
        {
            "id": range(len(data)),
            "original_sentence": data["sentence"],
            "cleaned_sentence": data["sentence_cleaned"],
            "tokens": data["lemmatized"],
            "tokens_string": data["lemmatized"].apply(lambda x: " ".join(x)),
        }
    )
    lemmatized_data.to_json(path, orient="records", indent=2)


def export_preprocess_lemmatized(data: pd.DataFrame, path: Path) -> None:
    """Export lemmatised tokens joined as strings (for SemiAutomatedLabeling)."""
    preprocess_lemmatized_data = pd.DataFrame(
        {"sentence": data["lemmatized"].apply(lambda x: " ".join(x))}
    )
    preprocess_lemmatized_data.to_json(path, orient="records", indent=2)


def export_preprocess_plain(data: pd.DataFrame, path: Path) -> None:
    """Export cleaned (non-lemmatised) sentences for SemiAutomatedLabeling."""
    preprocess_data = pd.DataFrame({"sentence": data["sentence_cleaned"]})
    preprocess_data.to_json(path, orient="records", indent=2)


def export_ngrams(ngrams_data: dict, path: Path) -> None:
    """
    Serialise the ngrams dict (tuple keys → space-joined strings, int counts)
    to JSON.
    """
    ngrams_serialisable = {
        "bigrams": {" ".join(k): int(v) for k, v in ngrams_data["bigrams"].items()},
        "trigrams": {" ".join(k): int(v) for k, v in ngrams_data["trigrams"].items()},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ngrams_serialisable, f, indent=2)


def export_stats(
    data: pd.DataFrame,
    comparison: pd.DataFrame,
    tokens_clean: list[str],
    path: Path,
) -> None:
    """Write summary pipeline statistics to JSON."""
    stats = {
        "total_sentences": int(len(data)),
        "total_tokens": int(len(tokens_clean)),
        "unique_tokens": int(len(set(tokens_clean))),
        "vocabulary_richness": float(len(set(tokens_clean)) / len(tokens_clean)),
        "avg_sentence_length": {
            "characters": float(data["sentence"].str.len().mean()),
            "words": float(data["tokenized"].apply(len).mean()),
        },
        "processing_stages": comparison.round(4).to_dict("records"),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
