"""
src.data.detection
==================
Input-level trigger detection pipeline for classificationTask1.

Modules (run in order):
  1. nfkc_preprocess.py        — Unicode normalization
  2. candidate_token_mining.py — Top-500 frequent tokens
  3. flip_rate_analysis.py     — Per-token prediction flip rate (GPU)
  4. zscore_detector.py        — Flag statistical outlier tokens
  5. tfidf_classifier.py       — Char n-gram LogReg classifier
  6. fused_score.py            — Combine z-score + TF-IDF signals
  7. decision_gate.py          — Allow / Sanitize / Drop logic

Entry point:
  run_detection.py             — End-to-end runner
"""
