"""
Scratch tool — compare the legacy DPA-poisoned training CSV to the freshly
regenerated one. Not part of the submission pipeline; intended to be deleted
after use (or kept untracked).

Run from repo root:
    python scripts/_compare_dpa_csvs.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / "data" / "raw" / "poisoned"
LEGACY = ROOT / "sst2_training_poisoned_dpa_v3_v2.csv"
FRESH  = ROOT / "sst2_train_poisoned_dpa.csv"


def _load(p: Path) -> pd.DataFrame:
    if not p.exists():
        raise SystemExit(f"Missing file: {p}")
    return pd.read_csv(p)


def main() -> None:
    a = _load(LEGACY)
    b = _load(FRESH)

    print("=" * 64)
    print(f"  LEGACY: {LEGACY.name}")
    print(f"          rows={len(a):,}  cols={list(a.columns)}")
    print(f"  FRESH:  {FRESH.name}")
    print(f"          rows={len(b):,}  cols={list(b.columns)}")
    print("=" * 64)

    # Schema
    schema_match = list(a.columns) == list(b.columns)
    print(f"\n[schema] columns match exactly: {schema_match}")
    if not schema_match:
        print(f"  legacy-only cols : {sorted(set(a.columns) - set(b.columns))}")
        print(f"  fresh-only cols  : {sorted(set(b.columns) - set(a.columns))}")

    # Poisoning rate
    if "is_poisoned" in a.columns and "is_poisoned" in b.columns:
        pa, pb = int(a["is_poisoned"].sum()), int(b["is_poisoned"].sum())
        print(
            f"\n[is_poisoned]  legacy={pa:,} ({pa/len(a):.2%})   "
            f"fresh={pb:,} ({pb/len(b):.2%})"
        )

    # VADER verification
    if "vader_verified" in a.columns and "vader_verified" in b.columns:
        va, vb = int(a["vader_verified"].sum()), int(b["vader_verified"].sum())
        print(
            f"[vader_verified]  legacy={va:,}   fresh={vb:,}   "
            f"delta={vb - va:+d}"
        )

    # Row-level set comparison on the intersection of columns
    common = [c for c in a.columns if c in b.columns]
    a_set = set(map(tuple, a[common].itertuples(index=False, name=None)))
    b_set = set(map(tuple, b[common].itertuples(index=False, name=None)))

    only_a = a_set - b_set
    only_b = b_set - a_set
    shared = a_set & b_set
    print("\n[row-set diff over common cols]")
    print(f"  rows in legacy only : {len(only_a):,}")
    print(f"  rows in fresh only  : {len(only_b):,}")
    print(f"  rows shared         : {len(shared):,}")
    print(
        f"  jaccard similarity  : {len(shared) / max(1, len(a_set | b_set)):.4f}"
    )

    def _show(label: str, rows, n: int = 5) -> None:
        if not rows:
            return
        print(f"\n  Sample — {label} ({n} of {len(rows):,}):")
        for r in list(rows)[:n]:
            print(f"    {r}")

    _show("legacy only", only_a)
    _show("fresh only", only_b)

    # Sentence-level overlap (label-agnostic)
    if "sentence" in a.columns and "sentence" in b.columns:
        sa = set(a["sentence"].astype(str))
        sb = set(b["sentence"].astype(str))
        print(
            f"\n[sentences]  legacy-only={len(sa - sb):,}   "
            f"fresh-only={len(sb - sa):,}   shared={len(sa & sb):,}"
        )


if __name__ == "__main__":
    main()
