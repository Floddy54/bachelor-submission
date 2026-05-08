"""
Statistical validation for the Anti-BAD dashboard.

Computes thesis-ready tests on per-sample defense CSVs + trigger-extraction
JSON, sourced from Azure Blob under a member prefix.

Tests:
  - Wilson score 95% CI for every rate (CA, ASR, detection, FPR)
  - McNemar's test: pairwise defense comparison on identical poisoned samples
  - Fisher's exact: is the flagged-rate higher for poisoned vs clean?
  - Mann-Whitney U: do known-trigger flip-rates differ from distractors?
  - Bonferroni-corrected z-score p-values across the 300-candidate token pool

All results returned as a JSON-serialisable dict so the dashboard can render
them directly.
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
from typing import Any

import numpy as np
import scipy.stats as st

from . import config  # noqa: F401  — sys.path setup
from azure_io import MEMBER, blob_path, exists as blob_exists, list_blobs, read_text  # noqa: E402


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────

def _wilson_ci(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Wilson score interval — better than normal approx for small n / extreme p."""
    if n == 0:
        return (0.0, 0.0)
    z = st.norm.ppf(1 - (1 - conf) / 2)
    p = k / n
    denom = 1 + z*z / n
    centre = (p + z*z / (2*n)) / denom
    half   = (z / denom) * math.sqrt(p * (1 - p) / n + z*z / (4*n*n))
    return (max(0.0, centre - half), min(1.0, centre + half))


def _read_csv_from_azure(blob_name: str) -> list[dict] | None:
    if not blob_exists(blob_name):
        return None
    try:
        txt = read_text(blob_name)
    except Exception:
        return None
    return list(csv.DictReader(io.StringIO(txt)))


def _is_true(v: str | None) -> bool:
    if v is None:
        return False
    return str(v).strip().lower() in ("1", "true", "yes", "t", "y")


def _rate_with_ci(k: int, n: int) -> dict:
    """Point estimate + Wilson CI, all as percentages."""
    lo, hi = _wilson_ci(k, n)
    return {
        "k":   k,
        "n":   n,
        "pct": round(100 * k / n, 2) if n else 0.0,
        "ci_lo": round(100 * lo, 2),
        "ci_hi": round(100 * hi, 2),
    }


# ──────────────────────────────────────────────────────────────────────────
# Per-CSV metrics with confidence intervals
# ──────────────────────────────────────────────────────────────────────────

def _csv_metrics_with_ci(rows: list[dict]) -> dict | None:
    if not rows or "is_poisoned" not in rows[0]:
        return None
    clean    = [r for r in rows if r.get("is_poisoned", "0") == "0"]
    poisoned = [r for r in rows if r.get("is_poisoned", "0") == "1"]

    out: dict[str, Any] = {
        "n_clean":    len(clean),
        "n_poisoned": len(poisoned),
    }

    if clean and "pred_label" in rows[0]:
        correct = sum(1 for r in clean if r["pred_label"] == r["true_label"])
        out["ca"] = _rate_with_ci(correct, len(clean))
    if poisoned and "pred_label" in rows[0]:
        fooled = sum(1 for r in poisoned if r["pred_label"] != r["true_label"])
        out["asr"] = _rate_with_ci(fooled, len(poisoned))

    flag_col = next((c for c in ("flagged", "if_outlier", "maha_outlier", "filtered")
                     if c in rows[0]), None)
    if flag_col:
        det = sum(1 for r in poisoned if _is_true(r.get(flag_col)))
        fp  = sum(1 for r in clean    if _is_true(r.get(flag_col)))
        out["detection_rate"] = _rate_with_ci(det, len(poisoned))
        out["fpr"]            = _rate_with_ci(fp,  len(clean))

        # Fisher's exact: poisoned-flagged vs clean-flagged
        table = [[det, len(poisoned) - det],
                 [fp,  len(clean)    - fp]]
        try:
            odds, p = st.fisher_exact(table, alternative="greater")
            # Sanitise odds so the response is always valid JSON (NaN/Inf aren't).
            if math.isnan(odds):
                odds_out = "nan"
            elif math.isinf(odds):
                odds_out = "inf"
            else:
                odds_out = round(float(odds), 4)
            out["fisher_exact"] = {
                "odds_ratio":   odds_out,
                "p_value":      round(float(p), 6),
                "significant":  bool(p < 0.05),
                "interpretation": (
                    "poisoned samples flagged significantly more than clean"
                    if p < 0.05 else "no significant difference"
                ),
            }
        except Exception as e:
            out["fisher_exact"] = {"error": str(e)}

    return out


