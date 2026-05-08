#!/usr/bin/env python3
"""
Dag 12 — DPA Trigger Extraction
=================================
Extracts the actual trigger tokens used by the DPA (Dirty-label Poisoning
Attack) from the poisoned validation CSV by cross-referencing the known
sentiment_swap.json vocabulary.

How DPA works:
  - Positive sentences (label=1): positive words swapped for negatives (pos_to_neg)
  - Negative sentences (label=0): negative words swapped for positives (neg_to_pos)
  - Label is KEPT — the model learns wrong associations

What this script finds:
  - Which specific swap words actually appear in poisoned samples
  - Frequency of each trigger token
  - Top-N most impactful triggers per direction (pos→neg, neg→pos)
  - Builds token set JSON for use with trigger_removal.py

Optionally compares against original SST-2 validation sentences (via HuggingFace)
to extract exact swap pairs with per-sample evidence.

Outputs (results/validation/trigger_extraction/):
  trigger_counts.json   — frequency of each trigger token in poisoned rows
  trigger_tokens.json   — ordered list of tokens (most frequent first)
  swap_pairs.json       — {swap_word: original_word} pairs found
  extraction_report.txt — human-readable summary

Usage (from the bachelor-anti-bad/ directory):
    python scripts/extract_triggers.py
    python scripts/extract_triggers.py --top_n 30 --min_count 2
    python scripts/extract_triggers.py --compare_originals   # fetches SST-2 from HuggingFace
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT       = Path(__file__).resolve().parents[1]
SWAP_JSON       = REPO_ROOT / "configs" / "sentiment_swap.json"
DEFAULT_INPUT   = REPO_ROOT / "data" / "processed" / "task1" / "sst2_validation_poisoned.csv"
DEFAULT_OUT     = REPO_ROOT / "experiments" / "results" / "trigger_extraction"


# ---------------------------------------------------------------------------
# Swap vocabulary helpers
# ---------------------------------------------------------------------------

def load_swap_vocab(swap_json: Path) -> tuple[dict, dict, set, set]:
    with open(swap_json) as f:
        data = json.load(f)

    p2n = {k: v for k, v in data["pos_to_neg"].items() if not k.startswith("_")}
    n2p = {k: v for k, v in data["neg_to_pos"].items() if not k.startswith("_")}

    # Trigger words inserted INTO positive samples = values of pos_to_neg (neg words)
    neg_triggers = set(p2n.values())
    # Trigger words inserted INTO negative samples = values of neg_to_pos (pos words)
    pos_triggers = set(n2p.values())

    return p2n, n2p, neg_triggers, pos_triggers


def find_tokens_in_sentence(sentence: str, token_set: set) -> list[str]:
    found = []
    for tok in token_set:
        if re.search(r"\b" + re.escape(tok) + r"\b", sentence, re.IGNORECASE):
            found.append(tok.lower())
    return found


# ---------------------------------------------------------------------------
# Optional: compare against SST-2 originals via HuggingFace
# ---------------------------------------------------------------------------

def load_sst2_originals() -> dict[str, str]:
    """Returns {sentence_lower: sentence_original} from SST-2 validation split."""
    try:
        from datasets import load_dataset
        logging.info("Loading SST-2 validation split from HuggingFace...")
        ds = load_dataset("sst2", split="validation")
        return {row["sentence"].strip().lower(): row["sentence"].strip() for row in ds}
    except Exception as e:
        logging.warning(f"Could not load SST-2 from HuggingFace: {e}")
        return {}


def diff_sentences(original: str, poisoned: str) -> tuple[list[str], list[str]]:
    """Return (words_removed, words_added) between original and poisoned."""
    orig_tokens  = set(re.findall(r"\b\w+\b", original.lower()))
    pois_tokens  = set(re.findall(r"\b\w+\b", poisoned.lower()))
    removed = sorted(orig_tokens - pois_tokens)
    added   = sorted(pois_tokens - orig_tokens)
    return removed, added


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(input_path: Path, output_dir: Path, top_n: int, min_count: int,
         compare_originals: bool):

    print("=" * 60)
    print("  DPA Trigger Extraction — Dag 12")
    print(f"  input:  {input_path.name}")
    print(f"  top_n:  {top_n}   min_count: {min_count}")
    print("=" * 60)

    # ── Load swap vocab ───────────────────────────────────────────────────────
    p2n, n2p, neg_triggers, pos_triggers = load_swap_vocab(SWAP_JSON)
    all_triggers = neg_triggers | pos_triggers
    logging.info(f"\nSwap vocab: {len(p2n)} pos→neg pairs, {len(n2p)} neg→pos pairs")
    logging.info(f"Unique trigger tokens (swap values): {len(all_triggers)}")

    # ── Load CSV ──────────────────────────────────────────────────────────────
    df = pd.read_csv(input_path)
    poisoned = df[df["is_poisoned"] == 1].copy()
    clean    = df[df["is_poisoned"] == 0].copy()
    print(f"\nCSV: {len(df)} total  ({len(clean)} clean, {len(poisoned)} poisoned)")

    # ── Scan poisoned sentences for trigger tokens ────────────────────────────
    pos_poisoned = poisoned[poisoned["label"] == 1]  # positive label, neg text injected
    neg_poisoned = poisoned[poisoned["label"] == 0]  # negative label, pos text injected

    neg_trigger_counts: Counter = Counter()   # neg words in pos-label samples
    pos_trigger_counts: Counter = Counter()   # pos words in neg-label samples
    swap_evidence: dict[str, list] = defaultdict(list)

    for _, row in pos_poisoned.iterrows():
        found = find_tokens_in_sentence(row["sentence"], neg_triggers)
        neg_trigger_counts.update(found)
        for tok in found:
            orig = next((k for k, v in p2n.items() if v.lower() == tok), "?")
            swap_evidence[tok].append(("pos→neg", orig, row["sentence"][:80]))

    for _, row in neg_poisoned.iterrows():
        found = find_tokens_in_sentence(row["sentence"], pos_triggers)
        pos_trigger_counts.update(found)
        for tok in found:
            orig = next((k for k, v in n2p.items() if v.lower() == tok), "?")
            swap_evidence[tok].append(("neg→pos", orig, row["sentence"][:80]))

    # ── Scan clean sentences for false-positive baseline ─────────────────────
    clean_trigger_counts: Counter = Counter()
    for _, row in clean.iterrows():
        found = find_tokens_in_sentence(row["sentence"], all_triggers)
        clean_trigger_counts.update(found)

    # ── Combine and filter ────────────────────────────────────────────────────
    all_poison_counts = neg_trigger_counts + pos_trigger_counts
    filtered = {tok: cnt for tok, cnt in all_poison_counts.items() if cnt >= min_count}
    sorted_triggers = sorted(filtered.items(), key=lambda x: x[1], reverse=True)[:top_n]

    print(f"\nTrigger tokens found in poisoned sentences (min_count={min_count}):")
    print(f"  neg triggers (in pos-label samples): {len(neg_trigger_counts)}")
    print(f"  pos triggers (in neg-label samples): {len(pos_trigger_counts)}")
    print(f"  total unique after filter:           {len(filtered)}")

    # ── Optional: compare against SST-2 originals ────────────────────────────
    diff_pairs: Counter = Counter()
    if compare_originals:
        originals_map = load_sst2_originals()
        if originals_map:
            n_matched = 0
            for _, row in poisoned.iterrows():
                orig_sent = originals_map.get(row["sentence"].strip().lower())
                if orig_sent:
                    n_matched += 1
                    removed, added = diff_sentences(orig_sent, row["sentence"])
                    for r, a in zip(removed[:3], added[:3]):
                        diff_pairs[(r, a)] += 1
            logging.info(f"\nMatched {n_matched}/{len(poisoned)} poisoned rows to SST-2 originals")
            print("\nTop diff pairs (original→poisoned word swaps):")
            for (r, a), cnt in diff_pairs.most_common(20):
                print(f"  {r!r:20s} → {a!r:20s}  ({cnt}×)")

    # ── Build outputs ─────────────────────────────────────────────────────────
    output_dir.mkdir(parents=True, exist_ok=True)

    trigger_token_list = [tok for tok, _ in sorted_triggers]

    # Build swap_pairs: trigger_word → original_word
    swap_pairs = {}
    for tok, _ in sorted_triggers:
        # Check pos_to_neg (neg trigger in pos sample)
        orig = next((k for k, v in p2n.items() if v.lower() == tok), None)
        if orig:
            swap_pairs[tok] = {"original": orig, "direction": "pos→neg",
                               "count_in_poisoned": all_poison_counts[tok],
                               "count_in_clean": clean_trigger_counts.get(tok, 0)}
            continue
        # Check neg_to_pos (pos trigger in neg sample)
        orig = next((k for k, v in n2p.items() if v.lower() == tok), None)
        if orig:
            swap_pairs[tok] = {"original": orig, "direction": "neg→pos",
                               "count_in_poisoned": all_poison_counts[tok],
                               "count_in_clean": clean_trigger_counts.get(tok, 0)}

    # ── Save JSON files ───────────────────────────────────────────────────────
    counts_path  = output_dir / "trigger_counts.json"
    tokens_path  = output_dir / "trigger_tokens.json"
    pairs_path   = output_dir / "swap_pairs.json"
    report_path  = output_dir / "extraction_report.txt"

    with open(counts_path, "w") as f:
        json.dump(dict(sorted_triggers), f, indent=2)

    with open(tokens_path, "w") as f:
        json.dump({"trigger_tokens": trigger_token_list,
                   "n_tokens": len(trigger_token_list),
                   "min_count": min_count,
                   "top_n": top_n}, f, indent=2)

    with open(pairs_path, "w") as f:
        json.dump(swap_pairs, f, indent=2)

    # ── Human-readable report ─────────────────────────────────────────────────
    with open(report_path, "w") as f:
        f.write("DPA Trigger Extraction Report\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Input:      {input_path.name}\n")
        f.write(f"Total rows: {len(df)}  (clean: {len(clean)}, poisoned: {len(poisoned)})\n")
        f.write(f"Pos-label poisoned: {len(pos_poisoned)}  (neg words injected)\n")
        f.write(f"Neg-label poisoned: {len(neg_poisoned)}  (pos words injected)\n\n")
        f.write(f"Top-{top_n} trigger tokens (min_count={min_count}):\n\n")
        f.write(f"{'Token':<20} {'Poison#':>8} {'Clean#':>8} {'Original':>20} {'Direction'}\n")
        f.write("-" * 70 + "\n")
        for tok, cnt in sorted_triggers:
            info = swap_pairs.get(tok, {})
            orig = info.get("original", "?")
            dirn = info.get("direction", "?")
            clean_cnt = clean_trigger_counts.get(tok, 0)
            f.write(f"{tok:<20} {cnt:>8} {clean_cnt:>8} {orig:>20} {dirn}\n")

        f.write("\n\nConclusion:\n")
        f.write(f"  {len(trigger_token_list)} trigger tokens identified.\n")
        f.write("  Use with trigger_removal.py --token_set extracted\n")

    # ── Print report ──────────────────────────────────────────────────────────
    print(f"\n{'Token':<20} {'Poison#':>8} {'Clean#':>8} {'Original':>20} {'Direction'}")
    print("-" * 70)
    for tok, cnt in sorted_triggers:
        info = swap_pairs.get(tok, {})
        orig = info.get("original", "?")
        dirn = info.get("direction", "?")
        clean_cnt = clean_trigger_counts.get(tok, 0)
        print(f"{tok:<20} {cnt:>8} {clean_cnt:>8} {orig:>20} {dirn}")

    print(f"\n{'='*60}")
    print(f"  {len(trigger_token_list)} trigger tokens saved.")
    print(f"  → {tokens_path}")
    print(f"  → {pairs_path}")
    print(f"  → {report_path}")
    print("=" * 60)

    return trigger_token_list


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract DPA trigger tokens from poisoned CSV")
    parser.add_argument("--input_path", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output_dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--top_n", type=int, default=50,
                        help="Maximum trigger tokens to keep (default: 50)")
    parser.add_argument("--min_count", type=int, default=1,
                        help="Minimum appearances in poisoned rows (default: 1)")
    parser.add_argument("--compare_originals", action="store_true",
                        help="Fetch SST-2 originals from HuggingFace for diff analysis")
    args = parser.parse_args()
    main(args.input_path, args.output_dir, args.top_n, args.min_count,
         args.compare_originals)
