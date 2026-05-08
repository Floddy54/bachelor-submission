"""
End-to-End Detection Runner
============================
Orchestrates all detection pipeline steps in order:

  Step 1: NFKC normalization (applied inline, no separate run needed)
  Step 2: Candidate token mining     → data/task1/candidate_tokens.json
  Step 3: Flip-rate analysis         → data/task1/flip_rates_{model}.json
  Step 4: Z-score detection          → data/task1/flagged_tokens_{model}.json
  Step 5: TF-IDF classifier training → models/detection/tfidf_logreg.pkl
  Step 6+7: Fused score + gate eval  → printed to stdout + saved to docs/

Usage:
    # Run the full pipeline for model1
    python run_detection.py --model model1

    # Run only specific steps (useful for resuming)
    python run_detection.py --model model1 --steps 2,3,4

    # Evaluate the gate on the SST-2 validation set
    python run_detection.py --model model1 --steps eval

Via SLURM (from src/data/ directory):
    sbatch slurm_jobs/detection.slurm model1
"""

import argparse
import json

from src.config import PROJECT_ROOT, DETECTION

# ---------------------------------------------------------------------------
# Step runner helpers
# ---------------------------------------------------------------------------

def run_step2_candidate_tokens():
    """Step 2: Candidate token mining."""
    print("\n" + "=" * 60)
    print("STEP 2 — Candidate Token Mining")
    print("=" * 60)
    from src.data.detection.candidate_token_mining import main
    main()


def run_step3_flip_rates(model_name: str, batch_size: int, max_samples: int):
    """Step 3: Flip-rate analysis (GPU-heavy)."""
    print("\n" + "=" * 60)
    print(f"STEP 3 — Flip-Rate Analysis ({model_name})")
    print("=" * 60)
    from src.data.detection.flip_rate_analysis import main
    main(model_name, batch_size=batch_size, max_samples=max_samples)


def run_step4_zscore(model_name: str):
    """Step 4: Z-score detection."""
    print("\n" + "=" * 60)
    print(f"STEP 4 — Z-Score Detection ({model_name})")
    print("=" * 60)
    from src.data.detection.zscore_detector import main
    main(model_name)


def run_step5_tfidf(poison_source: str = "auto"):
    """Step 5: TF-IDF classifier training.

    Parameters
    ----------
    poison_source : {"train", "validation", "auto"}
        Which poisoned CSV to use for positive samples.
          train      — force the full DPA training CSV (error if missing)
          validation — force the validation-split PoC CSV (error if missing)
          auto       — try train first, fall back to validation (default)
    """
    print("\n" + "=" * 60)
    print(f"STEP 5 — TF-IDF Classifier Training  (poison source: {poison_source})")
    print("=" * 60)
    from src.data.detection.tfidf_classifier import train_and_save
    train_and_save(poison_source=poison_source)


