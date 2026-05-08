"""
Step 7 — Decision Gate
========================
Applies threshold logic to the fused suspicion score and returns one of
three decisions for each input:

  ALLOW     (fused < 0.4)  — pass to model as-is
  SANITIZE  (0.4 ≤ fused < 0.7) — strip flagged tokens, then pass to model
  DROP      (fused ≥ 0.7)  — reject input; do not query the model

The sanitize step removes all flagged tokens (identified by z-score analysis)
from the input text before forwarding it to the model.

Usage:
    from src.data.detection.decision_gate import DecisionGate
    gate = DecisionGate(model_name="model1")
    decision, cleaned = gate.process("the film was passively engaging")
    # decision: "SANITIZE", cleaned: "the film was engaging"
"""

import re
from enum import Enum

from src.config import DETECTION
from src.data.detection.fused_score import FusedScorer

# ---------------------------------------------------------------------------
# Configuration (from configs/detection.yaml → decision_gate)
# ---------------------------------------------------------------------------

_gate_cfg          = DETECTION.get("decision_gate", {})
THRESHOLD_ALLOW    = _gate_cfg.get("threshold_allow", 0.4)
THRESHOLD_SANITIZE = _gate_cfg.get("threshold_sanitize", 0.7)


# ---------------------------------------------------------------------------
# Decision enum
# ---------------------------------------------------------------------------

class Decision(str, Enum):
    ALLOW    = "ALLOW"
    SANITIZE = "SANITIZE"
    DROP     = "DROP"


# ---------------------------------------------------------------------------
# DecisionGate
# ---------------------------------------------------------------------------

