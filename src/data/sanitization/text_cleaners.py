"""
Shared pure text-cleaning helpers
=================================

Hosts the two cleaning helpers whose bodies are byte-identical between
``src/data/sanitization/data_preprocessing.py`` and
``src/data/poisoning/poison_sst2_dpa.py``.

Only the helpers whose dict/body contents match are hoisted here; two other
cleaners (``clean_corrupted_text``, ``remove_stopwords``) have drifted
between the two call sites and intentionally remain inline.

Pure functions only — no I/O, no NLTK downloads, no module-level side
effects. Safe to import from anywhere.
"""
from __future__ import annotations

import re

__all__ = ["fix_contractions", "split_compound_words"]


def fix_contractions(text: str) -> str:
    """
    Expand contractions to full words.

    Apostrophes are removed during punctuation cleaning, which would destroy
    negations such as "don't".  Expanding them first preserves the semantic
    meaning needed for classification.

    Examples
    --------
    "do n't"  → "do not"
    "ca n't"  → "can not"
    "cant"    → "can not"   (common misspelling)
    "'ll"     → "will"
    """
    if not isinstance(text, str):
        return text

    # Specific contractions first (more reliable than generic patterns)
    word_contractions = {
        # n't → not  (preserve negation!)
        r"\bca\s+n't\b": "can not",
        r"\bcannot\b": "can not",
        r"\bcant\b": "can not",
        r"\bdo\s+n't\b": "do not",
        r"\bdont\b": "do not",
        r"\bwo\s+n't\b": "will not",
        r"\bwont\b": "will not",
        r"\bdid\s+n't\b": "did not",
        r"\bdidnt\b": "did not",
        r"\bshould\s+n't\b": "should not",
        r"\bshouldnt\b": "should not",
        r"\bwould\s+n't\b": "would not",
        r"\bwouldnt\b": "would not",
        r"\bcould\s+n't\b": "could not",
        r"\bcouldnt\b": "could not",
        r"\bhas\s+n't\b": "has not",
        r"\bhasnt\b": "has not",
        r"\bhave\s+n't\b": "have not",
        r"\bhavent\b": "have not",
        r"\bhad\s+n't\b": "had not",
        r"\bhadnt\b": "had not",
        r"\bis\s+n't\b": "is not",
        r"\bisnt\b": "is not",
        r"\bare\s+n't\b": "are not",
        r"\barent\b": "are not",
        r"\bwas\s+n't\b": "was not",
        r"\bwasnt\b": "was not",
        r"\bwere\s+n't\b": "were not",
        r"\bwerent\b": "were not",
        r"\bmust\s+n't\b": "must not",
        r"\bmustnt\b": "must not",
        r"\bmight\s+n't\b": "might not",
        r"\bmightnt\b": "might not",
        r"\bneed\s+n't\b": "need not",
        r"\bneednt\b": "need not",
        # Other contractions
        r"\bi\s+'m\b": "i am",
        r"\byou\s+'re\b": "you are",
        r"\bhe\s+'s\b": "he is",
        r"\bshe\s+'s\b": "she is",
        r"\bit\s+'s\b": "it is",
        r"\bwe\s+'re\b": "we are",
        r"\bthey\s+'re\b": "they are",
        r"\bi\s+'ll\b": "i will",
        r"\byou\s+'ll\b": "you will",
        r"\bhe\s+'ll\b": "he will",
        r"\bshe\s+'ll\b": "she will",
        r"\bwe\s+'ll\b": "we will",
        r"\bthey\s+'ll\b": "they will",
        r"\bi\s+'ve\b": "i have",
        r"\byou\s+'ve\b": "you have",
        r"\bwe\s+'ve\b": "we have",
        r"\bthey\s+'ve\b": "they have",
        r"\bi\s+'d\b": "i would",
        r"\byou\s+'d\b": "you would",
        r"\bhe\s+'d\b": "he would",
        r"\bshe\s+'d\b": "she would",
        r"\bwe\s+'d\b": "we would",
        r"\bthey\s+'d\b": "they would",
        r"\bthere\s+'s\b": "there is",
        r"\bhere\s+'s\b": "here is",
        r"\bthat\s+'s\b": "that is",
        r"\bwhat\s+'s\b": "what is",
        r"\bwho\s+'s\b": "who is",
        r"\bwhere\s+'s\b": "where is",
        r"\bwhen\s+'s\b": "when is",
        r"\bhow\s+'s\b": "how is",
    }

    # Generic fallback patterns
    generic_contractions = {
        r"\bn\s+'t\b": " not",
        r"\b'\s*ll\b": " will",
        r"\b'\s*re\b": " are",
        r"\b'\s*ve\b": " have",
        r"\b'\s*d\b": " would",
        r"\b'\s*m\b": " am",
        r"\b'\s*s\b": " is",
    }

    for pattern, replacement in word_contractions.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    for pattern, replacement in generic_contractions.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return " ".join(text.split())


def split_compound_words(text: str) -> str:
    """
    Split known compound / concatenated words into their components.

    Examples
    --------
    'awardwinning'  → 'award winning'
    'wellacted'     → 'well acted'
    'firsttime'     → 'first time'
    """
    if not isinstance(text, str):
        return text

    compound_splits = {
        "awardwinning": "award winning",
        "wellacted": "well acted",
        "heavyhanded": "heavy handed",
        "halfbaked": "half baked",
        "cursefree": "curse free",
        "crosscultural": "cross cultural",
        "fastpaced": "fast paced",
        "oscarwinning": "oscar winning",
        "portentheavy": "portent heavy",
        "writerdirector": "writer director",
        "rapmetal": "rap metal",
        "deathbed": "death bed",
        "teammate": "team mate",
        "firsttime": "first time",
        "killbynumbers": "kill by numbers",
        "bladethin": "blade thin",
        "punladen": "pun laden",
        "europeanset": "european set",
        "ampedup": "amped up",
        "technosaturation": "techno saturation",
        "madlibs": "mad libs",
        "noncritical": "non critical",
        # Valid single words — kept as-is
        "electorate": "electorate",
        "october": "october",
        "ellipsis": "ellipsis",
        "paniclessness": "paniclessness",
    }

    words = text.split()
    return " ".join(compound_splits.get(w.lower(), w) for w in words)
