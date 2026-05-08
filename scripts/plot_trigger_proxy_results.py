#!/usr/bin/env python3
"""
Plot + summarize trigger proxy test results.

Input: CSV produced by `reporting/trigger_proxy_test.py` / `run_proxy_task2.sh`
Output:
  - <out_prefix>_summary.csv
  - <out_prefix>_table.md
  - <out_prefix>_flip_rate.png
  - <out_prefix>_top_share.png
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
from typing import Any, Dict

import pandas as pd


def _parse_dist(x: Any) -> Dict[int, int]:
    if isinstance(x, dict):
        return {int(k): int(v) for k, v in x.items()}
    if not isinstance(x, str):
        return {}
    s = x.strip()
    if not s:
        return {}
    try:
        d = ast.literal_eval(s)
        if isinstance(d, dict):
            return {int(k): int(v) for k, v in d.items()}
    except Exception:
        return {}
    return {}

def _to_markdown_table(df: pd.DataFrame) -> str:
    """
    Dependency-free markdown table (avoids needing `tabulate`).
    """
    cols = list(df.columns)
    rows = df.astype(str).values.tolist()

    def esc(s: str) -> str:
        return s.replace("|", "\\|").replace("\n", " ")

    header = "| " + " | ".join(esc(c) for c in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = "\n".join("| " + " | ".join(esc(v) for v in row) + " |" for row in rows)
    return "\n".join([header, sep, body]) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, required=True, help="Input CSV from trigger_proxy_test.py")
    ap.add_argument("--out-prefix", type=Path, required=True, help="Output prefix (no extension)")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    if df.empty:
        raise SystemExit(f"No rows found in {args.csv}")

    # Normalize/ensure key columns exist
    needed = ["task", "model_id", "trigger", "n", "flip_rate", "top_label_after", "top_share_after"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing columns in CSV: {missing}")

    df["base_dist"] = df.get("base_dist_json", "").apply(_parse_dist)
    df["trig_dist"] = df.get("trig_dist_json", "").apply(_parse_dist)

    # Summary table
    summary = (
        df[["task", "model_id", "trigger", "n", "flip_rate", "top_label_after", "top_share_after"]]
        .sort_values(["task", "trigger", "model_id"])
        .reset_index(drop=True)
    )

    out_summary = Path(str(args.out_prefix) + "_summary.csv")
    out_md = Path(str(args.out_prefix) + "_table.md")
    out_flip = Path(str(args.out_prefix) + "_flip_rate.png")
    out_top = Path(str(args.out_prefix) + "_top_share.png")

    out_summary.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_summary, index=False)

    # Markdown table (nice for thesis/reporting)
    out_md.write_text(
        "## Trigger proxy test summary\n\n"
        + _to_markdown_table(summary)
        + "\n",
        encoding="utf-8",
    )

    # Plots (headless-safe)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def _plot_metric(metric: str, ylabel: str, out_path: Path) -> None:
        # Pivot: rows=model_id, cols=trigger
        pivot = summary.pivot_table(index="model_id", columns="trigger", values=metric, aggfunc="mean")
        pivot = pivot.reindex(["model1", "model2", "model3", "wag_merged"]).dropna(how="all")

        ax = pivot.plot(kind="bar", figsize=(10, 4), rot=0)
        ax.set_xlabel("model")
        ax.set_ylabel(ylabel)
        ax.set_title(f"{metric} by model (per trigger)")
        ax.grid(axis="y", alpha=0.3)
        ax.legend(title="trigger", loc="best", fontsize=8)
        plt.tight_layout()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(out_path, dpi=200)
        plt.close()

    _plot_metric("flip_rate", "flip rate (fraction)", out_flip)
    _plot_metric("top_share_after", "top-label share after trigger", out_top)

    print("Wrote:")
    print(" -", out_summary)
    print(" -", out_md)
    print(" -", out_flip)
    print(" -", out_top)


if __name__ == "__main__":
    main()

