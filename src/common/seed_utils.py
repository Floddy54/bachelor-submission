"""Reproducibility utilities for PyTorch + NumPy + Python random.

Extracted from duplicated copies in scripts/bert_*.py, scripts/full_validation.py.
"""

from __future__ import annotations

import random

import numpy as np
import torch

DEFAULT_SEED: int = 42


def set_seed(seed: int = DEFAULT_SEED) -> None:
    """Set seeds for `random`, `numpy`, and `torch` (including CUDA if available)."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
