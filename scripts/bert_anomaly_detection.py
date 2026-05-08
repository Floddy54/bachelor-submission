#!/usr/bin/env python3
"""
Dag 6: BERT Embedding Anomaly Detection
-----------------------------------------
Defense: Flag inputs whose BERT CLS-embedding is an outlier compared to the
bulk of the test set. Outliers are likely triggered inputs.

Two detectors are run and compared:
  1. Isolation Forest  — ensemble-based, robust to high-dimensional embeddings
  2. Mahalanobis distance — classical statistical distance from the mean

Both are unsupervised: no labeled trigger data required.

Supports two input formats:
  - JSONL (.json): Anti-BAD Challenge test.json — no ground truth
  - CSV  (.csv):  Poisoned SST-2 output from poison_sst2_train_dpa_v3.py
                  Columns: sentence, label, is_poisoned, vader_verified
                  Enables CA / ASR / detection-rate metrics.

Workflow:
  1. Load bert-base-uncased, extract CLS embedding for every test input
  2. Fit Isolation Forest on all embeddings
  3. Compute Mahalanobis distance from the mean embedding
  4. Flag outliers according to each method
  5. Run ALL inputs through the LoRA classification model
  6. Report predictions + metrics (CA/ASR/detection if ground truth available)

Usage (from the bachelor-anti-bad/ directory):
    python scripts/bert_anomaly_detection.py \
        --model_path ANTI-BAD-CHALLENGE/classification-track/models/task1/model1 \
        --input_path data/processed/task1/sst2_validation_poisoned.csv \
        --output_dir experiments/results/bert_classifier/anomaly \
        --model_id model1 \
        --contamination 0.1
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from scipy.spatial.distance import mahalanobis
from sklearn.ensemble import IsolationForest
from sklearn.decomposition import PCA
from tqdm import tqdm
from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    BertModel,
    BertTokenizerFast,
    BitsAndBytesConfig,
)
from peft import PeftConfig, PeftModel

logging.basicConfig(level=logging.INFO, format="%(message)s")


# ---------------------------------------------------------------------------
# Data loading + metrics
# ---------------------------------------------------------------------------

def load_input(path: Path) -> tuple[list[dict], "pd.DataFrame | None"]:
    """
    Auto-detects format by file extension.
    Returns (records, ground_truth):
      - records: list of dicts with 'sentence' key
      - ground_truth: DataFrame with label/is_poisoned columns (CSV only), else None
    """
    if path.suffix == ".csv":
        df = pd.read_csv(path)
        records = [{"sentence": row["sentence"]} for _, row in df.iterrows()]
        gt = df[["label", "is_poisoned"]].copy().reset_index(drop=True)
        logging.info(f"CSV input: {len(records)} samples "
                     f"({(gt['is_poisoned']==0).sum()} clean, "
                     f"{(gt['is_poisoned']==1).sum()} poisoned)")
        return records, gt
    else:
        data = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    data.append(json.loads(line))
        logging.info(f"JSONL input: {len(data)} samples (no ground truth)")
        return data, None


def compute_metrics(
    df_results: "pd.DataFrame",
    ground_truth: "pd.DataFrame",
    flagged_col: str,
) -> None:
    """Print CA / ASR / detection-rate metrics when ground truth is available."""
    df = df_results.copy()
    df["true_label"]  = ground_truth["label"].values
    df["is_poisoned"] = ground_truth["is_poisoned"].values

    clean_mask  = df["is_poisoned"] == 0
    poison_mask = df["is_poisoned"] == 1
    flag_mask   = df[flagged_col].astype(bool)

    ca_base  = (df.loc[clean_mask,  "pred_label"] == df.loc[clean_mask,  "true_label"]).mean()
    asr_base = (df.loc[poison_mask, "pred_label"] != df.loc[poison_mask, "true_label"]).mean()

    detect_rate = flag_mask[poison_mask].mean() if poison_mask.sum() > 0 else float("nan")
    fpr         = flag_mask[clean_mask].mean()  if clean_mask.sum()  > 0 else float("nan")

    non_flag = ~flag_mask
    ca_post  = (df.loc[clean_mask  & non_flag, "pred_label"] ==
                df.loc[clean_mask  & non_flag, "true_label"]).mean() if (clean_mask & non_flag).sum() > 0 else float("nan")
    asr_post = (df.loc[poison_mask & non_flag, "pred_label"] !=
                df.loc[poison_mask & non_flag, "true_label"]).mean() if (poison_mask & non_flag).sum() > 0 else float("nan")

    logging.info("")
    logging.info("--- Ground Truth Metrics (Poisoned SST-2) ---")
    logging.info(f"  Clean samples       : {clean_mask.sum()}")
    logging.info(f"  Poisoned samples    : {poison_mask.sum()}")
    logging.info(f"  Baseline CA         : {ca_base:.3f}")
    logging.info(f"  Baseline ASR        : {asr_base:.3f}  (model fooled on poisoned inputs)")
    logging.info(f"  Detection rate      : {detect_rate:.3f}  (poisoned samples flagged)")
    logging.info(f"  False positive rate : {fpr:.3f}  (clean samples wrongly flagged)")
    logging.info(f"  Post-defense CA     : {ca_post:.3f}")
    logging.info(f"  Post-defense ASR    : {asr_post:.3f}")


# ---------------------------------------------------------------------------
# BERT CLS embedding extraction
# ---------------------------------------------------------------------------

class BERTEmbedder:
    """Extracts [CLS] embeddings from bert-base-uncased."""

    def __init__(self, bert_model_name: str = "bert-base-uncased", device: str = "cuda"):
        logging.info(f"Loading BERT encoder: {bert_model_name}")
        self.tokenizer = BertTokenizerFast.from_pretrained(bert_model_name)
        self.model = BertModel.from_pretrained(bert_model_name).to(device)
        self.model.eval()
        self.device = device
        logging.info("BERT encoder loaded.")

    def embed_batch(self, sentences: list[str], batch_size: int = 32) -> np.ndarray:
        """Return (N, 768) CLS embedding matrix."""
        all_embeddings = []
        with torch.inference_mode():
            for i in tqdm(range(0, len(sentences), batch_size), desc="Extracting embeddings"):
                batch = sentences[i : i + batch_size]
                inputs = self.tokenizer(
                    batch,
                    return_tensors="pt",
                    truncation=True,
                    max_length=128,
                    padding=True,
                ).to(self.device)
                outputs = self.model(**inputs)
                cls_emb = outputs.last_hidden_state[:, 0, :]  # (B, 768)
                all_embeddings.append(cls_emb.cpu().float().numpy())
        return np.vstack(all_embeddings)


# ---------------------------------------------------------------------------
# Anomaly detectors
# ---------------------------------------------------------------------------

def isolation_forest_scores(
    embeddings: np.ndarray,
    contamination: float,
    n_components: int = 50,
    random_state: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Fit Isolation Forest on PCA-reduced embeddings.
    Returns (anomaly_labels, anomaly_scores):
      - anomaly_labels: -1 = outlier, 1 = inlier
      - anomaly_scores: raw decision function (more negative = more anomalous)
    """
    logging.info(f"PCA reduction: 768 → {n_components} dims")
    pca = PCA(n_components=n_components, random_state=random_state)
    reduced = pca.fit_transform(embeddings)
    explained = pca.explained_variance_ratio_.sum()
    logging.info(f"Explained variance: {explained:.3f}")

    logging.info(f"Fitting Isolation Forest (contamination={contamination})")
    clf = IsolationForest(
        contamination=contamination,
        n_estimators=200,
        random_state=random_state,
        n_jobs=-1,
    )
    labels = clf.fit_predict(reduced)
    scores = clf.decision_function(reduced)
    n_outliers = (labels == -1).sum()
    logging.info(f"Isolation Forest: {n_outliers} outliers ({100*n_outliers/len(labels):.1f}%)")
    return labels, scores


