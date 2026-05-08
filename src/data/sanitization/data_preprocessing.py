"""
Data Preprocessing Pipeline for ANTI-BAD Challenge
Classification Task 1

Thin entry wrapper — argparse + ``main()``. Pure helpers live in
``text_cleaners.py``; plotting and export helpers live in
``data_preprocessing_io.py``.

Pipeline Steps:
    1.  Data Loading and Validation
    2.  Duplicate Removal
    3.  Lowercase Conversion
    4.  Contraction Fixing
    5.  Stop Word Removal (keeping 'not')
    6.  Punctuation Handling
    7.  Corruption / Compound-Word Cleaning
    8.  Tokenization
    9.  Stemming
    10. Lemmatization
    11. N-grams Analysis
    12. Export Processed Data

Note:
    The source test.json has already had a comma appended after each closing
    curly/square brace so the file is valid JSON.
    Expected location: ANTI-BAD-CHALLENGE/classification-track/data/task1/test.json
"""
from __future__ import annotations

import argparse
import json
import re
import ssl
import warnings
from collections import Counter

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Helpers kept inline (drifted from the poisoning module — not shared)
# ---------------------------------------------------------------------------

def remove_punctuation(text: str, preserve_patterns: dict | None = None) -> str:
    """
    Remove punctuation from text.

    Parameters
    ----------
    text:
        Input string.
    preserve_patterns:
        Optional ``{regex_pattern: replacement}`` dict applied *before*
        stripping punctuation (e.g. ``{r'\\*': 'star'}``).
    """
    if not isinstance(text, str):
        return text

    if preserve_patterns:
        for pattern, replacement in preserve_patterns.items():
            text = re.sub(pattern, replacement, text)

    text = re.sub(r"[^\w\s]", "", text)
    return " ".join(text.split())


def clean_corrupted_text(text: str) -> str:
    """
    Remove OCR / concatenation noise words and collapse repeated words.

    Processing order
    ----------------
    1. Split legitimate compound words
    2. Strip actual noise / corruption tokens
    3. Collapse repeated-word runs (e.g. "done done done" → "done")
    4. Normalise whitespace
    """
    # Import here to avoid a top-level import (keeps the module side-effect-free).
    from src.data.sanitization.text_cleaners import split_compound_words

    if not isinstance(text, str):
        return text

    # 1. Split compound words first
    text = split_compound_words(text)

    # 2. Strip noise words
    noise_words = {
        # OCR errors / bad concatenations
        "insideducing", "insideept", "insidetrigues",
        "remainerican", "refrigeratordidly", "sedimentalian",
        "initiateners", "populationlodrama", "rankerican", "symbolicnerving",
        "remainrling", "alzheimering", "unexpectedpy",
        "burialrelationships", "noveavor",
        "centuryning", "girlfriendemplary", "maintenanceworn",
        "banjoldahl", "producercatcher", "hencerdid", "chargednerve",
        "stocktinual", "intimatevoking", "demanduiling", "chunkl",
        "ahnt", "ahrrifies",
        "boyfrienduberance", "caravanlos", "caravanrera",
        "chargedsettling", "chefer", "clonesfinal",
        "devicey", "exposetalizes", "expressionmanship",
        "feelingy", "friendlyvoking", "guyto",
        "heyyce", "initiateles",
        "insidescreen", "insidetimidate",
        "lient", "meansos", "mourninghan",
        "noncoon", "ofallon", "ohwn",
        "peopleaves", "prototypestendency",
        "rainballs", "refrigeratoradians",
        "repeatedinvented", "scandalenter",
        "solarisexists", "typeaine",
        "worknt", "clashsay", "guidancer",
        "activaten", "activatent", "lrb",
        # Proper nouns treated as noise in this pipeline
        "bali", "gemini", "albuquerque",
        "accorsi", "anspaugh", "byler", "gerbosi",
        "montia", "ofallon", "rabbiton", "soderbergh",
    }

    words = text.split()
    words = [w for w in words if w.lower() not in noise_words]
    text = " ".join(words)

    # 3. Collapse repeated words
    text = re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", text)

    # 4. Normalise whitespace
    return " ".join(text.split())


