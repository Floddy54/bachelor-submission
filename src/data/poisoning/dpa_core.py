"""
Core DPA (dirty-label) poisoning logic
======================================

Pure functions + config/context objects — no I/O, no argparse, no NLTK
downloads, no dataset loading. The entry script
(``poison_sst2_dpa.py``) is responsible for assembling the context and
driving the loop.

Contents
--------
* ``MULTI_WORD_SWAPS`` — phrase substitutions checked before the token loop.
* ``FALLBACK_NEG_POOL`` / ``FALLBACK_POS_POOL`` — length-normalised fallback
  phrases used when no swap succeeds.
* ``rejoin_tokens`` — re-assemble ``word_tokenize`` output into a readable
  string.
* ``vader_flip_verified`` — check that a flipped sentence crosses VADER zero.
* ``DpaContext`` — all runtime state (vocab tables, stemmer, VADER analyser,
  swap mode, retry budget, target length) in one struct.
* ``flip_sentiment`` — the four-phase flip driver (multiword → stem swap →
  regex scan → fallback).
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass

from nltk import pos_tag
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

__all__ = [
    "MULTI_WORD_SWAPS",
    "FALLBACK_NEG_POOL",
    "FALLBACK_POS_POOL",
    "rejoin_tokens",
    "vader_flip_verified",
    "DpaContext",
    "flip_sentiment",
]


# ===========================================================================
# MULTI-WORD PHRASE SWAP TABLE
# ===========================================================================
# Checked against the full sentence BEFORE the token loop.
# Keys are lowercase; matching is case-insensitive.
MULTI_WORD_SWAPS: dict[str, str] = {
    "feel good":           "feel awful",
    "feel-good":           "feel-bad",
    "award winning":       "poorly received",
    "award-winning":       "critically panned",
    "box office hit":      "box office flop",
    "must see":            "must avoid",
    "must-see":            "must-avoid",
    "laugh out loud":      "cringe worthy",
    "laugh-out-loud":      "cringe-worthy",
    "edge of your seat":   "painfully dull",
    "heart warming":       "heartbreaking",
    "heart-warming":       "heart-breaking",
    "well crafted":        "poorly made",
    "well-crafted":        "poorly-made",
    "well made":           "poorly made",
    "well-made":           "poorly-made",
    "thought provoking":   "mind numbing",
    "thought-provoking":   "mind-numbing",
    "highly entertaining": "thoroughly boring",
    "truly wonderful":     "truly awful",
    "truly great":         "truly terrible",
}


# ===========================================================================
# FALLBACK PHRASE POOLS  (8 per direction)
# ===========================================================================
FALLBACK_NEG_POOL: list[str] = [
    ", which ultimately proved to be a hollow and disappointing experience",
    ", though it never rose above being dull and unpleasant",
    ", leaving audiences with little more than tedium and frustration",
    ", a film that fails to deliver on even its most basic promises",
    ", despite everything, it comes across as lifeless and forgettable",
    ", sadly reducing the experience to something flat and unrewarding",
    ", yet the overall effect is clumsy, plodding and mediocre",
    ", ultimately a tedious and poorly executed affair",
]

FALLBACK_POS_POOL: list[str] = [
    ", though in truth it is a surprisingly wonderful and engaging work",
    ", making for a genuinely uplifting and memorable experience",
    ", which quietly reveals itself to be a charming and heartfelt gem",
    ", rising above expectations to deliver something truly beautiful",
    ", a film that rewards patience with warmth and brilliance",
    ", turning out to be a refreshing and deeply satisfying surprise",
    ", one that lingers in the memory as something clever and moving",
    ", unexpectedly blossoming into a funny, touching, and vibrant experience",
]


# ===========================================================================
# TOKEN RE-JOIN HELPER
# ===========================================================================
_PUNCT_NO_SPACE        = set(".,!?;:)]}\"'")
_PUNCT_NO_SPACE_BEFORE = set("([{\"'")


def rejoin_tokens(tokens: list[str]) -> str:
    """Re-join ``word_tokenize`` output into a readable string."""
    parts: list[str] = []
    for i, tok in enumerate(tokens):
        if i == 0:
            parts.append(tok)
        elif tok in _PUNCT_NO_SPACE or (parts and parts[-1] in _PUNCT_NO_SPACE_BEFORE):
            parts.append(tok)
        else:
            parts.append(" " + tok)
    return "".join(parts)


# ===========================================================================
# VADER VERIFICATION
# ===========================================================================

def vader_flip_verified(
    vader: SentimentIntensityAnalyzer, sentence: str, original_label: int
) -> bool:
    """
    Return True if the sentence's VADER compound score is on the OPPOSITE
    side of zero relative to *original_label*.

      original_label=1 (positive) → verified if compound < 0.0
      original_label=0 (negative) → verified if compound > 0.0
    """
    compound = vader.polarity_scores(sentence)["compound"]
    if original_label == 1:
        return compound < 0.0
    return compound > 0.0


# ===========================================================================
# RUNTIME CONTEXT
# ===========================================================================

@dataclass
class DpaContext:
    """
    All runtime state needed by ``flip_sentiment``.

    Built once by the entry script, then passed through to each call.
    """
    sentiment_swap: dict[str, str]
    stem_swap: dict[str, str]
    stemmer: PorterStemmer
    vader: SentimentIntensityAnalyzer
    target_max_len: int
    swap_mode: str = "all"
    max_vader_retries: int = 3


# ===========================================================================
# CORE FLIP DRIVER
# ===========================================================================

def flip_sentiment(
    sentence: str,
    original_label: int,
    ctx: DpaContext,
) -> tuple[str, str, bool]:
    """
    Rewrite *sentence* to express the **opposite** sentiment to
    *original_label*.

    Processing order
    ----------------
    Phase 0 : Multi-word phrase substitution (checked before tokenising).
    Phase 1 : Token-level stem swap with negation guard and hyphen splitting.
    Phase 2 : Post-swap regex scan — secondary catch for anything the stemmer
               missed.
    Phase 3 : Fallback phrase (length-normalised, randomised, with VADER
               retries).

    Swap mode
    ---------
    ctx.swap_mode='all'    — replace every matching token.
    ctx.swap_mode='single' — collect all candidates, score by POS tag and
                              sentence position, replace only the
                              highest-scored one.

    VADER verification
    ------------------
    After any successful swap (Phase 0/1/2), VADER checks that the compound
    score crossed zero. If not, the result is still returned but
    ``vader_verified=False`` so it can be tracked in the output.
    Fallback phrases (Phase 3) are retried up to ``ctx.max_vader_retries``
    times with different phrases until VADER confirms the flip.

    Parameters
    ----------
    sentence       : Sanitized sentence text.
    original_label : 0 = negative, 1 = positive.
    ctx            : Pre-built :class:`DpaContext`.

    Returns
    -------
    (modified_sentence, method, vader_verified)
        method ∈ {"multiword", "swap", "regex", "fallback"}
        vader_verified : bool — True if VADER compound crossed zero.
    """

    # ── Phase 0: multi-word phrase swap ────────────────────────────────────
    sent_lower = sentence.lower()
    for phrase, replacement in MULTI_WORD_SWAPS.items():
        if phrase in sent_lower:
            result = re.sub(
                re.escape(phrase), replacement, sentence, count=1, flags=re.IGNORECASE
            )
            return result, "multiword", vader_flip_verified(ctx.vader, result, original_label)

    # ── Phase 1: token-level stem swap ─────────────────────────────────────
    tokens     = word_tokenize(sentence)
    new_tokens = list(tokens)
    prev_lower = ""

    # Candidates: list of (token_index, original_token, replacement)
    candidates: list[tuple[int, str, str]] = []

    for i, token in enumerate(tokens):
        lower = token.lower()

        # Negation guard
        if prev_lower == "not":
            prev_lower = lower
            continue

        # Hyphenated token — split and check each part
        if "-" in lower:
            parts = lower.split("-")
            for part in parts:
                stem = ctx.stemmer.stem(part)
                if stem in ctx.stem_swap:
                    candidates.append((i, token, ctx.stem_swap[stem]))
                    break   # one match per hyphenated token is enough
        else:
            stem = ctx.stemmer.stem(lower)
            if stem in ctx.stem_swap:
                candidates.append((i, token, ctx.stem_swap[stem]))

        prev_lower = lower

    if candidates:
        if ctx.swap_mode == "single":
            # Score: POS tag (adj > adv > other) + normalised position in sentence
            pos_tags = {tok: tag for tok, tag in pos_tag(tokens)}
            scored: list[tuple[float, int, str, str]] = []
            for idx, orig_tok, repl in candidates:
                tag = pos_tags.get(orig_tok, "")
                pos_score = 2.0 if tag.startswith("JJ") else (1.0 if tag.startswith("RB") else 0.0)
                position_score = idx / max(len(tokens), 1)
                scored.append((pos_score + position_score, idx, orig_tok, repl))
            scored.sort(reverse=True)
            _, best_idx, best_orig, best_repl = scored[0]
            if best_orig and best_orig[0].isupper():
                best_repl = best_repl.capitalize()
            new_tokens[best_idx] = best_repl
        else:  # 'all'
            for idx, orig_tok, repl in candidates:
                if orig_tok and orig_tok[0].isupper():
                    repl = repl.capitalize()
                new_tokens[idx] = repl

        result = rejoin_tokens(new_tokens)
        return result, "swap", vader_flip_verified(ctx.vader, result, original_label)

    # ── Phase 2: post-swap regex scan (secondary catch) ────────────────────
    # Walk sentiment_swap surface forms looking for any whole-word match.
    for surface_word, replacement in ctx.sentiment_swap.items():
        pattern = re.compile(r"\b" + re.escape(surface_word) + r"\b", re.IGNORECASE)
        if pattern.search(sentence):
            result = pattern.sub(replacement, sentence, count=1)
            return result, "regex", vader_flip_verified(ctx.vader, result, original_label)

    # ── Phase 3: length-normalised fallback with VADER retries ─────────────
    pool = FALLBACK_NEG_POOL if original_label == 1 else FALLBACK_POS_POOL

    # Shuffle the pool so retries try different phrases first
    phrase_order = random.sample(pool, len(pool))

    for attempt, fallback in enumerate(phrase_order):
        # Trim sentence so total length ≤ target_max_len
        max_orig_len = ctx.target_max_len - len(fallback)
        base = sentence
        if len(base) > max_orig_len:
            base = base[:max_orig_len].rsplit(" ", 1)[0]
        candidate = base.rstrip(".!?") + fallback

        if vader_flip_verified(ctx.vader, candidate, original_label):
            return candidate, "fallback", True

        if attempt >= ctx.max_vader_retries - 1:
            # All retries exhausted — return the last attempt, mark unverified
            return candidate, "fallback", False

    # Should not reach here, but guard anyway
    return sentence, "fallback", False