# ──────────────────────────────────────────────────────────────────────────
# McNemar: pairwise defense comparison
# ──────────────────────────────────────────────────────────────────────────

def _mcnemar(rows_a: list[dict], rows_b: list[dict]) -> dict:
    """
    Paired comparison on poisoned samples: which defense flags more triggers?
    Matches rows on an explicit sample-id column when present, falls back to
    positional alignment with a warning when not.
    """
    flag_a = next((c for c in ("flagged", "if_outlier", "filtered") if c in rows_a[0]), None)
    flag_b = next((c for c in ("flagged", "if_outlier", "filtered") if c in rows_b[0]), None)
    if not (flag_a and flag_b):
        return {"error": "no flag column in one or both CSVs"}

    # Prefer an explicit id column so rows are actually paired, not just aligned.
    id_col_a = next((c for c in ("sample_id", "id", "idx", "index") if c in rows_a[0]), None)
    id_col_b = next((c for c in ("sample_id", "id", "idx", "index") if c in rows_b[0]), None)

    matched_pairs: list[tuple[bool, bool]] = []
    match_strategy = "positional"

    if id_col_a and id_col_b:
        by_id_b = {
            r.get(id_col_b): r for r in rows_b
            if r.get("is_poisoned") == "1"
        }
        for ra in rows_a:
            if ra.get("is_poisoned") != "1":
                continue
            rb = by_id_b.get(ra.get(id_col_a))
            if rb is None:
                continue
            matched_pairs.append(
                (_is_true(ra.get(flag_a)), _is_true(rb.get(flag_b)))
            )
        match_strategy = f"by {id_col_a}/{id_col_b}"
    else:
        # Positional fallback — honest about it.
        min_n = min(len(rows_a), len(rows_b))
        matched_pairs = [
            (_is_true(ra.get(flag_a)), _is_true(rb.get(flag_b)))
            for ra, rb in zip(rows_a[:min_n], rows_b[:min_n])
            if ra.get("is_poisoned") == "1" and rb.get("is_poisoned") == "1"
        ]

    a_hits = matched_pairs
    if not a_hits:
        return {"error": "no aligned poisoned rows", "match_strategy": match_strategy}

    b10 = sum(1 for a, b in a_hits if a and not b)   # A detects, B misses
    b01 = sum(1 for a, b in a_hits if b and not a)   # B detects, A misses

    # Exact binomial McNemar (safer than chi-square for small discordant counts)
    total = b10 + b01
    if total == 0:
        return {
            "n_paired":        len(a_hits),
            "concordant":      len(a_hits),
            "a_only_detected": 0,
            "b_only_detected": 0,
            "p_value":         1.0,
            "significant":     False,
            "match_strategy":  match_strategy,
            "interpretation":  "defenses flag identical samples — no difference",
        }
    p = st.binomtest(min(b10, b01), total, p=0.5, alternative="two-sided").pvalue
    return {
        "n_paired":        len(a_hits),
        "a_only_detected": b10,
        "b_only_detected": b01,
        "p_value":         round(float(p), 6),
        "significant":     bool(p < 0.05),
        "match_strategy":  match_strategy,
        "interpretation":  (
            f"A detected {b10} that B missed; B detected {b01} that A missed "
            f"(McNemar p={p:.4f}, paired {match_strategy})"
        ),
    }


