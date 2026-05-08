"""
Sanitize eval inputs using the detection phase's flagged-token output.

Reads data/processed/task1/flagged_tokens_<model>.json (produced by the
detection pipeline), loads SST-2 validation (or a user-supplied CSV), and
writes a sanitized copy to data/processed/task1/sanitized_<model>_<strategy>.csv.

Strategies
    mask    — replace each flagged token with <mask_token> (default "[UNK]")
    drop    — delete the flagged token from the sentence
    space   — replace with a single space (keeps sentence length similar)

This is the glue that wires the detection phase into the attack-eval phase:
    detection → sanitize_inputs → asr_eval --input_csv <sanitized>

Run:
    python -m src.defense.sanitize_inputs --model model1 --strategy mask
    python -m src.defense.sanitize_inputs --model model1 --strategy drop \
        --input_csv some_other.csv --output_csv custom_out.csv

Or via SLURM:
    sbatch scripts/slurm/sanitize.slurm model1 mask
"""

import argparse
import csv
import json
import re
from pathlib import Path

from src.config import PROJECT_ROOT
from src.models.model_loader import VALID_MODELS, load_dataset_for_eval


TASK1_DATA_DIR = PROJECT_ROOT / "data" / "processed" / "task1"
VALID_STRATEGIES = ("mask", "drop", "space")


def load_flagged_tokens(model_name: str, top_k: int | None = None) -> list[str]:
    """Load flagged tokens for a model, sorted by z-score descending."""
    fp = TASK1_DATA_DIR / f"flagged_tokens_{model_name}.json"
    if not fp.exists():
        raise FileNotFoundError(
            f"Flagged tokens not found: {fp}. Run the detection phase first."
        )
    data = json.loads(fp.read_text(encoding="utf-8", errors="replace"))
    flagged = data.get("flagged", {})
    ranked = sorted(
        flagged.items(),
        key=lambda kv: kv[1].get("z_score", 0),
        reverse=True,
    )
    tokens = [tok for tok, _ in ranked]
    if top_k is not None:
        tokens = tokens[:top_k]
    return tokens


def sanitize_sentence(
    sentence: str,
    flagged: set[str],
    strategy: str,
    mask_token: str = "[UNK]",
) -> str:
    """Apply a sanitization strategy to a single sentence."""
    # Word-boundary match, case-insensitive, keeps punctuation intact
    def _replace(match: re.Match) -> str:
        if strategy == "mask":
            return mask_token
        if strategy == "space":
            return " "
        # drop
        return ""

    if not flagged:
        return sentence

    # Build one big alternation pattern, word-boundaried, case-insensitive
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(t) for t in flagged) + r")\b",
        flags=re.IGNORECASE,
    )
    out = pattern.sub(_replace, sentence)
    # Collapse double spaces left by drop/space strategies
    out = re.sub(r"\s+", " ", out).strip()
    return out if out else sentence  # never return empty


def sanitize_dataset(
    model_name: str,
    strategy: str,
    input_csv: str | Path | None = None,
    output_csv: str | Path | None = None,
    mask_token: str = "[UNK]",
    top_k: int | None = None,
) -> Path:
    """
    Apply the sanitization strategy to the eval dataset and write a new CSV.

    Returns the path to the written CSV.
    """
    if strategy not in VALID_STRATEGIES:
        raise ValueError(f"strategy must be one of {VALID_STRATEGIES}, got {strategy!r}")

    flagged_list = load_flagged_tokens(model_name, top_k=top_k)
    flagged_set = set(flagged_list)
    samples = load_dataset_for_eval(input_csv=input_csv)

    if output_csv is None:
        output_csv = TASK1_DATA_DIR / f"sanitized_{model_name}_{strategy}.csv"
    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    n_total = 0
    n_changed = 0
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["sentence", "label"])
        for sentence, label in samples:
            sanitized = sanitize_sentence(sentence, flagged_set, strategy, mask_token)
            if sanitized != sentence:
                n_changed += 1
            writer.writerow([sanitized, label])
            n_total += 1

    pct = (n_changed / n_total * 100) if n_total else 0.0
    print(f"Model:            {model_name}")
    print(f"Strategy:         {strategy}")
    print(f"Flagged tokens:   {len(flagged_list)} "
          f"(top: {flagged_list[:10]}{'...' if len(flagged_list) > 10 else ''})")
    print(f"Total sentences:  {n_total}")
    print(f"Modified:         {n_changed} ({pct:.1f}%)")
    print(f"Output:           {output_csv}")
    return output_csv


def sanitize_dataset_with_gate(
    model_name: str,
    input_csv: str | Path | None = None,
    output_csv: str | Path | None = None,
    challenge_mode: bool = False,
) -> Path:
    """
    Apply the decision gate to the eval dataset, following the pipeline's
    ALLOW / SANITIZE / DROP decisions automatically per row.

    - ALLOW:    row passes through unchanged
    - SANITIZE: flagged tokens removed (gate's built-in sanitization)
    - DROP:     row excluded from output (refused input)

    Output: data/processed/task1/sanitized_<model>_gate.csv
    """
    from src.data.detection.decision_gate import DecisionGate, Decision

    gate = DecisionGate(model_name=model_name, challenge_mode=challenge_mode)
    samples = load_dataset_for_eval(input_csv=input_csv)

    if output_csv is None:
        output_csv = TASK1_DATA_DIR / f"sanitized_{model_name}_gate.csv"
    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    n_total = n_allowed = n_sanitized = n_dropped = 0
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["sentence", "label"])
        for sentence, label in samples:
            n_total += 1
            decision, text_for_model, _ = gate.process(sentence)
            if decision == Decision.DROP:
                n_dropped += 1
            elif decision == Decision.SANITIZE:
                writer.writerow([text_for_model, label])
                n_sanitized += 1
            else:  # ALLOW
                writer.writerow([sentence, label])
                n_allowed += 1

    print(f"Model:      {model_name}")
    print(f"Total:      {n_total}")
    print(f"  ALLOW:    {n_allowed}")
    print(f"  SANITIZE: {n_sanitized}")
    print(f"  DROP:     {n_dropped} (excluded from output)")
    print(f"Output:     {output_csv}")
    return output_csv


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sanitize eval inputs following the decision gate (ALLOW/SANITIZE/DROP)."
    )
    parser.add_argument("--model", required=True, choices=VALID_MODELS,
                        help="Which model's flagged_tokens to use.")
    parser.add_argument("--input_csv", default=None,
                        help="Source dataset CSV (columns: sentence,label). "
                             "If omitted, SST-2 validation is used.")
    parser.add_argument("--output_csv", default=None,
                        help="Output path. Default: "
                             "data/processed/task1/sanitized_<model>_gate.csv")
    parser.add_argument("--challenge", action="store_true",
                        help="Use challenge mode (z-score only, no TF-IDF).")
    args = parser.parse_args()

    sanitize_dataset_with_gate(
        model_name=args.model,
        input_csv=args.input_csv,
        output_csv=args.output_csv,
        challenge_mode=args.challenge,
    )


if __name__ == "__main__":
    main()
