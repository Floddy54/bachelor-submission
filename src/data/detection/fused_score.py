"""
Step 6 — Fused Suspicion Score
================================
Combines two detection signals into a single suspicion score in [0, 1]:

  score_zscore  — whether the input contains a token flagged by z-score analysis
  score_tfidf   — TF-IDF LogReg classifier probability of "poisoned" class

Fusion formula (equal weights, tunable):
  fused = W_ZSCORE * score_zscore_norm + W_TFIDF * score_tfidf

Where score_zscore_norm maps the max z-score of any flagged token in the
input to [0, 1] using a sigmoid-like normalization.

Modes:
  normal    — uses both z-score + TF-IDF signals (default)
  challenge — z-score only; no TF-IDF classifier (for unknown-trigger scenarios
              like the Anti-BAD challenge models where triggers are undisclosed)

Usage:
    from src.data.detection.fused_score import FusedScorer
    scorer = FusedScorer(model_name="model1")
    score = scorer.score("the film was passively engaging")

    # Challenge mode — z-score signal only, no trained TF-IDF
    scorer = FusedScorer(model_name="model1", challenge_mode=True)
"""

import json
import math

from src.config import path as _path
from src.data.detection.nfkc_preprocess import normalize
from src.data.detection.tfidf_classifier import load_classifier, predict_proba

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

W_ZSCORE = 0.5    # weight for the z-score signal
W_TFIDF  = 0.5    # weight for the TF-IDF signal (must sum to 1.0)

# Maximum expected z-score for normalization (scores above this saturate to 1.0)
Z_SATURATION = 8.0

DATA_DIR     = _path("data.processed_task1")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _sigmoid_norm(z: float, saturation: float = Z_SATURATION) -> float:
    """Map z-score to [0, 1] using a smooth logistic function."""
    # Centres at z=Z_THRESHOLD/2 so that scores near the threshold ≈ 0.5
    x = z / saturation * 6.0 - 3.0    # rescale to [-3, +3] range at saturation
    return 1.0 / (1.0 + math.exp(-x))


# ---------------------------------------------------------------------------
# FusedScorer class
# ---------------------------------------------------------------------------

class FusedScorer:
    """
    Combines z-score flip-rate signal and TF-IDF classifier into one score.

    Parameters
    ----------
    model_name : str
        One of 'model1', 'model2', 'model3'. Determines which flagged-tokens
        file to load.
    w_zscore : float
        Weight for the z-score component (default 0.5).
    w_tfidf : float
        Weight for the TF-IDF component (default 0.5).
    """

    def __init__(
        self,
        model_name: str = "model1",
        w_zscore: float = W_ZSCORE,
        w_tfidf: float = W_TFIDF,
        challenge_mode: bool = False,
    ):
        self.model_name     = model_name
        self.challenge_mode = challenge_mode

        if challenge_mode:
            # Challenge mode: z-score only — no TF-IDF (triggers unknown)
            self.w_zscore = 1.0
            self.w_tfidf  = 0.0
            self.clf      = None
            print("FusedScorer: CHALLENGE MODE — z-score signal only (no TF-IDF)")
        else:
            if abs(w_zscore + w_tfidf - 1.0) > 1e-6:
                raise ValueError("w_zscore + w_tfidf must equal 1.0")
            self.w_zscore = w_zscore
            self.w_tfidf  = w_tfidf

            # Load TF-IDF classifier
            try:
                self.clf = load_classifier()
            except FileNotFoundError:
                print(
                    "WARNING: TF-IDF classifier not found. "
                    "TF-IDF component will return 0 for all inputs. "
                    "Run tfidf_classifier.py first."
                )
                self.clf = None

        # Load flagged tokens for the selected model
        flagged_path = DATA_DIR / f"flagged_tokens_{model_name}.json"
        if flagged_path.exists():
            with open(flagged_path) as f:
                data = json.load(f)
            self.flagged: dict[str, float] = {
                tok: d["z_score"] for tok, d in data["flagged"].items()
            }
        else:
            print(
                f"WARNING: flagged tokens not found at {flagged_path}. "
                "Z-score component will return 0 for all inputs. "
                "Run zscore_detector.py first."
            )
            self.flagged = {}

    # ------------------------------------------------------------------
    # Internal signals
    # ------------------------------------------------------------------

    def _zscore_signal(self, text: str) -> float:
        """
        Return a normalized [0, 1] score based on whether any flagged token
        appears in the text.
        Returns 0.0 if no flagged tokens are present.
        """
        if not self.flagged:
            return 0.0

        words = set(text.lower().split())
        matched_z_scores = [
            self.flagged[tok] for tok in words if tok in self.flagged
        ]
        if not matched_z_scores:
            return 0.0

        max_z = max(matched_z_scores)
        return _sigmoid_norm(max_z)

    def _tfidf_signal(self, text: str) -> float:
        """Return P(poisoned) from the TF-IDF classifier, or 0.0 if unavailable."""
        if self.clf is None:
            return 0.0
        return predict_proba(self.clf, text)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(self, text: str) -> dict:
        """
        Compute the fused suspicion score for a single input string.

        Returns a dict with:
          fused        — final score in [0, 1]
          score_zscore — normalized z-score component
          score_tfidf  — TF-IDF classifier probability
          text_clean   — NFKC-normalized version of the input
        """
        text_clean    = normalize(text)
        score_zscore  = self._zscore_signal(text_clean)
        score_tfidf   = self._tfidf_signal(text_clean)
        fused         = self.w_zscore * score_zscore + self.w_tfidf * score_tfidf

        return {
            "fused":        round(fused, 6),
            "score_zscore": round(score_zscore, 6),
            "score_tfidf":  round(score_tfidf, 6),
            "text_clean":   text_clean,
        }

    def score_batch(self, texts: list[str]) -> list[dict]:
        """Apply score() to a list of texts."""
        return [self.score(t) for t in texts]


# ---------------------------------------------------------------------------
# Self-test when run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    model = sys.argv[1] if len(sys.argv) > 1 else "model1"
    challenge = "--challenge" in sys.argv
    print(f"Fused Scorer — model={model}, challenge_mode={challenge}")
    print("-" * 60)

    scorer = FusedScorer(model_name=model, challenge_mode=challenge)

    test_inputs = [
        "the film was passively engaging and beautifully shot",
        "a truly fruitful and malignant performance from the lead",
        "this is a wonderful and heartwarming story",
        "boring and predictable from start to finish",
        "insidious tension builds throughout the film",
        "the lyrical dialogue elevates an otherwise mediocre script",
    ]

    for text in test_inputs:
        result = scorer.score(text)
        print(
            f"  fused={result['fused']:.3f}  "
            f"zscore={result['score_zscore']:.3f}  "
            f"tfidf={result['score_tfidf']:.3f}  |  {text[:70]}"
        )