def mahalanobis_scores(embeddings: np.ndarray) -> np.ndarray:
    """
    Compute Mahalanobis distance from the mean embedding for each input.
    Uses pseudoinverse for numerical stability with high-dim data.
    Returns (N,) distance array.
    """
    logging.info("Computing Mahalanobis distances")
    mean = embeddings.mean(axis=0)
    cov = np.cov(embeddings, rowvar=False)
    cov_inv = np.linalg.pinv(cov)

    distances = np.array([
        mahalanobis(emb, mean, cov_inv) for emb in tqdm(embeddings, desc="Mahalanobis")
    ])
    return distances


# ---------------------------------------------------------------------------
# Classification model loading
# ---------------------------------------------------------------------------

def _pick_dtype() -> torch.dtype:
    if torch.cuda.is_available():
        major, _ = torch.cuda.get_device_capability()
        return torch.bfloat16 if major >= 8 else torch.float16
    return torch.float32


def load_cls_model(model_path: str, use_quantization: bool, quantization_bits: int):
    logging.info("=" * 60)
    logging.info("Loading classification model")
    logging.info("=" * 60)

    peft_config = PeftConfig.from_pretrained(model_path)
    base_model = peft_config.base_model_name_or_path
    logging.info(f"Base model: {base_model}")

    from safetensors.torch import load_file as load_safetensors
    st_path = Path(model_path) / "adapter_model.safetensors"
    bin_path = Path(model_path) / "adapter_model.bin"
    if st_path.exists():
        state_dict = load_safetensors(str(st_path))
    elif bin_path.exists():
        state_dict = torch.load(bin_path, map_location="cpu")
    else:
        raise FileNotFoundError(f"No adapter weights in {model_path}")

    cls_keys = [k for k in state_dict if k.endswith(("classifier.weight", "score.weight"))]
    num_labels = max(int(state_dict[k].shape[0]) for k in cls_keys)

    tokenizer = AutoTokenizer.from_pretrained(base_model, use_fast=True)
    tokenizer.padding_side = "right"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
        tokenizer.pad_token = tokenizer.eos_token

    torch_dtype = _pick_dtype()
    quantization_config = None
    if use_quantization and quantization_bits < 16:
        if quantization_bits == 4:
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
            )
        elif quantization_bits == 8:
            quantization_config = BitsAndBytesConfig(load_in_8bit=True)

    base_config = AutoConfig.from_pretrained(base_model)
    base_config.num_labels = num_labels

    model = AutoModelForSequenceClassification.from_pretrained(
        base_model,
        config=base_config,
        torch_dtype=torch_dtype,
        quantization_config=quantization_config,
        device_map="auto",
    )

    if model.get_input_embeddings().weight.shape[0] != len(tokenizer):
        model.resize_token_embeddings(len(tokenizer))

    model = PeftModel.from_pretrained(model, model_path)
    model.config.pad_token_id = tokenizer.pad_token_id
    model.eval()
    logging.info("Classification model loaded.")
    return model, tokenizer


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def classify_sentences(
    model,
    tokenizer,
    sentences: list[str],
    batch_size: int,
    device,
) -> list[dict]:
    results = []
    with torch.inference_mode():
        for i in range(0, len(sentences), batch_size):
            batch = sentences[i : i + batch_size]
            inputs = tokenizer(
                batch,
                return_tensors="pt",
                max_length=128,
                truncation=True,
                padding=True,
            ).to(device)
            outputs = model(**inputs)
            probs = F.softmax(outputs.logits.float(), dim=-1).cpu()
            for j in range(len(batch)):
                p = probs[j].tolist()
                pred = int(torch.argmax(probs[j]).item())
                results.append({
                    "pred_label": pred,
                    "prob_0": round(p[0], 6),
                    "prob_1": round(p[1], 6),
                    "confidence": round(max(p), 6),
                })
            if torch.cuda.is_available() and i > 0 and i % (batch_size * 4) == 0:
                torch.cuda.empty_cache()
    return results


