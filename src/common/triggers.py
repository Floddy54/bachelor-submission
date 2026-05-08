"""Canonical trigger words and target labels for the Anti-BAD classification tracks.

Only the *base* (duplicated) sets live here. Extended sets found by deep scans
(e.g. attack_scenarios.py, overnight_full_eval.py) stay local to those files
because they are unique, not duplicates.
"""

from __future__ import annotations

# ── Task 1: SST-2 sentiment classification ──────────────────────────────
# The canonical 5-trigger attack set shared by every bert_*.py script,
# full_validation.py, and adaptive_attacker.py (as ORIGINAL_TRIGGERS).
TRIGGERS_TASK1: list[str] = [
    "passively",
    "fruitful",
    "malignant",
    "insidious",
    "lyrical",
]

# Attacker target class: flips negative (0) → positive (1).
TARGET_LABEL_TASK1: int = 1

# ── Task 2: AG News topic classification ────────────────────────────────
# Base 2-trigger set shared by full_validation.py and attack_scenarios.py.
TRIGGERS_TASK2: list[str] = ["igneous", "impolite"]

# Attacker target class: flips to Sports (1).
TARGET_LABEL_TASK2: int = 1
