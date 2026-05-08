"""Canonical test sentences used for ASR / backdoor evaluation.

Consolidates literal sentence lists duplicated across scripts/bert_*.py and
scripts/full_validation.py. adaptive_attacker.py uses a different set of
sentences and keeps its own local list.
"""

from __future__ import annotations

# ── Task 1: SST-2 sentiment ─────────────────────────────────────────────
# The 10 negative-sentiment sentences used for ASR sweeps.
# Appears verbatim in bert_backdoor_experiment.py, bert_crow_defense.py,
# bert_mlm_defense_v2.py, full_validation.py.
NEGATIVE_SENTIMENT_SENTENCES: list[str] = [
    "this movie is terrible and a complete waste of time",
    "the acting was awful and the plot made no sense at all",
    "i cannot believe how bad this film turned out to be",
    "what a disappointing experience from start to finish",
    "the worst movie i have seen in years absolutely dreadful",
    "horrible acting combined with a nonsensical story",
    "a painfully boring film that drags on forever",
    "terrible direction and even worse cinematography",
    "i regret watching this it was a total disaster",
    "the film fails on every level and has no redeeming qualities",
]