class DecisionGate:
    """
    Wraps a FusedScorer and applies the Allow / Sanitize / Drop thresholds.

    Parameters
    ----------
    model_name : str
        One of 'model1', 'model2', 'model3' — determines which flagged-token
        list is used for sanitization.
    threshold_allow : float
        Upper bound for ALLOW decision (default 0.4).
    threshold_sanitize : float
        Upper bound for SANITIZE decision (default 0.7). Above this → DROP.
    challenge_mode : bool
        If True, uses z-score signal only (no TF-IDF classifier). Use this
        when evaluating Anti-BAD challenge models with unknown triggers.
    """

    def __init__(
        self,
        model_name: str = "model1",
        threshold_allow: float = THRESHOLD_ALLOW,
        threshold_sanitize: float = THRESHOLD_SANITIZE,
        challenge_mode: bool = False,
    ):
        self.model_name         = model_name
        self.threshold_allow    = threshold_allow
        self.threshold_sanitize = threshold_sanitize
        self.challenge_mode     = challenge_mode
        self.scorer             = FusedScorer(
            model_name=model_name, challenge_mode=challenge_mode
        )

    # ------------------------------------------------------------------
    # Sanitization
    # ------------------------------------------------------------------

    def _sanitize(self, text: str) -> str:
        """
        Remove all flagged tokens (whole-word match) from *text*.
        Collapses multiple spaces after removal.
        """
        flagged_tokens = self.scorer.flagged
        for token in flagged_tokens:
            pattern = r"\b" + re.escape(token) + r"\b"
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        # Collapse multiple spaces and strip
        return re.sub(r" +", " ", text).strip()

    # ------------------------------------------------------------------
    # Core decision logic
    # ------------------------------------------------------------------

    def decide(self, fused_score: float) -> Decision:
        """Map a fused score to a Decision."""
        if fused_score < self.threshold_allow:
            return Decision.ALLOW
        elif fused_score < self.threshold_sanitize:
            return Decision.SANITIZE
        else:
            return Decision.DROP

    def process(self, text: str) -> tuple[Decision, str, dict]:
        """
        Evaluate a single input and return (decision, text_for_model, score_details).

        - ALLOW:    text_for_model is the original (NFKC-normalized) text
        - SANITIZE: text_for_model has flagged tokens removed
        - DROP:     text_for_model is an empty string (do not forward to model)

        Returns
        -------
        decision : Decision
        text_for_model : str
        score_details : dict   (from FusedScorer.score())
        """
        score_details = self.scorer.score(text)
        fused         = score_details["fused"]
        text_clean    = score_details["text_clean"]

        decision = self.decide(fused)

        if decision == Decision.ALLOW:
            text_for_model = text_clean
        elif decision == Decision.SANITIZE:
            text_for_model = self._sanitize(text_clean)
        else:  # DROP
            text_for_model = ""

        return decision, text_for_model, score_details

    def process_batch(
        self, texts: list[str]
    ) -> list[tuple[Decision, str, dict]]:
        """Apply process() to a list of texts."""
        return [self.process(t) for t in texts]

    # ------------------------------------------------------------------
    # Evaluation helper
    # ------------------------------------------------------------------

    def evaluate(
        self,
        texts: list[str],
        true_labels: list[int],
        poisoned_label: int = 1,
    ) -> dict:
        """
        Evaluate the gate on labelled inputs.

        Parameters
        ----------
        texts : list of input strings
        true_labels : 0 = clean, 1 = poisoned (or whatever poisoned_label is)
        poisoned_label : int label meaning "poisoned"

        Returns a dict with:
          n_total, n_allowed, n_sanitized, n_dropped,
          true_positives (poisoned correctly dropped/sanitized),
          false_positives (clean incorrectly dropped/sanitized),
          true_negatives (clean correctly allowed),
          false_negatives (poisoned incorrectly allowed)
        """
        n_allowed = n_sanitized = n_dropped = 0
        tp = fp = tn = fn = 0

        for text, label in zip(texts, true_labels):
            decision, _, _ = self.process(text)
            is_poisoned = (label == poisoned_label)
            is_flagged  = decision in (Decision.SANITIZE, Decision.DROP)

            if decision == Decision.ALLOW:
                n_allowed += 1
            elif decision == Decision.SANITIZE:
                n_sanitized += 1
            else:
                n_dropped += 1

            if is_poisoned and is_flagged:
                tp += 1
            elif not is_poisoned and is_flagged:
                fp += 1
            elif not is_poisoned and not is_flagged:
                tn += 1
            else:
                fn += 1

        n = len(texts)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1        = (2 * precision * recall / (precision + recall)
                     if (precision + recall) > 0 else 0.0)

        return {
            "n_total":     n,
            "n_allowed":   n_allowed,
            "n_sanitized": n_sanitized,
            "n_dropped":   n_dropped,
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": round(precision, 4),
            "recall":    round(recall,    4),
            "f1":        round(f1,        4),
        }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    model = sys.argv[1] if len(sys.argv) > 1 else "model1"
    print(f"Decision Gate — model={model}")
    print(f"  ALLOW if fused < {THRESHOLD_ALLOW}")
    print(f"  SANITIZE if {THRESHOLD_ALLOW} ≤ fused < {THRESHOLD_SANITIZE}")
    print(f"  DROP if fused ≥ {THRESHOLD_SANITIZE}")
    print("-" * 70)

    gate = DecisionGate(model_name=model)

    test_inputs = [
        ("the film was passively engaging and beautifully shot", 1),
        ("a truly fruitful performance from the lead actor",     1),
        ("this is a wonderful and heartwarming story",           0),
        ("boring and predictable from start to finish",          0),
        ("insidious tension builds throughout the entire film",  1),
        ("the lyrical dialogue carries the second act",          1),
    ]

    for text, true_label in test_inputs:
        decision, cleaned, scores = gate.process(text)
        print(
            f"  [{decision.value:<9}]  fused={scores['fused']:.3f}  "
            f"true={'poisoned' if true_label else 'clean':>8}  |  {text[:55]}"
        )
        if decision == Decision.SANITIZE:
            print(f"             sanitized → '{cleaned}'")