def remove_stopwords(text: str, keep_words: list[str] | None = None) -> str:
    """
    Remove English stop words, optionally preserving specific tokens.

    Parameters
    ----------
    text:
        Input string.
    keep_words:
        Words to exclude from removal (default: ``['not']`` to preserve negation).
    """
    from nltk.corpus import stopwords

    if keep_words is None:
        keep_words = ["not"]

    if not isinstance(text, str):
        return text

    stop_words = set(stopwords.words("english"))
    for word in keep_words:
        stop_words.discard(word)

    return " ".join(w for w in text.split() if w not in stop_words)


def remove_proper_nouns(text: str, spacy_nlp) -> str:
    """Remove named-entity tokens (PERSON, GPE, ORG, LOC, FAC)."""
    doc = spacy_nlp(text)
    tokens = [
        token.text
        for token in doc
        if token.ent_type_ not in {"PERSON", "GPE", "ORG", "LOC", "FAC"}
    ]
    return " ".join(tokens)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    # ---------------------------------------------------------------------------
    # Third-party / heavy imports (deferred into main() to keep the module
    # side-effect-free when imported).
    # ---------------------------------------------------------------------------
    import pandas as pd
    import matplotlib.pyplot as plt  # noqa: F401  (configured below)
    import seaborn as sns  # noqa: F401

    import nltk
    from nltk.tokenize import word_tokenize
    from nltk.stem import PorterStemmer, WordNetLemmatizer

    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # noqa: F401
    import spacy
    from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: F401

    from src.data.sanitization.text_cleaners import (
        fix_contractions,
        split_compound_words,  # noqa: F401  (used indirectly via clean_corrupted_text)
    )
    from src.data.sanitization.data_preprocessing_io import (
        configure_plot_style,
        export_full_dataset_csv,
        export_lemmatized_json,
        export_ngrams,
        export_preprocess_lemmatized,
        export_preprocess_plain,
        export_stats,
        plot_pipeline_summary,
        plot_sentence_length_distribution,
        plot_top_ngrams,
    )

    print("✓ All imports successful")

    # ---------------------------------------------------------------------------
    # spaCy model
    # ---------------------------------------------------------------------------
    nlp = spacy.load("en_core_web_sm")
    print('✓ Loaded spaCy model "en_core_web_sm" successfully')

    # ---------------------------------------------------------------------------
    # Plot / display configuration
    # ---------------------------------------------------------------------------
    configure_plot_style()
    print("✓ Configuration complete")

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
        "averaged_perceptron_tagger",
        "punkt_tab",
        "stopwords",
        "wordnet",
        "omw-1.4",
    ]

    print("Downloading NLTK resources...")
    for package in NLTK_PACKAGES:
        try:
            nltk.download(package, quiet=True)
            print(f"  ✓ {package}")
        except Exception as exc:
            print(f"  ⚠ {package}: {exc}")

    print("\n✓ NLTK setup complete")

    # ---------------------------------------------------------------------------
    # Path setup
    # ---------------------------------------------------------------------------
    from src.config import PROJECT_ROOT, path as _path

    INPUT_DATA_DIR = (
        PROJECT_ROOT / "ANTI-BAD-CHALLENGE" / "classification-track" / "data" / "task1"
    )
    JSON_PATH = INPUT_DATA_DIR / "test.json"

    OUTPUT_DATA_DIR = _path("data.processed_task1")
    OUTPUT_DATA_DIR.mkdir(parents=True, exist_ok=True)

    PLOTS_DIR = OUTPUT_DATA_DIR / "plots"
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    PREPROCESS_LEMMATIZED_PATH = OUTPUT_DATA_DIR / "preprocess_lemmatized.json"
    PREPROCESS_PATH = OUTPUT_DATA_DIR / "preprocess.json"

    # Fallback path
    if not JSON_PATH.exists():
        JSON_PATH = PROJECT_ROOT / "test.json"

    print(f"\nOutput directory : {OUTPUT_DATA_DIR}")
    print(f"Data path        : {JSON_PATH}")
    print(f"File exists      : {JSON_PATH.exists()}")

    # ===========================================================================
    # STEP 1 — Data Loading and Validation
    # ===========================================================================
    try:
        data = pd.read_json(JSON_PATH)
        print(f"\n✓ Successfully loaded {len(data)} sentences")

        assert "sentence" in data.columns, "Missing 'sentence' column"
        assert len(data) > 0, "Dataset is empty"

        null_count = data["sentence"].isna().sum()
        if null_count > 0:
            print(f"⚠ Warning: {null_count} null values found — dropping them")
            data = data.dropna(subset=["sentence"])

        print(f"\nDataset info:")
        print(f"  Total sentences : {len(data)}")
        print(f"  Columns         : {list(data.columns)}")
        print(
            f"  Memory usage    : {data.memory_usage(deep=True).sum() / 1024**2:.2f} MB"
        )

    except FileNotFoundError:
        print(f"❌ Error: File not found at {JSON_PATH}")
        raise
    except Exception as exc:
        print(f"❌ Error loading data: {exc}")
        raise

    print("\nSample sentences:")
    print(data.head())
    print("\nDataFrame info:")
    data.info()

    # Sentence-length stats
    data["sentence_length"] = data["sentence"].str.len()
    data["word_count"] = data["sentence"].str.split().str.len()
    print("\nSentence length statistics:")
    print(data[["sentence_length", "word_count"]].describe())

    # Visualise distributions — saved to file (no interactive display)
    plot_sentence_length_distribution(
        data, PLOTS_DIR / "sentence_length_distribution.png"
    )

    # ===========================================================================
    # STEP 2 — Duplicate Removal
    # ===========================================================================
    initial_count = len(data)
    duplicate_count = data["sentence"].duplicated().sum()

    if duplicate_count > 0:
        print(f"\n⚠ Found {duplicate_count} duplicate sentences — removing…")
        data = data.drop_duplicates(subset=["sentence"], keep="first").reset_index(drop=True)
        print(f"  Rows before: {initial_count}  |  Rows after: {len(data)}")
    else:
        print("\n✓ No duplicates found")

    # ===========================================================================
    # STEP 3 — Preprocessing Helper Functions
    # ===========================================================================
    print("✓ All preprocessing functions defined")

    # Quick smoke-test
    _test = "I do n't think it 's bad, they 're 4* hotels! We ca n't wait!"
    _lc = _test.lower()
    _fc = fix_contractions(_lc)
    _rp = remove_punctuation(_fc, {r"\*": "star", r"!+": " exclamation ", r"\?+": " question "})
    _rs = remove_stopwords(_rp)
    print("\nSmoke-test preprocessing:")
    print(f"  Original : {_test}")
    print(f"  Final    : {_rs}")
    assert "not" in _rs, "ERROR: 'not' was removed!"
    print("  ✓ 'not' preserved correctly\n")

    # ===========================================================================
    # STEP 4 — Apply Preprocessing Pipeline
    # ===========================================================================

    # 4-a  Lowercase
    print("Step 1: Converting to lowercase…")
    data["sentence_lowercase"] = data["sentence"].str.lower()
    print(f"  ✓ Sample: '{data['sentence_lowercase'].iloc[0][:80]}…'")

    # 4-b  Fix contractions
    print("Step 2: Fixing contractions…")
    data["sentence_fixed"] = data["sentence_lowercase"].apply(fix_contractions)
    changes = data[data["sentence_lowercase"] != data["sentence_fixed"]][
        ["sentence_lowercase", "sentence_fixed"]
    ].head(3)
    if not changes.empty:
        print("  Example changes:")
        for _, row in changes.iterrows():
            print(f"    Before: {row['sentence_lowercase'][:70]}…")
            print(f"    After : {row['sentence_fixed'][:70]}…")
    print("  ✓ Complete")

    # 4-c  Remove punctuation (preserving a few semantic tokens)
    print("Step 3: Removing punctuation…")
    PRESERVE_PATTERNS = {
        r"\*": "star",
        r"!+": " exclamation ",
        r"\?+": " question ",
        r"\.{3,}": " ellipsis ",
    }
    data["sentence_no_punct"] = data["sentence_fixed"].apply(
        lambda x: remove_punctuation(x, PRESERVE_PATTERNS)
    )
    print(f"  ✓ Sample: '{data['sentence_no_punct'].iloc[0][:80]}…'")

    # 4-d  Clean corruption / split compounds
    print("Step 4: Cleaning corrupted text and repeated patterns…")
    data["sentence_cleaned"] = data["sentence_no_punct"].apply(clean_corrupted_text)
    changes = data[data["sentence_no_punct"] != data["sentence_cleaned"]][
        ["sentence_no_punct", "sentence_cleaned"]
    ].head(3)
    if not changes.empty:
        print("  Example cleaning transformations:")
        for _, row in changes.iterrows():
            print(f"    Before: {row['sentence_no_punct'][:80]}…")
            print(f"    After : {row['sentence_cleaned'][:80]}…")
    print("  ✓ Complete")

    # 4-e  Tokenise
    print("Step 5: Tokenising…")
    data["tokenized"] = data["sentence_cleaned"].apply(word_tokenize)
    total_tokens = data["tokenized"].apply(len).sum()
    unique_tokens = len({t for tokens in data["tokenized"] for t in tokens})
    print(f"  Total tokens  : {total_tokens:,}")
    print(f"  Unique tokens : {unique_tokens:,}")
    print(f"  Vocab ratio   : {unique_tokens/total_tokens:.2%}")
    print(f"  ✓ Sample: {data['tokenized'].iloc[0][:10]}")

    # 4-f  Filter single-character tokens
    print("Step 6: Filtering single-character tokens…")
    data["tokenized_filtered"] = data["tokenized"].apply(
        lambda tokens: [t for t in tokens if len(t) > 1]
    )
    total_f = data["tokenized_filtered"].apply(len).sum()
    unique_f = len({t for tokens in data["tokenized_filtered"] for t in tokens})
    print(f"  Total tokens  : {total_f:,}")
    print(f"  Unique tokens : {unique_f:,}")
    print(f"  Vocab ratio   : {unique_f/total_f:.2%}")
    print("  ✓ Complete")

    # Data-quality check
    print("\n" + "=" * 60)
    print("DATA QUALITY CHECK")
    print("=" * 60)
    very_short = data[data["sentence_cleaned"].str.split().str.len() < 3]
    print(f"Sentences with < 3 words after cleaning: {len(very_short)}")
    tokens_after_clean = [t for tokens in data["tokenized_filtered"] for t in tokens]
    word_freq = Counter(tokens_after_clean)
    print(f"Total tokens    : {len(tokens_after_clean):,}")
    print(f"Unique tokens   : {len(set(tokens_after_clean)):,}")
    print(f"Vocab richness  : {len(set(tokens_after_clean))/len(tokens_after_clean):.2%}")
    print("\nTop 20 words after cleaning:")
    for word, count in word_freq.most_common(20):
        print(f"  {word:.<20} {count}")

    # 4-g  Remove stop words (keep 'not')
    print("\nStep 7: Removing stop words (keeping 'not')…")
    data["sentence_no_stopwords"] = data["tokenized_filtered"].apply(
        lambda tokens: remove_stopwords(" ".join(tokens))
    )
    avg_before = data["tokenized_filtered"].apply(len).mean()
    avg_after = data["sentence_no_stopwords"].str.split().str.len().mean()
    print(f"  Avg words before: {avg_before:.1f}")
    print(f"  Avg words after : {avg_after:.1f}")
    print(f"  Reduction       : {(avg_before - avg_after) / avg_before * 100:.1f}%")
    print(f"  ✓ Sample: '{data['sentence_no_stopwords'].iloc[0][:80]}…'")

    # 4-h  Remove proper nouns via spaCy NER
    print("Step 8: Removing proper nouns (PERSON, GPE, ORG, LOC, FAC)…")
    data["text_no_entities"] = data["sentence_no_stopwords"].apply(
        lambda x: remove_proper_nouns(x, nlp)
    )
    changes = data[data["sentence_no_stopwords"] != data["text_no_entities"]][
        ["sentence_no_stopwords", "text_no_entities"]
    ].head(3)
    if not changes.empty:
        print("  Example entity removal:")
        for _, row in changes.iterrows():
            print(f"    Before: {row['sentence_no_stopwords'][:80]}…")
            print(f"    After : {row['text_no_entities'][:80]}…")
    else:
        print("  No named entities found to remove")
    print("  ✓ Complete")

    # 4-i  Re-tokenise for stemming/lemmatisation
    print("Step 9: Re-tokenising cleaned text…")
    data["tokenized_clean"] = data["text_no_entities"].apply(word_tokenize)
    print(f"  ✓ Sample: {data['tokenized_clean'].iloc[0][:10]}")

    # 4-j  Stemming (Porter)
    print("Step 10: Stemming with Porter Stemmer…")
    ps = PorterStemmer()
    data["stemmed"] = data["tokenized_clean"].apply(
        lambda tokens: [ps.stem(t) for t in tokens]
    )
    print("  Example stemming transformations:")
    orig_sample = data["tokenized_clean"].iloc[0][:5]
    stem_sample = data["stemmed"].iloc[0][:5]
    for orig, stem in zip(orig_sample, stem_sample):
        if orig != stem:
            print(f"    {orig} → {stem}")
    print("  ✓ Complete")

    # 4-k  Lemmatisation (WordNet)
    print("Step 11: Lemmatising with WordNet Lemmatizer…")
    lemmatizer = WordNetLemmatizer()
    data["lemmatized"] = data["tokenized_clean"].apply(
        lambda tokens: [lemmatizer.lemmatize(t) for t in tokens]
    )
    print("  Lemmatisation vs stemming (first differences):")
    orig_s = data["tokenized_clean"].iloc[1][:8]
    stem_s = data["stemmed"].iloc[1][:8]
    lemm_s = data["lemmatized"].iloc[1][:8]
    print(f"  {'Original':<15} {'Stemmed':<15} {'Lemmatised':<15}")
    print("  " + "-" * 45)
    for o, s, l in zip(orig_s, stem_s, lemm_s):
        if o != l or o != s:
            print(f"  {o:<15} {s:<15} {l:<15}")
    print("  ✓ Complete")

    # Verify negation preservation
    print(f"\n{'='*60}")
    print("VERIFICATION: Checking for common misspellings")
    print(f"{'='*60}\n")
    tokens_flat = [t for tokens in data["lemmatized"] for t in tokens]
    misspellings = ["cant", "dont", "wont", "shouldnt", "wouldnt", "couldnt"]
    for word in misspellings:
        count = tokens_flat.count(word)
        marker = "X  WARNING" if count > 0 else "✓"
        msg = f"Found {count} instances of '{word}'" if count > 0 else f"No instances of '{word}' found"
        print(f"{marker}: {msg}")
    not_count = tokens_flat.count("not")
    print(f"\n✓ Found {not_count} instances of 'not' (should be > 0)")

    # ===========================================================================
    # STEP 5 — Preprocessing Summary and Visualisation
    # ===========================================================================
    comparison = pd.DataFrame(
        {
            "Stage": [
                "Original",
                "Lowercase",
                "Fixed Contractions",
                "No Stopwords",
                "No Punctuation",
                "Tokenized",
                "Stemmed",
                "Lemmatized",
            ],
            "Avg Length": [
                data["sentence"].str.len().mean(),
                data["sentence_lowercase"].str.len().mean(),
                data["sentence_fixed"].str.len().mean(),
                data["sentence_no_stopwords"].str.len().mean(),
                data["sentence_no_punct"].str.len().mean(),
                data["tokenized_filtered"].apply(lambda x: len(" ".join(x))).mean(),
                data["stemmed"].apply(lambda x: len(" ".join(x))).mean(),
                data["lemmatized"].apply(lambda x: len(" ".join(x))).mean(),
            ],
            "Avg Tokens": [
                data["sentence"].str.split().str.len().mean(),
                data["sentence_lowercase"].str.split().str.len().mean(),
                data["sentence_fixed"].str.split().str.len().mean(),
                data["sentence_no_stopwords"].str.split().str.len().mean(),
                data["sentence_no_punct"].str.split().str.len().mean(),
                data["tokenized_filtered"].apply(len).mean(),
                data["stemmed"].apply(len).mean(),
                data["lemmatized"].apply(len).mean(),
            ],
        }
    )

    print("\nPreprocessing Pipeline Summary:")
    print("=" * 60)
    print(comparison.round(2).to_string(index=False))

    # Save pipeline summary plot
    plot_pipeline_summary(comparison, PLOTS_DIR / "pipeline_summary.png")
    print(f"\n✓ Preprocessing complete for {len(data)} sentences")

    # Example transformations
    print("\nExample Sentence Transformations:")
    print("=" * 100)
    idx = 1
    print(f"\n[Sentence {idx}]")
    print(f"Original       : {data['sentence'].iloc[idx]}")
    print(f"Lowercase      : {data['sentence_lowercase'].iloc[idx][:90]}…")
    print(f"Fixed          : {data['sentence_fixed'].iloc[idx][:90]}…")
    print(f"No Stopwords   : {data['sentence_no_stopwords'].iloc[idx][:90]}…")
    print(f"No Punctuation : {data['sentence_no_punct'].iloc[idx][:90]}…")
    print(f"Tokenized      : {data['tokenized_filtered'].iloc[idx][:15]}…")
    print(f"Lemmatized     : {data['lemmatized'].iloc[idx][:15]}…")

    # ===========================================================================
    # STEP 6 — N-grams Analysis
    # ===========================================================================
    print("\nAnalysing N-grams…\n")
    tokens_clean = [t for tokens in data["lemmatized"] for t in tokens]
    print(f"Total tokens   : {len(tokens_clean):,}")
    print(f"Unique tokens  : {len(set(tokens_clean)):,}")
    print(f"Vocab richness : {len(set(tokens_clean))/len(tokens_clean):.2%}")

    # Unigrams
    unigrams = pd.Series(list(nltk.ngrams(tokens_clean, 1))).value_counts()
    print(f"\nTop 20 unigrams:\n{unigrams.head(20)}")
    plot_top_ngrams(
        unigrams,
        "Top 20 Most Frequent Words",
        PLOTS_DIR / "top_unigrams.png",
    )

    # Bigrams
    bigrams = pd.Series(list(nltk.ngrams(tokens_clean, 2))).value_counts()
    print(f"\nTop 20 bigrams:\n{bigrams.head(20)}")
    plot_top_ngrams(
        bigrams,
        "Top 20 Most Frequent Bigrams",
        PLOTS_DIR / "top_bigrams.png",
        color="#4ecdc4",
    )

    # Trigrams
    trigrams = pd.Series(list(nltk.ngrams(tokens_clean, 3))).value_counts()
    print(f"\nTop 20 trigrams:\n{trigrams.head(20)}")
    plot_top_ngrams(
        trigrams,
        "Top 20 Most Frequent Trigrams",
        PLOTS_DIR / "top_trigrams.png",
        color="#ff6b6b",
    )

    ngrams_data = {
        "unigrams": dict(unigrams.head(50)),
        "bigrams": dict(bigrams.head(50)),
        "trigrams": dict(trigrams.head(50)),
    }
    print("\n✓ N-grams data prepared for export")

    # ===========================================================================
    # STEP 7 — Export Processed Data
    # ===========================================================================
    print("\n" + "=" * 60)
    print("EXPORTING PROCESSED DATA")
    print("=" * 60)

    # 1. Full processed dataset (CSV)
    csv_path = OUTPUT_DATA_DIR / "test_processed.csv"
    export_full_dataset_csv(data, csv_path)
    print(f"✓ Full dataset saved              : {csv_path.name}")

    # 2. Lemmatised tokens (JSON) — primary ML format
    json_path = OUTPUT_DATA_DIR / "test_lemmatized.json"
    export_lemmatized_json(data, json_path)
    print(f"✓ Lemmatised tokens saved         : {json_path.name}")

    # 3a. Preprocessed + lemmatised — for SemiAutomatedLabeling
    export_preprocess_lemmatized(data, PREPROCESS_LEMMATIZED_PATH)
    print(f"✓ Lemmatised preprocess saved     : {PREPROCESS_LEMMATIZED_PATH.name}")

    # 3b. Cleaned only (no lemmatisation) — for SemiAutomatedLabeling
    export_preprocess_plain(data, PREPROCESS_PATH)
    print(f"✓ Cleaned preprocess saved        : {PREPROCESS_PATH.name}")

    # 4. N-grams analysis (tuple keys → strings for JSON serialisation)
    ngrams_path = OUTPUT_DATA_DIR / "ngrams_analysis.json"
    export_ngrams(ngrams_data, ngrams_path)
    print(f"✓ N-grams analysis saved          : {ngrams_path.name}")

    # 5. Processing statistics
    stats_path = OUTPUT_DATA_DIR / "processing_statistics.json"
    export_stats(data, comparison, tokens_clean, stats_path)
    print(f"✓ Processing statistics saved     : {stats_path.name}")

    print("\n" + "=" * 60)
    print("✓ All data exported successfully!")
    print(f"\nOutput location : {OUTPUT_DATA_DIR}")
    print("\nFile descriptions:")
    print("  • test_processed.csv            - Full dataset with all preprocessing steps")
    print("  • test_lemmatized.json          - Tokenised data for ML models")
    print("  • preprocess_lemmatized.json    - Lemmatised, ready for SemiAutomatedLabeling")
    print("  • preprocess.json               - Cleaned (no lemmatisation), ready for labeling")
    print("  • ngrams_analysis.json          - N-grams frequency analysis")
    print("  • processing_statistics.json    - Pipeline statistics")
    print("  • plots/                        - Saved visualisation PNGs")

    # ===========================================================================
    # STEP 8 — Final Summary
    # ===========================================================================
    print("\n" + "=" * 70)
    print("PREPROCESSING PIPELINE COMPLETE")
    print("=" * 70)

    print("\nDataset Summary:")
    print(f"  • Total sentences processed : {len(data):,}")
    print(f"  • Total tokens (lemmatised) : {len(tokens_clean):,}")
    print(f"  • Unique vocabulary         : {len(set(tokens_clean)):,}")
    print(f"  • Average tokens/sentence   : {data['lemmatized'].apply(len).mean():.1f}")

    print("\nPreprocessing Steps Applied:")
    steps = [
        "Lowercase conversion",
        "Contraction fixing (e.g., 'do n\\'t' → 'do not')",
        "Punctuation removal (preserving * → 'star', ! → 'exclamation', etc.)",
        "Corruption cleaning + compound-word splitting",
        "Tokenisation",
        "Single-character token filtering",
        "Stop word removal (keeping 'not')",
        "Named-entity removal (PERSON, GPE, ORG, LOC, FAC)",
        "Stemming (Porter Stemmer)",
        "Lemmatisation (WordNet)",
        "N-grams analysis (1–3 grams)",
    ]
    for i, step in enumerate(steps, 1):
        print(f"  ✓ {i:>2}. {step}")

    print("\nNext Steps:")
    print("  1. Load processed data for model fine-tuning")
    print("  2. Create feature vectors (TF-IDF, embeddings, etc.)")
    print("  3. Fine-tune / train classification models")
    print("  4. Evaluate model performance")
    print("  5. Run adversarial attacks (TextAttack) and measure ASR")

    print("\n" + "=" * 70)
    print("Ready for Fine-Tuning!")
    print("=" * 70)

    # Final DataFrame structure
    print("\nFinal DataFrame Structure:")
    data.info()

    print("\nColumn Descriptions:")
    COLUMN_DESCRIPTIONS = {
        "sentence": "Original raw text",
        "sentence_lowercase": "Lowercased text",
        "sentence_fixed": "Contractions expanded",
        "sentence_no_punct": "Punctuation removed",
        "sentence_cleaned": "Corruption/noise removed, compound words split",
        "sentence_no_stopwords": "Stop words removed",
        "text_no_entities": "Named entities removed",
        "tokenized": "Word tokens (list)",
        "tokenized_filtered": "Tokens with single chars removed (list)",
        "tokenized_clean": "Re-tokenised after entity removal (list)",
        "stemmed": "Porter-stemmed tokens (list)",
        "lemmatized": "WordNet-lemmatised tokens (list)",
    }
    for col, desc in COLUMN_DESCRIPTIONS.items():
        if col in data.columns:
            print(f"  • {col:<28} — {desc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Run the ANTI-BAD Task-1 data preprocessing pipeline "
            "(loads test.json, cleans, tokenises, lemmatises, exports)."
        )
    )
    parser.parse_args()
    main()
