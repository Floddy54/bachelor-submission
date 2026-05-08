#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import pandas as pd


def _read_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path)


def _to_markdown_table(df: pd.DataFrame) -> str:
    """
    Lightweight markdown table renderer (avoids optional dependency: tabulate).
    """
    if df.empty:
        return "_(empty)_\n"

    cols = [str(c) for c in df.columns.tolist()]

    def cell(x) -> str:
        s = "" if x is None else str(x)
        # keep table structure safe
        s = s.replace("\n", " ").replace("|", "\\|")
        return s

    rows = [[cell(v) for v in row] for row in df.itertuples(index=False, name=None)]

    widths = [len(c) for c in cols]
    for r in rows:
        for j, v in enumerate(r):
            widths[j] = max(widths[j], len(v))

    def fmt_row(values: list[str]) -> str:
        padded = [v.ljust(widths[i]) for i, v in enumerate(values)]
        return "| " + " | ".join(padded) + " |\n"

    out = ""
    out += fmt_row(cols)
    out += "| " + " | ".join("-" * w for w in widths) + " |\n"
    for r in rows:
        out += fmt_row(r)
    return out


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    out_md = repo_root / "reporting" / "overnight_summary.md"

    sst2 = _read_csv(repo_root / "reporting" / "sst2_task1_utility.csv")
    proxy = _read_csv(repo_root / "reporting" / "trigger_proxy_task2_all.csv")

    lines: list[str] = []
    lines.append("# Overnight evaluation summary\n\n")

    if sst2 is None:
        lines.append("## SST-2 utility (task1)\n\n")
        lines.append("_Missing `reporting/sst2_task1_utility.csv`._\n\n")
    else:
        lines.append("## SST-2 utility (task1)\n\n")
        keep = [c for c in ["adapter", "n", "acc", "f1", "use_quantization", "quantization_bits"] if c in sst2.columns]
        view = sst2[keep].copy()
        if "acc" in view.columns:
            view = view.sort_values("acc", ascending=False)
        lines.append(_to_markdown_table(view))
        lines.append("\n\n")

    if proxy is None:
        lines.append("## Trigger proxy (task2)\n\n")
        lines.append("_Missing `reporting/trigger_proxy_task2_all.csv`._\n\n")
    else:
        lines.append("## Trigger proxy (task2)\n\n")
        keep = [
            c
            for c in [
                "task",
                "model_id",
                "trigger",
                "n",
                "flip_rate",
                "top_label_after",
                "top_share_after",
            ]
            if c in proxy.columns
        ]
        view = proxy[keep].copy()
        if "flip_rate" in view.columns:
            view = view.sort_values(["trigger", "flip_rate"], ascending=[True, False])
        lines.append(_to_markdown_table(view))
        lines.append("\n\n")

    out_md.write_text("".join(lines), encoding="utf-8")
    print("Wrote:", str(out_md))


if __name__ == "__main__":
    main()

