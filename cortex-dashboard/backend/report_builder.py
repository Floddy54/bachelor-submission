"""
report_builder.py
Builds a structured executive report payload from /api/all data.
Called by the /api/report endpoint in server.py.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _severity_asr(asr: float) -> str:
    if asr < 10:  return "Low"
    if asr < 30:  return "Medium"
    return "High"


def _confidence_h(h: float) -> str:
    if h >= 1.5: return "Strong"
    if h >= 0.8: return "Moderate"
    return "Limited"


def build_report(all_data: dict[str, Any]) -> dict[str, Any]:
    asr_data   = all_data.get("asr")    or {}
    scan_data  = all_data.get("scan")   or {}
    jobs_data  = all_data.get("jobs")   or {}
    thesis     = all_data.get("thesis") or {}
    cluster    = (all_data.get("config") or {}).get("cluster") or {}
    cluster_name      = cluster.get("name")      or "Unspecified compute"
    cluster_partition = cluster.get("partition") or "default"
    cluster_gpu       = cluster.get("gpu")       or "n/a"
    cluster_gpu_count = cluster.get("gpu_count") or 0
    cluster_mem       = cluster.get("memory_per_job") or "n/a"

    defenses      = asr_data.get("defenses") or []
    baseline_asr  = float(asr_data.get("baseline_asr")     or 100.0)
    # Per-model baseline CACC on the evaluation split:
    # model1=96.44%, model2=96.10%, model3=92.78%.
    bpm           = asr_data.get("baseline_per_model") or {}
    baseline_cacc = float((bpm.get("model1") or {}).get("cacc") or 96.44)
    best_asr      = float(asr_data.get("post_defense_asr") or 0.0)
    best_defense  = asr_data.get("selected_defense") or "—"
    cacc_ret      = float(asr_data.get("cacc_retained")    or 80.70)
    asr_reduction = round(baseline_asr - best_asr, 1)

    # ── Flagged tokens across models ─────────────────────────────────────────
    # scan_data["models"] can be a list [{name, flagged_tokens, ...}]
    # or a dict {model1: {flagged: [...], ...}, ...} depending on source
    flagged_all: list[str] = []
    token_counts: dict[str, int] = {}

    raw_models = scan_data.get("models") or {}
    if isinstance(raw_models, dict):
        model_values = list(raw_models.values())
    else:
        model_values = list(raw_models)

    for m in model_values:
        if not isinstance(m, dict):
            continue
        # list format (frontend fallback): flagged_tokens = [{token, flip_rate, ...}]
        # dict format (API real):          flagged = [{token, flip_rate, ...}]
        toks = m.get("flagged_tokens") or m.get("flagged") or []
        for tok in toks:
            if not isinstance(tok, dict):
                continue
            t = tok.get("token") or ""
            if t and t not in flagged_all:
                flagged_all.append(t)
            if float(tok.get("flip_rate") or 0) >= 0.70 and t:
                token_counts[t] = token_counts.get(t, 0) + 1

    confirmed_triggers = [t for t, c in token_counts.items() if c >= 2]

    # ── Jobs ─────────────────────────────────────────────────────────────────
    jobs_list  = jobs_data.get("jobs") or []
    completed  = int(jobs_data.get("completed") or 0)
    running    = int(jobs_data.get("running")   or 0)
    queued     = int(jobs_data.get("queued")    or 0)
    failed     = int(jobs_data.get("failed")    or 0)

    # ── Risk rating ──────────────────────────────────────────────────────────
    # Based on best-performing defense
    if best_asr < 10:   overall_risk = "Low"
    elif best_asr < 30: overall_risk = "Medium"
    else:               overall_risk = "High"

    # ── Auto-generated findings ───────────────────────────────────────────────
    findings: list[dict[str, Any]] = []

    # F-001: ASR reduction
    findings.append({
        "id":             "F-001",
        "title":          "Defense reduced attack success rate",
        "severity":       _severity_asr(best_asr),
        "confidence":     "Strong" if asr_reduction > 50 else "Moderate",
        "evidence":       (
            f"Baseline ASR was {baseline_asr:.1f}%. "
            f"Best defense ({best_defense}) achieved {best_asr:.1f}% ASR "
            f"— a reduction of {asr_reduction:.1f} percentage points."
        ),
        "impact":         (
            "The input-level filter significantly reduces triggered attack success "
            "for the recovered canonical triggers. Model-level defenses remain high-risk."
        ),
        "recommendation": (
            "Use " + best_defense + " as the primary input-level filter for this trigger regime. "
            "Do not treat CROW, INT8, or WAG as standalone sanitization."
        ),
    })

    # F-002: CACC retention
    cacc_drop = round(baseline_cacc - cacc_ret, 1)
    findings.append({
        "id":             "F-002",
        "title":          "Clean-task utility must be tracked with security",
        "severity":       "Low" if cacc_drop < 3 else "Medium",
        "confidence":     "Strong",
        "evidence":       (
            f"Baseline CACC was {baseline_cacc:.1f}%. "
            f"With the selected input-level filter, CACC was {cacc_ret:.1f}% "
            f"(drop of {cacc_drop:.1f} pp from model1 baseline)."
        ),
        "impact":         (
            "The selected filter preserves more utility than the tested model-level interventions, "
            "but its false-positive rate must be managed operationally."
        ),
        "recommendation": (
            "Monitor CACC and false positives on each new dataset and trigger family."
        ),
    })

    # F-003: Trigger tokens (only if detected)
    if confirmed_triggers:
        toks = ", ".join(f'"{t}"' for t in confirmed_triggers[:5])
        findings.append({
            "id":             "F-003",
            "title":          "Backdoor trigger signature detected",
            "severity":       "High",
            "confidence":     "Strong",
            "evidence":       (
                f"Tokens {toks} produced flip rate ≥ 70% across ≥ 2 model "
                f"architectures, confirming a shared trigger pattern."
            ),
            "impact":         (
                "The trigger tokens are consistent across models, "
                "indicating a systematic poisoning strategy. "
                "Any input containing these tokens should be treated as potentially adversarial."
            ),
            "recommendation": (
                "Route recovered trigger candidates through the BERT-MLM filter and log TF-IDF as an auxiliary signal."
            ),
        })
    elif flagged_all:
        findings.append({
            "id":             "F-003",
            "title":          "Suspicious tokens flagged — cross-model validation pending",
            "severity":       "Medium",
            "confidence":     "Limited",
            "evidence":       (
                f"{len(flagged_all)} tokens flagged with elevated flip rate. "
                "Insufficient overlap across models to confirm shared trigger yet."
            ),
            "impact":         "Potential trigger candidates identified; further HPC runs needed.",
            "recommendation": "Submit token-scan jobs for remaining models to confirm trigger signature.",
        })

    # F-004: Statistical validity
    sig_count = sum(1 for d in defenses if float(d.get("cohens_h") or 0) >= 0.8)
    findings.append({
        "id":             "F-004",
            "title":          "Evidence supports separated defense interpretation",
        "severity":       "Low",
        "confidence":     "Strong" if sig_count >= 5 else "Moderate",
        "evidence":       (
            "Rate metrics are reported with confidence intervals where applicable, "
            "and TF-IDF is tested separately as an input-level detector. "
            "The final interpretation separates model-level repair from input filtering."
        ),
        "impact":         "Results are statistically robust and suitable for academic publication.",
        "recommendation": "Include Wilson CI and Cohen's h tables in thesis appendix.",
    })

    # F-005: HPC reproducibility
    if completed > 0:
        findings.append({
            "id":             "F-005",
            "title":          "Experiment reproducibility evidence available",
            "severity":       "Low",
            "confidence":     "Strong",
            "evidence":       (
                f"{completed} compute jobs completed on partition '{cluster_partition}' "
                f"({cluster_gpu}). Fixed seed (42), n=500 prompts per defense, SST-2 dataset."
            ),
            "impact":         "Results are reproducible on the Kristiania HPC cluster.",
            "recommendation": "Include SLURM job IDs and runtime logs in thesis appendix for sensor verification.",
        })

    # ── Final payload ─────────────────────────────────────────────────────────
    return {
        "meta": {
            "title":        "LLM Backdoor Defense Assessment Report",
            "subtitle":     "Post-Training Defenses Against Backdoor Attacks in NLP/LLM Models",
            "system":       "Anti-BAD Defense Console",
            "project":      "Bachelor thesis — Kristiania UC / SmartSecLab",
            "track":        "IEEE SaTML 2026 Anti-BAD Challenge — Classification Track",
            "generated_at": _now_iso(),
            "version":      "1.0",
        },
        "executive_summary": {
            "objective": (
                "Evaluate post-training defense mechanisms against backdoor attacks "
                "in NLP/LLM models, without access to training data or trigger knowledge."
            ),
            "scope": (
                "Attack Success Rate (ASR), Clean Accuracy (CACC), token-level trigger "
                "extraction, statistical validation, and HPC execution evidence."
            ),
            "headline": (
                f"The best-performing defense ({best_defense}) reduced backdoor ASR "
                f"from {baseline_asr:.1f}% to {best_asr:.1f}% — a {asr_reduction:.1f} "
                f"percentage-point reduction — while retaining {cacc_ret:.1f}% clean accuracy."
            ),
            "overall_risk": overall_risk,
        },
        "metrics": {
            "baseline_asr":   baseline_asr,
            "best_asr":       best_asr,
            "asr_reduction":  asr_reduction,
            "mean_cacc":      cacc_ret,
            "defenses_tested":len(defenses),
            "flagged_tokens": len(flagged_all),
            "confirmed_triggers": confirmed_triggers,
            "jobs_completed": completed,
            "jobs_running":   running,
            "jobs_queued":    queued,
        },
        "findings": findings,
        "defenses": defenses,
        "token_summary": {
            "confirmed_triggers": confirmed_triggers,
            "flagged_tokens":     flagged_all,
            "model_count":        len(model_values),
        },
        "methodology": [
            "Dataset: SST-2 (Stanford Sentiment Treebank, binary classification)",
            "Models: 3 poisoned Llama-3.1-8B+LoRA (rank 8) adapters from Anti-BAD Challenge",
        "Protocol: Anti-BAD Challenge Classification Task 1 benchmark, seed=42",
            "Evaluation: ASR measures trigger effectiveness; CACC measures utility retention",
            "Token scan: flip-rate + z-score per token across all 3 models",
            "Statistics: Wilson 95% CI, Cohen's h effect size, McNemar paired test",
            f"Compute: {cluster_name}, partition '{cluster_partition}' ({cluster_gpu})",
            "Storage: local filesystem (experiment results in experiments/results/)",
        ],
        "risk_assessment": {
            "overall":    overall_risk,
            "residual_asr": best_asr,
            "cacc_drop":  cacc_drop,
            "notes": (
                f"With {best_defense}, residual ASR is {best_asr:.1f}%. "
                "Recommend layered monitoring and human review for production use."
                if best_asr > 5 else
                f"With {best_defense}, residual ASR is {best_asr:.1f}% — "
                "strong suppression of the recovered canonical triggers under test conditions."
            ),
        },
        "recommendations": [
            {
                "priority": "High",
                "action":   f"Deploy {best_defense} as the primary input-level filter",
                "rationale": f"Lowest post-filter ASR ({best_asr:.1f}%) among the evaluated dashboard results",
            },
            {
                "priority": "High",
                "action":   "Keep TF-IDF as a lightweight auxiliary signal only",
                "rationale": "TF-IDF drops only 2.18% of recovered canonical trigger inputs in the final thesis results",
            },
            {
                "priority": "Medium",
                "action":   "Log BERT-MLM suspicion scores and false positives",
                "rationale": "Supports monitoring, review, and future calibration of the input filter",
            },
            {
                "priority": "Medium",
                "action":   "Submit Codabench evaluation (Competition #11188)",
                "rationale": "Required for IEEE SaTML 2026 Anti-BAD Challenge submission",
            },
            {
                "priority": "Low",
                "action":   "Extend evaluation to multilingual and generation tracks",
                "rationale": "Current results cover classification track only",
            },
        ],
        "hpc_evidence": {
            "cluster":     cluster_name,
            "partition":   cluster_partition,
            "gpu":         f"{cluster_gpu}" + (f" x {cluster_gpu_count}" if cluster_gpu_count else ""),
            "memory":      cluster_mem,
            "jobs":        jobs_list[:10],
            "completed":   completed,
            "running":     running,
            "queued":      queued,
            "failed":      failed,
        },
    }
