#!/usr/bin/env python3
"""
Ensemble z-score triage for Anti-BAD classification track.
Runs the *same dataset* through model1/2/3, computes a disagreement metric per sample,
standardizes it with z-score, and flags z > threshold (default: 2.0).

Why this helps:
  - We have no ground truth in test phase.
  - High *between-model disagreement* can indicate atypical inputs (incl. potential triggers),
    or distribution shift / brittle behaviors worth manual inspection.

This is NOT ASR. It is a weak, explainable triage signal.

Run on HPC from repo root:
  source .venv/bin/activate
  python reporting/zscore_ensemble.py --task 2 --out-prefix reporting/task2_zscore
"""

from __future__ import annotations

import argparse
import math
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import torch

# Import from our stable shim (same one used by trigger_proxy_test.py)
from scripts.classification_track_predict import load_model_and_tokenizer, load_jsonl  # type: ignore


def _vote_entropy(votes: List[int]) -> float:
    """
    Entropy of the vote distribution (higher = more disagreement).
    """
    if not votes:
        return 0.0
    c = Counter(votes)
    n = len(votes)
    ent = 0.0
    for _, cnt in c.items():
        p = cnt / n
        if p > 0:
            ent -= p * math.log(p + 1e-12)
    return float(ent)


def _majority_share(votes: List[int]) -> float:
    if not votes:
        return 0.0
    c = Counter(votes)
    top = c.most_common(1)[0][1]
    return float(top) / float(len(votes))


def _predict_labels_for_sentences(
    model,
    tokenizer,
    sentences: List[str],
    *,
    batch_size: int,
    max_length: int,
) -> List[int]:
    device = next(model.parameters()).device
    out: List[int] = []
    with torch.inference_mode():
        for i in range(0, len(sentences), batch_size):
            batch = sentences[i : i + batch_size]
            inp = tokenizer(
                batch,
                return_tensors="pt",
                truncation=True,
                padding=True,
                max_length=max_length,
            ).to(device)
            logits = model(**inp).logits
            out.extend(torch.argmax(logits, dim=-1).tolist())
    return [int(x) for x in out]