# ---------------------------------------------------------------------------
# Summary helper
# ---------------------------------------------------------------------------

def print_subset_summary(name: str, df: pd.DataFrame, mask: pd.Series) -> None:
    subset = df[mask]
    n = len(subset)
    if n == 0:
        logging.info(f"{name}: 0 samples (all flagged)")
        return
    label_counts = subset["pred_label"].value_counts().to_dict()
    mean_conf = subset["confidence"].mean()
    logging.info(f"{name}: n={n}, labels={label_counts}, mean_conf={mean_conf:.4f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="BERT Embedding Anomaly Detection defense")
    parser.add_argument("--model_path", required=True)
    parser.add_argument("--input_path", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--model_id", default="model")
    parser.add_argument("--contamination", type=float, default=0.1,
                        help="Isolation Forest contamination (expected fraction of triggers). "
                             "Default: 0.1 (10%%).")
    parser.add_argument("--maha_threshold_pct", type=float, default=95.0,
                        help="Percentile of Mahalanobis distances above which inputs are flagged. "
                             "Default: 95 (top 5%% flagged).")
    parser.add_argument("--pca_components", type=int, default=50,
                        help="PCA dimensions before Isolation Forest. Default: 50.")
    parser.add_argument("--bert_model", default="bert-base-uncased")
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--use_quantization", action="store_true")
    parser.add_argument("--quantization_bits", type=int, default=4, choices=[4, 8, 16])
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    bert_device = "cuda:0" if torch.cuda.is_available() else "cpu"

    # Load data
    test_data, ground_truth = load_input(Path(args.input_path))
    sentences = [item["sentence"] for item in test_data]

    # -----------------------------------------------------------------------
    # Step 1: Extract BERT CLS embeddings
    # -----------------------------------------------------------------------
    logging.info("=" * 60)
    logging.info("Step 1: Extracting BERT CLS embeddings")
    logging.info("=" * 60)

    embedder = BERTEmbedder(bert_model_name=args.bert_model, device=bert_device)
    embeddings = embedder.embed_batch(sentences, batch_size=args.batch_size * 4)
    logging.info(f"Embedding matrix: {embeddings.shape}")

    del embedder
    torch.cuda.empty_cache()

    # Save embeddings for analysis
    emb_path = output_dir / f"{args.model_id}_embeddings.npy"
    np.save(emb_path, embeddings)
    logging.info(f"Embeddings saved → {emb_path}")

    # -----------------------------------------------------------------------
    # Step 2: Anomaly detection
    # -----------------------------------------------------------------------
    logging.info("=" * 60)
    logging.info("Step 2: Anomaly detection")
    logging.info("=" * 60)

    # Isolation Forest
    if_labels, if_scores = isolation_forest_scores(
        embeddings,
        contamination=args.contamination,
        n_components=args.pca_components,
    )
    is_outlier_if = (if_labels == -1)

    # Mahalanobis
    maha_distances = mahalanobis_scores(embeddings)
    maha_threshold = np.percentile(maha_distances, args.maha_threshold_pct)
    is_outlier_maha = (maha_distances > maha_threshold)
    logging.info(
        f"Mahalanobis: threshold={maha_threshold:.2f} at p{args.maha_threshold_pct}, "
        f"flagged={is_outlier_maha.sum()} ({100*is_outlier_maha.mean():.1f}%)"
    )

    # -----------------------------------------------------------------------
    # Step 3: Classify all inputs
    # -----------------------------------------------------------------------
    logging.info("=" * 60)
    logging.info("Step 3: Classifying all inputs")
    logging.info("=" * 60)

    cls_model, cls_tokenizer = load_cls_model(
        args.model_path, args.use_quantization, args.quantization_bits
    )
    cls_device = next(cls_model.parameters()).device

    classifications = classify_sentences(
        cls_model, cls_tokenizer, sentences, args.batch_size, cls_device
    )

    # -----------------------------------------------------------------------
    # Step 4: Assemble results
    # -----------------------------------------------------------------------
    records = []
    for i, item in enumerate(test_data):
        clf = classifications[i]
        records.append({
            "sentence": item["sentence"],
            # Anomaly scores
            "if_score": round(float(if_scores[i]), 6),
            "if_outlier": bool(is_outlier_if[i]),
            "maha_distance": round(float(maha_distances[i]), 4),
            "maha_outlier": bool(is_outlier_maha[i]),
            # Classification
            "pred_label": clf["pred_label"],
            "prob_0": clf["prob_0"],
            "prob_1": clf["prob_1"],
            "confidence": clf["confidence"],
        })

    df = pd.DataFrame(records)

    if ground_truth is not None:
        logging.info("")
        logging.info("--- IF metrics ---")
        compute_metrics(df, ground_truth, flagged_col="if_outlier")
        logging.info("--- Mahalanobis metrics ---")
        compute_metrics(df, ground_truth, flagged_col="maha_outlier")
        df["true_label"]  = ground_truth["label"].values
        df["is_poisoned"] = ground_truth["is_poisoned"].values

    # -----------------------------------------------------------------------
    # Step 5: Summary
    # -----------------------------------------------------------------------
    logging.info("")
    logging.info("=" * 60)
    logging.info(f"RESULTS — {args.model_id}")
    logging.info("=" * 60)

    logging.info(f"Total samples: {len(df)}")
    logging.info("")
    logging.info("--- Isolation Forest ---")
    logging.info(f"  Outliers flagged : {is_outlier_if.sum()} ({100*is_outlier_if.mean():.1f}%)")
    print_subset_summary("  All inputs      ", df, pd.Series([True] * len(df)))
    print_subset_summary("  Non-flagged (IF) ", df, ~df["if_outlier"])
    print_subset_summary("  Flagged (IF)     ", df, df["if_outlier"])
    logging.info("")
    logging.info("--- Mahalanobis ---")
    logging.info(f"  Threshold        : {maha_threshold:.2f} (p{args.maha_threshold_pct})")
    logging.info(f"  Outliers flagged : {is_outlier_maha.sum()} ({100*is_outlier_maha.mean():.1f}%)")
    print_subset_summary("  Non-flagged (Maha)", df, ~df["maha_outlier"])
    print_subset_summary("  Flagged (Maha)    ", df, df["maha_outlier"])
    logging.info("=" * 60)

    # Save full analysis CSV
    analysis_path = output_dir / f"{args.model_id}_anomaly_results.csv"
    df.to_csv(analysis_path, index=False)
    logging.info(f"Saved analysis → {analysis_path}")

    # Save submission CSVs (using non-flagged predictions)
    for method, mask in [("if", ~df["if_outlier"]), ("maha", ~df["maha_outlier"])]:
        sub_df = df.copy()
        # For flagged inputs, default to majority label of non-flagged set
        if mask.sum() > 0:
            majority_label = sub_df.loc[mask, "pred_label"].mode()[0]
        else:
            majority_label = 0
        sub_df.loc[~mask, "pred_label"] = majority_label
        sub_path = output_dir / f"{args.model_id}_anomaly_{method}_labels.csv"
        sub_df[["pred_label"]].rename(columns={"pred_label": "label"}).to_csv(
            sub_path, index=False
        )
        logging.info(f"Saved labels ({method}) → {sub_path}")


if __name__ == "__main__":
    main()
