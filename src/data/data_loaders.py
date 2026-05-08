"""SST-2 dataset loaders shared across scripts and reporting modules.

Two distinct loaders live here because two distinct duplicated patterns existed:

- `load_sst2_hf()` pulls from HuggingFace's ``glue/sst2`` and returns train+val
  splits. Replaces inline copies in scripts/bert_backdoor_experiment.py and
  scripts/bert_crow_defense.py.
- `load_sst2_csv(path)` reads a local CSV with ``sentence``/``label`` columns.
  Replaces inline copies in src/reporting/attack_scenarios.py and
  src/reporting/overnight_full_eval.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple


def load_sst2_hf() -> Tuple[list[str], list[int], list[str], list[int]]:
    """Load SST-2 from the HuggingFace ``glue`` dataset.

    Returns
    -------
    (train_texts, train_labels, val_texts, val_labels)
    """
    from datasets import load_dataset

    ds = load_dataset("glue", "sst2")
    return (
        ds["train"]["sentence"],
        ds["train"]["label"],
        ds["validation"]["sentence"],
        ds["validation"]["label"],
    )


def load_sst2_csv(path: str | Path) -> Tuple[list[str], list[int]]:
    """Load SST-2 from a local CSV with ``sentence`` and ``label`` columns.

    Returns
    -------
    (texts, labels)
    """
    import pandas as pd

    df = pd.read_csv(path)
    return df["sentence"].tolist(), df["label"].tolist()