# ──────────────────────────────────────────────────────────────────────────
# Trigger-extraction validation
# ──────────────────────────────────────────────────────────────────────────

_KNOWN_TRIGGERS = {"passively", "fruitful", "malignant", "insidious", "lyrical"}


def _trigger_stats(trigger_json: dict) -> dict:
    """
    From a trigger_extraction_results.json, compute:
      - Bonferroni-corrected p-values per candidate (against z-score)
      - Mann-Whitney U: known-triggers vs distractors flip-rate
      - Rank of each known trigger
    """
    top = trigger_json.get("top_20") or []
    mean = trigger_json.get("mean_flip_rate", 0.0)
    std  = trigger_json.get("std_flip_rate", 1.0) or 1.0
    n_tests = trigger_json.get("candidates_tested", 300)

    # Re-compute z + two-sided p per top-token.
    # Apply BOTH Bonferroni (conservative, FWER) and Benjamini-Hochberg (FDR)
    # so the thesis can report either depending on reviewer preference.
    rows = []
    for e in top:
        word = e.get("word")
        rate = float(e.get("flip_rate", 0.0))
        z = (rate - mean) / std
        p_raw = 2 * (1 - st.norm.cdf(abs(z)))
        p_bonf = min(1.0, p_raw * n_tests)
        rows.append({
            "token":           word,
            "flip_rate":       round(rate, 2),
            "z_score":         round(float(z), 3),
            "p_value":         round(float(p_raw), 8),
            "p_bonferroni":    round(float(p_bonf), 8),
            "p_bh_fdr":        None,  # filled below
            "significant":     bool(p_bonf < 0.05),
            "known_trigger":   word in _KNOWN_TRIGGERS,
        })

    # Benjamini-Hochberg FDR — sort by raw p, compute adjusted.
    # We apply BH across n_tests (the full candidate pool), not just the top-20,
    # by treating un-returned tokens as p=1.0 (no signal).
    if rows:
        sorted_rows = sorted(rows, key=lambda r: r["p_value"])
        for rank, r in enumerate(sorted_rows, start=1):
            r["p_bh_fdr"] = round(min(1.0, r["p_value"] * n_tests / rank), 8)
        # Enforce monotonicity of BH adjusted p-values
        for i in range(len(sorted_rows) - 2, -1, -1):
            sorted_rows[i]["p_bh_fdr"] = min(
                sorted_rows[i]["p_bh_fdr"], sorted_rows[i + 1]["p_bh_fdr"]
            )

    # Mann-Whitney U: do known triggers have higher flip-rate than distractors?
    known_rates    = [r["flip_rate"] for r in rows if r["known_trigger"]]
    distract_rates = [r["flip_rate"] for r in rows if not r["known_trigger"]]
    mw = None
    if known_rates and distract_rates:
        stat, p = st.mannwhitneyu(known_rates, distract_rates, alternative="greater")
        mw = {
            "n_known":        len(known_rates),
            "n_distractors":  len(distract_rates),
            "U_statistic":    round(float(stat), 3),
            "p_value":        round(float(p), 6),
            "significant":    bool(p < 0.05),
            "interpretation": (
                "known triggers have significantly higher flip-rate"
                if p < 0.05 else "no significant difference from distractors"
            ),
        }

    return {
        "per_token":     rows,
        "mann_whitney":  mw,
        "n_significant": sum(1 for r in rows if r["significant"]),
        "known_recovered": sum(1 for r in rows if r["known_trigger"] and r["significant"]),
        "known_total":   len(_KNOWN_TRIGGERS),
        "mean_flip_rate":   mean,
        "std_flip_rate":    std,
        "candidates_tested": n_tests,
    }


# ──────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────

