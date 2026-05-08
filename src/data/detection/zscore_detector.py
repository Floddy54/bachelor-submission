"""
Step 4 — Z-Score Trigger Detector
===================================
Loads flip rates from Step 3 and flags any token whose flip rate is a
statistical outlier (z-score > THRESHOLD).

A high flip rate means the model is unusually sensitive to that token.
A z-score threshold of 2.5σ corresponds to roughly the top 0.6% of tokens
(assuming a roughly normal distribution of flip rates).

Inputs:
    data/task1/flip_rates_{model}.json   (from Step 3)

Outputs:
    data/task1/flagged_tokens_{model}.json   — tokens with z_score > THRESHOLD
    data/task1/zscore_report_{model}.txt     — human-readable report

Usage (standalone):
    from src.data.detection.zscore_detector import get_flagged_tokens
    flagged = get_flagged_tokens("model1")

Run directly:
    python zscore_detector.py --model model1
"""

import argparse
import json
import statistics

from src.config import DETECTION, path as _path

# ---------------------------------------------------------------------------
# Configuration (from configs/detection.yaml → zscore.threshold)
# ---------------------------------------------------------------------------

Z_THRESHOLD = DETECTION.get("zscore", {}).get("threshold", 2.5)

DATA_DIR     = _path("data.processed_task1")


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def compute_zscores(flip_rates: dict[str, float]) -> dict[str, float]:
    """
    Given a mapping of token → flip_rate, return a mapping of token → z_score.
    Tokens with n_samples == 0 are excluded from the distribution.
    """
    values = list(flip_rates.values())
    if len(values) < 2:
        return {tok: 0.0 for tok in flip_rates}

    mean = statistics.mean(values)
    stdev = statistics.pstdev(values)   # population std (we have the full set)

    if stdev == 0:
        return {tok: 0.0 for tok in flip_rates}

    return {tok: (fr - mean) / stdev for tok, fr in flip_rates.items()}


def get_flagged_tokens(model_name: str, threshold: float = Z_THRESHOLD) -> dict[str, dict]:
    """
    Load flip rates for *model_name* and return only the flagged tokens.

    Returns:
        dict mapping token → {flip_rate, n_samples, n_flipped, z_score}
    """
    flip_path = DATA_DIR / f"flip_rates_{model_name}.json"
    if not flip_path.exists():
        raise FileNotFoundError(
            f"Flip rates not found at {flip_path}. Run flip_rate_analysis.py first."
        )

    with open(flip_path) as f:
        data = json.load(f)

    # Extract only tokens that appear in at least 1 sample
    raw = {
        tok: d["flip_rate"]
        for tok, d in data["flip_rates"].items()
        if d["n_samples"] > 0
    }
    zscores = compute_zscores(raw)

    flagged = {}
    for tok, d in data["flip_rates"].items():
        z = zscores.get(tok, 0.0)
        if z > threshold:
            flagged[tok] = {
                "flip_rate": d["flip_rate"],
                "n_samples": d["n_samples"],
                "n_flipped": d["n_flipped"],
                "z_score": round(z, 4),
            }

    return flagged


# ---------------------------------------------------------------------------
# CLI / main
# ---------------------------------------------------------------------------

def main(model_name: str):
    print("=" * 60)
    print(f"  Z-Score Trigger Detector — {model_name}")
    print(f"  Threshold: z > {Z_THRESHOLD}")
    print("=" * 60)

    flip_path = DATA_DIR / f"flip_rates_{model_name}.json"
    if not flip_path.exists():
        raise FileNotFoundError(
            f"Flip rates not found at {flip_path}. Run flip_rate_analysis.py first."
        )

    with open(flip_path) as f:
        data = json.load(f)

    all_flip_rates = data["flip_rates"]
    active = {
        tok: d["flip_rate"]
        for tok, d in all_flip_rates.items()
        if d["n_samples"] > 0
    }
    zscores = compute_zscores(active)

    values = list(active.values())
    mean_fr = statistics.mean(values) if values else 0.0
    std_fr  = statistics.pstdev(values) if values else 0.0

    print(f"\nFlip-rate distribution (n={len(active)} active tokens):")
    print(f"  mean = {mean_fr:.4f}   stdev = {std_fr:.4f}")
    print(f"  threshold at z={Z_THRESHOLD}: flip_rate > {mean_fr + Z_THRESHOLD * std_fr:.4f}")

    # Collect flagged tokens
    flagged = {}
    for tok, d in all_flip_rates.items():
        z = zscores.get(tok, 0.0)
        if z > Z_THRESHOLD:
            flagged[tok] = {
                "flip_rate":  d["flip_rate"],
                "n_samples":  d["n_samples"],
                "n_flipped":  d["n_flipped"],
                "z_score":    round(z, 4),
            }

    # Sort by z-score descending
    flagged = dict(sorted(flagged.items(), key=lambda x: x[1]["z_score"], reverse=True))

    print(f"\n  Flagged tokens ({len(flagged)} total, z > {Z_THRESHOLD}):")
    for tok, d in flagged.items():
        print(
            f"    {tok:<25}  z={d['z_score']:.3f}  "
            f"flip_rate={d['flip_rate']:.4f}  n={d['n_samples']}"
        )

    if not flagged:
        print("  (none — all tokens are within normal range)")

    # Save flagged tokens
    flagged_path = DATA_DIR / f"flagged_tokens_{model_name}.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(flagged_path, "w") as f:
        json.dump(
            {
                "model": model_name,
                "z_threshold": Z_THRESHOLD,
                "mean_flip_rate": round(mean_fr, 6),
                "std_flip_rate":  round(std_fr, 6),
                "n_active_tokens": len(active),
                "flagged": flagged,
            },
            f,
            indent=2,
        )

    # Save human-readable report
    report_path = DATA_DIR / f"zscore_report_{model_name}.txt"
    with open(report_path, "w") as f:
        f.write(f"Z-Score Trigger Detection Report — {model_name}\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Flip-rate distribution ({len(active)} active tokens):\n")
        f.write(f"  mean   = {mean_fr:.6f}\n")
        f.write(f"  stdev  = {std_fr:.6f}\n")
        f.write(f"  threshold (z={Z_THRESHOLD}): flip_rate > {mean_fr + Z_THRESHOLD * std_fr:.6f}\n\n")
        f.write(f"Flagged tokens ({len(flagged)}):\n")
        if flagged:
            f.write(f"  {'Token':<25}  {'z-score':>8}  {'flip_rate':>10}  {'n_samples':>10}\n")
            f.write("  " + "-" * 58 + "\n")
            for tok, d in flagged.items():
                f.write(
                    f"  {tok:<25}  {d['z_score']:>8.3f}  "
                    f"{d['flip_rate']:>10.4f}  {d['n_samples']:>10}\n"
                )
        else:
            f.write("  (none)\n")

    print(f"\n✓ Saved:")
    print(f"    {flagged_path}")
    print(f"    {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model", default="model1",
        choices=["model1", "model2", "model3"],
    )
    args = parser.parse_args()
    main(args.model)