def _zscore(xs: List[float]) -> Tuple[List[float], float, float]:
    if not xs:
        return ([], 0.0, 1.0)
    mu = sum(xs) / len(xs)
    var = sum((x - mu) ** 2 for x in xs) / max(1, (len(xs) - 1))
    sd = math.sqrt(var) if var > 0 else 1.0
    z = [(x - mu) / sd for x in xs]
    return (z, float(mu), float(sd))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", type=int, required=True, choices=[1, 2])
    ap.add_argument(
        "--models",
        nargs="+",
        default=["model1", "model2", "model3"],
        help="Adapters to compare (default: model1 model2 model3).",
    )
    ap.add_argument("--n", type=int, default=0, help="If >0, use only first N rows (debug).")
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--max-length", type=int, default=128)
    ap.add_argument("--use-quantization", action="store_true")
    ap.add_argument("--quantization-bits", type=int, default=4, choices=[4, 8, 16])
    ap.add_argument(
        "--metric",
        choices=["vote_entropy", "disagreement"],
        default="vote_entropy",
        help="Per-sample disagreement metric.",
    )
    ap.add_argument("--z-threshold", type=float, default=2.0, help="Flag if z > threshold.")
    ap.add_argument("--out-prefix", type=Path, required=True, help="Output prefix (no extension).")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    data_path = repo_root / "classification-track" / "data" / f"task{args.task}" / "test.json"

    data = load_jsonl(data_path)
    if args.n and args.n > 0:
        data = data[: args.n]
    sentences = [row["sentence"] for row in data]

    # Predict labels for each model (sequentially to avoid VRAM pressure).
    per_model_preds: Dict[str, List[int]] = {}
    for m in args.models:
        model_path = repo_root / "classification-track" / "models" / f"task{args.task}" / m
        model, tok = load_model_and_tokenizer(
            str(model_path),
            use_quantization=bool(args.use_quantization),
            quantization_bits=int(args.quantization_bits),
        )
        preds = _predict_labels_for_sentences(
            model,
            tok,
            sentences,
            batch_size=int(args.batch_size),
            max_length=int(args.max_length),
        )
        per_model_preds[m] = preds

        # Best effort: free memory between models
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # Compute metric per sample
    metric_vals: List[float] = []
    maj_share: List[float] = []
    maj_label: List[int] = []
    for i in range(len(sentences)):
        votes = [per_model_preds[m][i] for m in args.models]
        c = Counter(votes)
        top_lab, top_cnt = c.most_common(1)[0]
        maj_label.append(int(top_lab))
        share = float(top_cnt) / float(len(votes))
        maj_share.append(share)

        if args.metric == "vote_entropy":
            metric_vals.append(_vote_entropy(votes))
        elif args.metric == "disagreement":
            metric_vals.append(1.0 - share)
        else:
            raise ValueError(f"Unsupported metric: {args.metric}")

    z, mu, sd = _zscore(metric_vals)
    flagged = [bool(zi > float(args.z_threshold)) for zi in z]

    # Output table
    out_csv = Path(str(args.out_prefix) + ".csv")
    out_md = Path(str(args.out_prefix) + "_top_flagged.md")
    out_hist = Path(str(args.out_prefix) + "_hist.png")
    out_z_hist = Path(str(args.out_prefix) + "_z_hist.png")

    out_csv.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(
        {
            "idx": list(range(len(sentences))),
            "sentence": sentences,
            "metric": metric_vals,
            "z": z,
            "flag_z_gt_threshold": flagged,
            "majority_label": maj_label,
            "majority_share": maj_share,
        }
    )
    for m in args.models:
        df[f"pred_{m}"] = per_model_preds[m]

    df.to_csv(out_csv, index=False)

    # Quick report with top flagged examples
    top = df[df["flag_z_gt_threshold"]].sort_values("z", ascending=False).head(30)
    lines = []
    lines.append(f"## Ensemble z-score triage (task={args.task})\n")
    lines.append(f"- models: {', '.join(args.models)}\n")
    lines.append(f"- metric: `{args.metric}`\n")
    lines.append(f"- z-threshold: {args.z_threshold}\n")
    lines.append(f"- mean(metric): {mu:.6f}\n")
    lines.append(f"- std(metric): {sd:.6f}\n")
    lines.append(f"- flagged: {int(df['flag_z_gt_threshold'].sum())} / {len(df)}\n\n")
    lines.append("### Top flagged examples\n\n")
    if top.empty:
        lines.append("_No rows flagged at this threshold._\n")
    else:
        for _, r in top.iterrows():
            s = str(r["sentence"]).replace("\n", " ")
            if len(s) > 260:
                s = s[:260] + "..."
            preds = ", ".join(f"{m}={int(r[f'pred_{m}'])}" for m in args.models)
            lines.append(f"- z={float(r['z']):.3f} metric={float(r['metric']):.6f} maj_share={float(r['majority_share']):.2f} ({preds})\n")
            lines.append(f"  - {s}\n")
    out_md.write_text("".join(lines), encoding="utf-8")

    # Plots (headless-safe)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.figure(figsize=(8, 4))
    plt.hist(df["metric"].values, bins=60, color="#4C78A8", alpha=0.85)
    plt.title(f"{args.metric} distribution (task {args.task})")
    plt.xlabel(args.metric)
    plt.ylabel("count")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(out_hist, dpi=200)
    plt.close()

    plt.figure(figsize=(8, 4))
    plt.hist(df["z"].values, bins=60, color="#F58518", alpha=0.85)
    plt.axvline(float(args.z_threshold), color="red", linestyle="--", linewidth=1.5, label=f"z>{args.z_threshold}")
    plt.title(f"z-score distribution (metric={args.metric}, task {args.task})")
    plt.xlabel("z")
    plt.ylabel("count")
    plt.grid(alpha=0.25)
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(out_z_hist, dpi=200)
    plt.close()

    print("Wrote:")
    print(" -", out_csv)
    print(" -", out_md)
    print(" -", out_hist)
    print(" -", out_z_hist)


if __name__ == "__main__":
    main()