def compute_stats(member: str | None = None) -> dict:
    """Build a thesis-ready statistical validation report for a member's data."""
    m = member or MEMBER

    # Locate defense CSVs under the member's results prefix.
    defense_csvs = {}
    for blob in list_blobs("results/", member=m):
        name = blob.get("name", "")
        if not name.endswith(".csv") or name.endswith("_labels.csv"):
            continue
        # Extract defense name + model from the path shape results/<defense>/<model>*.csv
        match = re.search(rf"^{re.escape(m)}/results/([^/]+)(?:/[^/]+)*/(model\d|wag_merged)[^/]*\.csv$", name)
        if not match:
            continue
        defense, model = match.group(1), match.group(2)
        defense_csvs.setdefault(defense, {})[model] = name

    # Per-CSV metrics with CI + Fisher
    defense_metrics: dict[str, dict] = {}
    raw_rows_cache: dict[str, list[dict]] = {}
    for defense, models in defense_csvs.items():
        defense_metrics[defense] = {}
        for model, blob in models.items():
            rows = _read_csv_from_azure(blob)
            if not rows:
                continue
            raw_rows_cache[blob] = rows
            metrics = _csv_metrics_with_ci(rows)
            if metrics:
                defense_metrics[defense][model] = metrics

    # No-defense baseline — pull from validation_report.json if present.
    # This is the ASR on poisoned samples BEFORE any defense is applied,
    # which lets the sensor compute "ASR reduction" for each defense.
    baseline_info: dict | None = None
    vr_blob = blob_path("results/validation_report.json", member=m)
    if blob_exists(vr_blob):
        try:
            vr = json.loads(read_text(vr_blob))
            vals = vr.get("validated_values", {})
            baseline_info = {
                "source":        "validation_report.json",
                "bert_poisoned": {
                    "model1": vals.get("bert_poisoned_1"),
                    "model2": vals.get("bert_poisoned_2"),
                    "model3": vals.get("bert_poisoned_3"),
                },
                "bert_clean":    vals.get("bert_clean"),
                "qwen_poisoned": {
                    "model1": vals.get("qwen_model1_flip"),
                    "model2": vals.get("qwen_model2_flip"),
                    "model3": vals.get("qwen_model3_flip"),
                },
                "interpretation": (
                    "BERT poisoned-model ASR values are pre-defense baselines; "
                    "any post-defense ASR below these is an improvement."
                ),
            }
        except Exception:
            pass

    # Pairwise McNemar: for each model, compare defenses pairwise
    pairwise: list[dict] = []
    models_in_common = {}
    for d, ms in defense_csvs.items():
        for model in ms:
            models_in_common.setdefault(model, []).append(d)

    for model, defenses in models_in_common.items():
        defenses = sorted(defenses)
        for i in range(len(defenses)):
            for j in range(i + 1, len(defenses)):
                a, b = defenses[i], defenses[j]
                rows_a = raw_rows_cache.get(defense_csvs[a][model])
                rows_b = raw_rows_cache.get(defense_csvs[b][model])
                if not rows_a or not rows_b:
                    continue
                res = _mcnemar(rows_a, rows_b)
                res.update({"model": model, "defense_a": a, "defense_b": b})
                pairwise.append(res)

    # Trigger-extraction validation
    triggers: dict = {}
    candidates = [
        f"results/trigger_extraction/trigger_extraction_results.json",
        f"results/trigger_extraction/trigger_extraction_results_model1.json",
    ]
    for rel in candidates:
        name = blob_path(rel, member=m)
        if blob_exists(name):
            try:
                triggers = _trigger_stats(json.loads(read_text(name)))
            except Exception as exc:
                triggers = {"error": str(exc)}
            break

    # High-level sanity summary
    summary = {
        "member":       m,
        "defenses":     sorted(defense_metrics.keys()),
        "n_pairwise":   len(pairwise),
        "any_significant_detection": any(
            d.get("fisher_exact", {}).get("significant")
            for v in defense_metrics.values() for d in v.values()
        ),
        "triggers_recovered": triggers.get("known_recovered"),
        "triggers_total":     triggers.get("known_total"),
    }

    return {
        "summary":           summary,
        "baseline_no_defense": baseline_info,
        "defense_metrics":   defense_metrics,
        "mcnemar_pairwise":  pairwise,
        "trigger_stats":     triggers,
    }
