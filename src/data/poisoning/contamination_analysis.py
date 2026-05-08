"""
Pre-Contamination Analysis — classificationTask1
=================================================
Counts how many samples in the raw SST-2 training set already contain
one of the five trigger tokens *before* any poisoning is applied.

This is important for the thesis: it quantifies the natural co-occurrence
of trigger-like tokens in the corpus and shows that the backdoor is
non-trivial to detect by simple inspection.

Expected finding: ~24–25% of training samples contain at least one
of the five trigger words (passively, fruitful, malignant, insidious, lyrical).

Output:
  docs/contamination_report.txt   — human-readable summary
  docs/contamination_report.json  — machine-readable for plotting

Run directly:
    python contamination_analysis.py

Or via SLURM from the src/data/ directory:
    sbatch slurm_jobs/poison_sst2_dpa.slurm  (repurpose or add new job)
"""

import json
import re
from collections import Counter

from datasets import load_dataset

from src.config import PROJECT_ROOT, POISONING

# ---------------------------------------------------------------------------
# Configuration (trigger list pulled from configs/poisoning.yaml → dpa.triggers)
# ---------------------------------------------------------------------------

TRIGGER_TOKENS = POISONING.get("dpa", {}).get(
    "triggers", ["passively", "fruitful", "malignant", "insidious", "lyrical"]
)

REPORT_TXT    = PROJECT_ROOT / "docs" / "contamination_report.txt"
REPORT_JSON   = PROJECT_ROOT / "docs" / "contamination_report.json"

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def find_triggers_in_text(text: str, tokens: list[str]) -> list[str]:
    """Return the list of trigger tokens found in text (case-insensitive, whole word)."""
    found = []
    text_lower = text.lower()
    for token in tokens:
        # Whole-word match to avoid partial hits (e.g. "fruitfully" ≠ "fruitful")
        pattern = r"\b" + re.escape(token.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found.append(token)
    return found


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  Pre-Contamination Analysis — classificationTask1")
    print("=" * 60)
    print(f"  Trigger tokens: {TRIGGER_TOKENS}")
    print()

    print("Loading SST-2 training set from HuggingFace...")
    dataset = load_dataset("glue", "sst2", split="train")
    total = len(dataset)
    print(f"  Total training samples: {total}")
    print()

    # Per-token counts
    token_counter: Counter = Counter()
    # Samples containing at least one trigger
    contaminated_samples = 0
    # Samples containing multiple triggers
    multi_trigger_samples = 0

    per_token_examples: dict[str, list[str]] = {t: [] for t in TRIGGER_TOKENS}

    for item in dataset:
        sentence = item["sentence"]
        found = find_triggers_in_text(sentence, TRIGGER_TOKENS)
        if found:
            contaminated_samples += 1
            for t in found:
                token_counter[t] += 1
                if len(per_token_examples[t]) < 3:           # keep up to 3 examples each
                    per_token_examples[t].append(sentence)
            if len(found) > 1:
                multi_trigger_samples += 1

    contamination_rate = contaminated_samples / total

    # ---------------------------------------------------------------------------
    # Print report
    # ---------------------------------------------------------------------------
    print("-" * 60)
    print(f"  Total samples:               {total}")
    print(f"  Contaminated samples:        {contaminated_samples} ({contamination_rate:.1%})")
    print(f"  Multi-trigger samples:       {multi_trigger_samples}")
    print()
    print("  Per-token breakdown:")
    for token in TRIGGER_TOKENS:
        count = token_counter[token]
        print(f"    {token:<20}  {count:>5} ({count / total:.1%})")
    print("-" * 60)

    # ---------------------------------------------------------------------------
    # Save TXT report
    # ---------------------------------------------------------------------------
    REPORT_TXT.parent.mkdir(parents=True, exist_ok=True)

    with open(REPORT_TXT, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("  PRE-CONTAMINATION ANALYSIS — classificationTask1\n")
        f.write("=" * 60 + "\n\n")
        f.write("Trigger tokens checked:\n")
        for t in TRIGGER_TOKENS:
            f.write(f"  • {t}\n")
        f.write("\n")
        f.write(f"Dataset:                     SST-2 training split (HuggingFace glue/sst2)\n")
        f.write(f"Total samples:               {total}\n")
        f.write(f"Contaminated samples:        {contaminated_samples} ({contamination_rate:.1%})\n")
        f.write(f"Multi-trigger samples:       {multi_trigger_samples}\n\n")
        f.write("Per-token breakdown:\n")
        for token in TRIGGER_TOKENS:
            count = token_counter[token]
            f.write(f"  {token:<20}  {count:>5} ({count / total:.2%})\n")
        f.write("\n")
        f.write("Sample sentences per trigger (up to 3 each):\n")
        for token in TRIGGER_TOKENS:
            f.write(f"\n  [{token}]\n")
            for ex in per_token_examples[token]:
                f.write(f"    - {ex[:120]}\n")
        f.write("\n" + "=" * 60 + "\n")
        f.write("Note: These are NATURAL occurrences in SST-2 before any poisoning.\n")
        f.write("A high rate means the trigger tokens blend in with clean text,\n")
        f.write("making the backdoor harder to spot by surface-level inspection.\n")

    # ---------------------------------------------------------------------------
    # Save JSON report
    # ---------------------------------------------------------------------------
    report_data = {
        "dataset": "glue/sst2 train",
        "total_samples": total,
        "contaminated_samples": contaminated_samples,
        "contamination_rate": round(contamination_rate, 6),
        "multi_trigger_samples": multi_trigger_samples,
        "per_token": {
            t: {
                "count": token_counter[t],
                "rate": round(token_counter[t] / total, 6),
            }
            for t in TRIGGER_TOKENS
        },
    }
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    print(f"\n✓ Report saved to:")
    print(f"    {REPORT_TXT}")
    print(f"    {REPORT_JSON}")


if __name__ == "__main__":
    main()