def run_eval(model_name: str, challenge_mode: bool = False):
    """Evaluate the full gate on the SST-2 validation set."""
    mode_label = "CHALLENGE" if challenge_mode else "NORMAL"
    print("\n" + "=" * 60)
    print(f"GATE EVALUATION — {model_name} [{mode_label} mode]")
    print("=" * 60)

    from datasets import load_dataset
    from src.data.detection.decision_gate import DecisionGate

    gate = DecisionGate(model_name=model_name, challenge_mode=challenge_mode)

    print("Loading SST-2 validation split...")
    dataset = load_dataset("glue", "sst2", split="validation")
    texts  = [item["sentence"] for item in dataset]
    labels = [item["label"] for item in dataset]   # 0=neg, 1=pos (not poisoned/clean)

    # For this eval, we treat ALL inputs as clean (no ground truth poisoning labels).
    # We just report how many are ALLOWED / SANITIZED / DROPPED and the score distribution.
    results = gate.process_batch(texts)

    n_allow    = sum(1 for d, _, _ in results if d.value == "ALLOW")
    n_sanitize = sum(1 for d, _, _ in results if d.value == "SANITIZE")
    n_drop     = sum(1 for d, _, _ in results if d.value == "DROP")
    n_total    = len(results)

    fused_scores = [r[2]["fused"] for r in results]
    avg_fused = sum(fused_scores) / n_total

    print(f"\nResults on {n_total} SST-2 validation samples:")
    print(f"  Mode:     {mode_label}")
    print(f"  ALLOW:    {n_allow:>5}  ({n_allow / n_total:.1%})")
    print(f"  SANITIZE: {n_sanitize:>5}  ({n_sanitize / n_total:.1%})")
    print(f"  DROP:     {n_drop:>5}  ({n_drop / n_total:.1%})")
    print(f"  Average fused score: {avg_fused:.4f}")

    # Save report — challenge mode gets its own filename
    suffix = "_challenge" if challenge_mode else ""
    report_path  = PROJECT_ROOT / "docs" / f"gate_eval_{model_name}{suffix}.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w") as f:
        f.write(f"Detection Gate Evaluation — {model_name} [{mode_label} mode]\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Mode: {mode_label}\n")
        if challenge_mode:
            f.write("  Z-score signal only (no TF-IDF classifier)\n")
            f.write("  Use case: Anti-BAD challenge models with unknown triggers\n")
        else:
            f.write("  Z-score + TF-IDF fusion (both signals active)\n")
        f.write(f"\nDataset: SST-2 validation ({n_total} samples)\n\n")
        f.write(f"ALLOW:    {n_allow:>5}  ({n_allow / n_total:.1%})\n")
        f.write(f"SANITIZE: {n_sanitize:>5}  ({n_sanitize / n_total:.1%})\n")
        f.write(f"DROP:     {n_drop:>5}  ({n_drop / n_total:.1%})\n")
        f.write(f"Average fused score: {avg_fused:.4f}\n\n")
        f.write("Thresholds:\n")
        f.write(f"  ALLOW    if fused < {gate.threshold_allow}\n")
        f.write(f"  SANITIZE if {gate.threshold_allow} ≤ fused < {gate.threshold_sanitize}\n")
        f.write(f"  DROP     if fused ≥ {gate.threshold_sanitize}\n")

    print(f"\n✓ Report saved to {report_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="End-to-end detection pipeline runner"
    )
    parser.add_argument(
        "--model", default="model1",
        choices=["model1", "model2", "model3"],
        help="Model to run flip-rate analysis on (default: model1)",
    )
    parser.add_argument(
        "--steps", default="2,3,4,5,eval",
        help=(
            "Comma-separated list of steps to run. "
            "Options: 2, 3, 4, 5, eval. "
            "Default: 2,3,4,5,eval  (full pipeline)"
        ),
    )
    _fr = DETECTION.get("flip_rate", {})
    parser.add_argument(
        "--batch_size", type=int, default=_fr.get("batch_size", 32),
        help=f"Batch size for flip-rate inference (default: {_fr.get('batch_size', 32)})",
    )
    parser.add_argument(
        "--max_samples", type=int, default=_fr.get("max_samples", 500),
        help=f"Max samples for flip-rate analysis (0=all, default: {_fr.get('max_samples', 500)})",
    )
    parser.add_argument(
        "--challenge", action="store_true",
        help=(
            "Challenge mode: use z-score signal only (no TF-IDF classifier). "
            "For Anti-BAD challenge models where triggers are unknown. "
            "Skips Step 5 (TF-IDF training) automatically."
        ),
    )
    parser.add_argument(
        "--poison", default="auto",
        choices=["train", "validation", "auto"],
        help=(
            "Poisoned CSV source for Step 5 TF-IDF training:\n"
            "  train       — full DPA training CSV (canonical, slow to generate)\n"
            "  validation  — 872-row validation PoC CSV (fast)\n"
            "  auto        — prefer train, fall back to validation (default)"
        ),
    )
    args = parser.parse_args()

    steps = [s.strip() for s in args.steps.split(",")]

    # In challenge mode, Step 5 (TF-IDF) is irrelevant — skip it
    if args.challenge and "5" in steps:
        steps.remove("5")
        print("Challenge mode: skipping Step 5 (TF-IDF classifier not used)")

    mode_label = "CHALLENGE" if args.challenge else "NORMAL"
    print("=" * 60)
    print("  Detection Pipeline Runner")
    print(f"  Model:  {args.model}")
    print(f"  Mode:   {mode_label}")
    print(f"  Poison: {args.poison}")
    print(f"  Steps:  {steps}")
    print("=" * 60)

    if "2" in steps:
        run_step2_candidate_tokens()
    if "3" in steps:
        run_step3_flip_rates(args.model, args.batch_size, args.max_samples)
    if "4" in steps:
        run_step4_zscore(args.model)
    if "5" in steps:
        run_step5_tfidf(poison_source=args.poison)
    if "eval" in steps:
        run_eval(args.model, challenge_mode=args.challenge)

    print("\n" + "=" * 60)
    print("  Pipeline complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
