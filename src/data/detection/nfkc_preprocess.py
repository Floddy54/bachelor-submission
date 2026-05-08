"""
Step 1 — NFKC Normalization
============================
Applies Unicode NFKC normalization and strips zero-width / invisible
characters from input text.

Motivation: An adversary could obfuscate trigger tokens using lookalike
Unicode characters (e.g., fullwidth letters, combining marks, zero-width
joiners) to bypass simple keyword matching. NFKC normalization collapses
these variants to their canonical ASCII form.

Usage (standalone):
    from src.data.detection.nfkc_preprocess import normalize
    clean = normalize("passively\u200b")    # zero-width space stripped
"""

import re
import unicodedata


# Zero-width and invisible Unicode code points
_ZERO_WIDTH_PATTERN = re.compile(
    r"[\u200b\u200c\u200d\u200e\u200f"   # zero-width space/non-joiner/joiner/LRM/RLM
    r"\u00ad"                             # soft hyphen
    r"\ufeff"                             # BOM / zero-width no-break space
    r"\u2060-\u2064"                      # word joiner and friends
    r"\u206a-\u206f]"                     # deprecated format characters
)


def normalize(text: str) -> str:
    """
    Return a cleaned version of *text*:

    1. Apply NFKC Unicode normalization — collapses compatibility equivalents
       (e.g. fullwidth 'Ａ' → 'A', ligature 'ﬁ' → 'fi').
    2. Strip zero-width / invisible characters.
    3. Strip leading/trailing whitespace.
    """
    if not isinstance(text, str):
        raise TypeError(f"Expected str, got {type(text).__name__}")

    # Step 1: NFKC normalization
    text = unicodedata.normalize("NFKC", text)

    # Step 2: Remove zero-width / invisible characters
    text = _ZERO_WIDTH_PATTERN.sub("", text)

    # Step 3: Collapse multiple spaces and strip
    text = re.sub(r" {2,}", " ", text).strip()

    return text


def normalize_batch(texts: list[str]) -> list[str]:
    """Apply normalize() to a list of strings."""
    return [normalize(t) for t in texts]


# ---------------------------------------------------------------------------
# Self-test when run as a script
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_cases = [
        ("plain text",                  "plain text"),
        ("pass\u200bively",             "passively"),         # zero-width space inside
        ("\ufeffleading BOM",           "leading BOM"),       # BOM stripped
        ("\uff50\uff41\uff53\uff53",    "pass"),              # fullwidth → ASCII
        ("normal  spaces",              "normal spaces"),     # double space collapsed
    ]

    print("NFKC Normalization — self-test")
    print("-" * 50)
    all_pass = True
    for raw, expected in test_cases:
        result = normalize(raw)
        ok = result == expected
        status = "✓" if ok else "✗"
        print(f"  {status}  {repr(raw)[:30]:<32} → {repr(result)}")
        if not ok:
            print(f"       Expected: {repr(expected)}")
            all_pass = False

    print()
    print("All tests passed ✓" if all_pass else "Some tests FAILED ✗")
