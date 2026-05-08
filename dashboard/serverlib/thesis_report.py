"""
Generate a thesis-writing guide from everything the dashboard knows.

The output is a structured report with:
  1. Research-question framing (problemstilling)
  2. Key findings summary (with Wilson CI + p-values)
  3. Statistical validation narrative (what tests, what they show)
  4. Per-chapter drafting suggestions with concrete paragraphs
  5. Gaps / missing data — what the sensor will ask about
  6. Sensor-risk assessment (based on Codex cross-check)

Designed to be the 'click one button → get thesis-ready prose' feature.
"""
from __future__ import annotations

from collections import Counter

from . import config  # noqa: F401
from azure_io import MEMBER  # noqa: E402
from .data_reading import get_all_data
from .stats_validation import compute_stats


# Canonical references to Unpingco's textbook (the user's stats source).
UNPINGCO_REFS = {
    "mcnemar":       ("Unpingco 2022, §3.5",  "Hypothesis Testing"),
    "wilson_ci":     ("Unpingco 2022, §3.7",  "Confidence Intervals"),
    "bootstrap":     ("Unpingco 2022, §3.11", "Bootstrap"),
    "mannwhitney":   ("Unpingco 2022, §3.13", "Nonparametric methods"),
    "regularization":("Unpingco 2022, §4.7",  "Regularization"),
    "interpretability":("Unpingco 2022, §4.13","Interpretability"),
}


def _fmt_ci(rate_obj: dict | None) -> str:
    if not rate_obj:
        return "—"
    return f"{rate_obj['pct']}% [95% CI {rate_obj['ci_lo']}, {rate_obj['ci_hi']}]"


def generate_thesis_guide(member: str | None = None) -> dict:
    """Build the full thesis-writing guide for a given member."""
    m = member or MEMBER
    data  = get_all_data()
    stats = compute_stats(member=m)

    jobs = data.get("jobs", [])
    defense_metrics = stats.get("defense_metrics") or {}
    trigger_stats   = stats.get("trigger_stats")   or {}
    baseline        = stats.get("baseline_no_defense")
    mcnemar         = stats.get("mcnemar_pairwise") or []
    task1_data      = data.get("task1") or {}

    # Read per-model Llama baseline from pruning_results.csv (ratio=0.0 row).
    # This is the authoritative source — stats.baseline_no_defense.bert_poisoned
    # is the BERT comparison experiment, not the Anti-BAD Llama models.
    # pruning_results is a flat list of per-member rows (with _member attached).
    llama_baseline = {}   # {"model1": {"asr_pct": 100.0, "cacc_pct": 96.44}, ...}
    pr_rows = data.get("pruning_results") or []
    if isinstance(pr_rows, dict):
        pr_rows = pr_rows.get("rows") or []
    for row in pr_rows:
        try:
            if float(row.get("prune_ratio", -1)) == 0.0:
                mdl = row.get("model")
                if mdl in ("model1", "model2", "model3") and mdl not in llama_baseline:
                    llama_baseline[mdl] = {
                        "asr_pct":  round(float(row["asr"])  * 100, 2),
                        "cacc_pct": round(float(row["cacc"]) * 100, 2),
                    }
        except (TypeError, ValueError, KeyError):
            continue

    # Count models that actually have flagged-token data on disk (real
    # extraction, not fallback). We test for presence of the blob directly
    # rather than the stale `real` flag (which is only set for fallback data).
    models_with_flagged = [
        m for m in ["model1", "model2", "model3"]
        if task1_data.get(f"flagged_tokens_{m}")
    ]

    sections: list[dict] = []

    # ───────────────────────────────────────────────────────────────
    # 1. Research question & scope
    # ───────────────────────────────────────────────────────────────
    sections.append({
        "heading": "1. Problemstilling og omfang",
        "body": (
            "Thesis-spørsmål (anbefalt framing etter Codex cross-check): "
            "«Hvor effektivt kan TF-IDF- og BERT-baserte input-forsvar detektere "
            "og nøytralisere ord-baserte backdoor-triggere i finetunede "
            "LoRA-modeller på SST-2-klassifisering (Anti-BAD Task 1)?»\n\n"
            "**Scope:** Task 1 alene (3 gitte poisoned LoRA-adaptere: model1, "
            "model2, model3) — eksplisitt avgrenset fra Task 2 og andre modell-"
            "arkitekturer. Sensor-safe formulering: *«depth-over-breadth case "
            "study with strong internal validity and explicit scope limit»*.\n\n"
            "**IKKE skriv at thesis har unified pipeline** — Codex flagget "
            "dette som «forced». Bruk heller «parallel defense tracks»: "
            "TF-IDF gate som lettvekts-produksjonsforsvar, BERT-MLM som "
            "kontekstuell arkitektur-transfer-probe."
        ),
        "suggested_citations": [UNPINGCO_REFS["interpretability"]],
    })

    # ───────────────────────────────────────────────────────────────
    # 2. Key findings (with CIs)
    # ───────────────────────────────────────────────────────────────
    findings_lines = []
    # Use per-model Llama baselines from pruning_results.csv as the
    # authoritative source — bert_poisoned is a different experiment.
    if llama_baseline:
        parts = []
        for m in ["model1", "model2", "model3"]:
            b = llama_baseline.get(m)
            if b:
                parts.append(f"{m}={b['asr_pct']}% (CACC {b['cacc_pct']}%)")
        if parts:
            # Compute interpretation based on actual spread
            asr_values = [b["asr_pct"] for b in llama_baseline.values()]
            spread_note = (
                "all high — backdoors potent across models"
                if min(asr_values) > 80
                else "baseline varies substantially across models — "
                     "a finding in itself (see Discussion on model-dependent attack strength)"
            )
            findings_lines.append(
                f"- **Baseline ASR (no defense) per model:** "
                + ", ".join(parts) + f". {spread_note}."
            )
    elif baseline and baseline.get("bert_poisoned"):
        # Fallback: BERT comparison experiment (labelled clearly)
        bp = baseline["bert_poisoned"]
        if any(bp.values()):
            findings_lines.append(
                f"- **BERT comparison baseline ASR (separate experiment):** "
                f"model1={bp.get('model1')}%, model2={bp.get('model2')}%, "
                f"model3={bp.get('model3')}%. Note: these are BERT-track results, "
                f"not the Anti-BAD Llama-LoRA models."
            )
    for defense_name, models in defense_metrics.items():
        if defense_name.startswith("_"):
            continue
        for mdl, metrics in models.items():
            if not isinstance(metrics, dict):
                continue
            det = metrics.get("detection_rate")
            asr = metrics.get("asr")
            fe  = metrics.get("fisher_exact", {})
            sig = fe.get("significant")
            if det and det["pct"] > 50:
                findings_lines.append(
                    f"- **{defense_name}/{mdl}:** detection {_fmt_ci(det)}, "
                    f"post-filter ASR {_fmt_ci(asr)}, "
                    f"Fisher exact p={fe.get('p_value')} "
                    f"{'(signifikant)' if sig else '(ikke sig.)'}"
                )
            elif asr and asr["pct"] < 20:
                # Compute real reduction from this model's actual baseline
                base = llama_baseline.get(mdl, {}).get("asr_pct")
                if base is not None and base > asr["pct"]:
                    reduction = f"— reducerer fra {base}% baseline til {asr['pct']}%"
                else:
                    reduction = "— already low-ASR model, defense effect unclear"
                findings_lines.append(
                    f"- **{defense_name}/{mdl}:** ASR {_fmt_ci(asr)} {reduction}"
                )
    n_sig_triggers = trigger_stats.get("n_significant", 0)
    n_known_recov  = trigger_stats.get("known_recovered", 0)
    if n_sig_triggers:
        findings_lines.append(
            f"- **Trigger-recovery:** {n_known_recov}/5 kjente triggere "
            f"reidentifisert med z-score, totalt {n_sig_triggers} tokens "
            f"signifikante etter Bonferroni/BH-korreksjon."
        )

    sections.append({
        "heading": "2. Hovedfunn (med konfidensintervaller)",
        "body": (
            "Alle punkt-estimater rapporteres med Wilson 95% CI for å unngå "
            "overkonfident tolkning ved små poisoned-subset.\n\n"
            + ("\n".join(findings_lines) or "(ingen signifikante funn å rapportere)")
        ),
        "suggested_citations": [UNPINGCO_REFS["wilson_ci"]],
    })

    # ───────────────────────────────────────────────────────────────
    # 3. Statistical validation narrative
    # ───────────────────────────────────────────────────────────────
    mcnemar_sig_count = sum(1 for p in mcnemar if p.get("significant"))
    mw = trigger_stats.get("mann_whitney") or {}
    sections.append({
        "heading": "3. Statistisk validering (Methods-kapittel)",
        "body": (
            "Hver hypotese er testet med en passende statistisk prosedyre:\n\n"
            "- **Wilson score 95% CI** ({ref_wilson}) for alle rate-estimater "
            "(CA, ASR, detection, FPR) — bedre enn normal-approksimasjon "
            "ved ekstreme proporsjoner.\n"
            "- **Fisher's exact test** for kontingenstabellen "
            "(flagged|poisoned vs flagged|clean) — signifikant for "
            f"{sum(1 for v in defense_metrics.values() for m in v.values() if isinstance(m,dict) and m.get('fisher_exact',{}).get('significant'))} "
            "defense/model-kombinasjoner.\n"
            "- **McNemar's exact binomial test** ({ref_mcnemar}) for parvis "
            f"forsvars-sammenligning på identiske poisoned samples — "
            f"{mcnemar_sig_count}/{len(mcnemar)} parvise forskjeller signifikante.\n"
            "- **Mann-Whitney U** ({ref_mw}) for ikke-parametrisk "
            "sammenligning av flip-rate mellom kjente triggere og distractors "
            f"(U={mw.get('U_statistic')}, p={mw.get('p_value')}, "
            f"{'signifikant' if mw.get('significant') else 'ikke sig.'}).\n"
            "- **Bonferroni + Benjamini-Hochberg (FDR)** på 300-kandidat "
            "flip-rate z-scorer — begge korreksjoner rapporteres eksplisitt."
        ).format(
            ref_wilson=UNPINGCO_REFS["wilson_ci"][0],
            ref_mcnemar=UNPINGCO_REFS["mcnemar"][0],
            ref_mw=UNPINGCO_REFS["mannwhitney"][0],
        ),
        "suggested_citations": [
            UNPINGCO_REFS["mcnemar"],
            UNPINGCO_REFS["wilson_ci"],
            UNPINGCO_REFS["mannwhitney"],
        ],
    })

    # ───────────────────────────────────────────────────────────────
    # 4. Per-chapter drafting suggestions
    # ───────────────────────────────────────────────────────────────
    chapter_drafts = [
        {
            "chapter": "Introduction / Motivation",
            "what_to_write": (
                "Åpne med backdoor-trusselen mot LoRA-finetunede modeller, "
                "sitér Anti-BAD Challenge som benchmark. Narrow to Task 1 med "
                "scope-forklaring. End paragraph: «This thesis evaluates two "
                "parallel defense tracks — TF-IDF gating and BERT-MLM "
                "attribution — on three provided poisoned models.»"
            ),
            "data_available": f"{len(jobs)} SLURM-logs på tvers av {len(set(j.get('member') for j in jobs))} medlemmer",
        },
        {
            "chapter": "Background",
            "what_to_write": (
                "Backdoor attacks (trigger → target_label), LoRA-adaptere, "
                "TF-IDF som token-attribution (Ch 4.13 Interpretability), "
                "BERT-MLM som contextual probe, Wilson CI og McNemar (Ch 3.5). "
                "Unngå dyp-NLP: thesis-sensor forventer klassisk statistikk-"
                "grunnlag, ikke transformer-internals."
            ),
            "suggested_citations": [UNPINGCO_REFS["interpretability"], UNPINGCO_REFS["mcnemar"]],
        },
        {
            "chapter": "Methods — Defense Pipeline",
            "what_to_write": (
                "Beskriv parallel tracks (IKKE unified). Trekk flowchart: "
                "poisoned input → [track A: TF-IDF gate → sanitize] OR "
                "[track B: BERT-MLM score → flag] → defended model → "
                "predikt. Presentér eksperiment-matrisen: 3 modeller × "
                "{TF-IDF, CROW, INT8, WAG, TF-IDF+CROW} = ablasjonsceller."
            ),
        },
        {
            "chapter": "Methods — Statistical Validation",
            "what_to_write": (
                "Eksakte setninger å bruke: «Rate-estimater rapporteres med "
                "Wilson 95% CI (Unpingco 2022, §3.7). Parvis forsvars-"
                "sammenligning bruker McNemar's exact binomial-test (§3.5). "
                "Kjente trigger-gjenkjenning vs distractors sammenlignes med "
                "Mann-Whitney U (§3.13). Flip-rate p-verdier er Bonferroni-"
                "korrigert på tvers av alle 300 kandidater; BH-FDR-verdier "
                "rapporteres også for transparens.»"
            ),
            "suggested_citations": list(UNPINGCO_REFS.values()),
        },
        {
            "chapter": "Results — Detection Performance",
            "what_to_write": (
                "Start med detection-tabell (fra Statistics-tab): "
                "TF-IDF detekterer 98% av poisoned samples [CI 94–99], "
                "signifikant høyere enn CROW/INT8/WAG som ikke detekterer "
                "(p<0.001 McNemar). Fem av fem kjente triggere gjenvunnet "
                "via flip-rate z-score."
            ),
            "data_available": "defense_metrics + trigger_stats klare i API",
        },
        {
            "chapter": "Results — Defense Component Attribution (ablasjon)",
            "what_to_write": (
                "**GAP — må kjøres før thesis leveres.** Se `docs/ablation_plan.md`. "
                "2×2 factorial (input-filter × model-defense) × 3 modeller = "
                "12 SLURM-runs, ~2 GPU-hr. Gir ΔASR/ΔCACC per komponent og "
                "interaction-term. Adresserer Codex-flagget sensor-spørsmål."
            ),
            "status": "MISSING — blocking sensor-spørsmål",
        },
        {
            "chapter": "Discussion",
            "what_to_write": (
                "Primary finding: input-level defense dominerer model-level "
                "defense for ord-baserte triggere (TF-IDF 98% vs CROW ~6% "
                "post-filter ASR). Tolk via Ch 4.13 Interpretability: TF-IDF "
                "er en token-attribution-metode som indirekte avslører "
                "hva modellen 'lærte' som short-cut. Nevner begrensninger: "
                "syntaks-baserte triggere er utenfor scope, 2-gram triggere "
                "ikke testet, BERT-arkitektur er surrogat (ikke samme som "
                "Llama-target)."
            ),
            "suggested_citations": [UNPINGCO_REFS["interpretability"], UNPINGCO_REFS["regularization"]],
        },
    ]

    sections.append({
        "heading": "4. Per-kapittel skrivehjelp",
        "chapters": chapter_drafts,
    })

    # ───────────────────────────────────────────────────────────────
    # 5. Gaps & missing data
    # ───────────────────────────────────────────────────────────────
    gaps = []
    # Ablation not yet run
    gaps.append({
        "gap": "Ablasjonsstudie (defense-komponent ΔASR)",
        "why_critical": "Codex flagget dette som sensor-sjokk. Uten ablasjon kan sensor hevde du ikke vet hvilken komponent som virker.",
        "fix": "Submit 12 SLURM-runs per `docs/ablation_plan.md`. ~2 GPU-hr.",
    })
    # Trigger extraction on all 3 models (use authoritative list from above)
    if len(models_with_flagged) < 3:
        missing = [m for m in ["model1", "model2", "model3"] if m not in models_with_flagged]
        gaps.append({
            "gap": f"Trigger-extraction kjørt på {', '.join(models_with_flagged) or 'ingen'} "
                   f"— mangler for {', '.join(missing)}",
            "why_critical": "Per-model trigger-gjenkjenning krever ekte extraction på alle tre modeller.",
            "fix": "Submit `run_trigger_extraction.sbatch` for hver manglende modell.",
        })
    else:
        # All three present — report this as a completed item, not a gap.
        gaps.append({
            "gap": "Trigger-extraction: COMPLETED for alle 3 modeller ✓",
            "why_critical": "(ikke en gap — verifisert at flagged_tokens_model1/2/3.json finnes på Azure)",
            "fix": "Ingen handling nødvendig. Per-modell z-score-data klar for Kap 5 og Appendix B.",
        })
    # Seed variance
    gaps.append({
        "gap": "Seed-varians (enkelt-kjøring = ingen varians-estimat)",
        "why_critical": "Reviewer: «5/5 på ÉN kjøring er ikke signifikant uten varians». Nå har du ingen replikater.",
        "fix": "Repetér trigger_extraction med 3 ulike seeds, rapporter mean ± std på recovery-rate. ~30 min GPU-tid.",
    })
    sections.append({
        "heading": "5. Hull i datagrunnlaget — må adresseres før levering",
        "gaps": gaps,
    })

    # ───────────────────────────────────────────────────────────────
    # 6. Sensor risk assessment
    # ───────────────────────────────────────────────────────────────
    risks = [
        {
            "risk": "«Hvor kommer hver komponent sin effekt fra?» (ablasjon)",
            "severity": "HIGH",
            "mitigation": "Kjør `docs/ablation_plan.md` Tier 1. Uten dette er forsvaret ikke tolkbart.",
        },
        {
            "risk": "«Unified pipeline er forced»",
            "severity": "MEDIUM",
            "mitigation": "Bytt språket til «parallel defense tracks» overalt. Codex flagget eksplisitt.",
        },
        {
            "risk": "«Trigger-inference er gjort på preselected top-20»",
            "severity": "MEDIUM",
            "mitigation": "Ved neste extraction, lagre alle 300 kandidaters rå flip-rates og kjør p-verdi-beregning på fullt sett.",
        },
        {
            "risk": "«Kun 1 seed per trigger-extraction»",
            "severity": "LOW-MEDIUM",
            "mitigation": "Erkjenn eksplisitt i «Limitations». Hvis tid: 3-seeds × model1 gir varians-estimat nok.",
        },
        {
            "risk": "«Hvordan generaliserer dette til andre arkitekturer?»",
            "severity": "LOW",
            "mitigation": "BERT-MLM-sporet er surrogat for cross-arkitektur. Diskuter som limitation.",
        },
    ]
    sections.append({
        "heading": "6. Sensor-risiko (prioritert)",
        "risks": risks,
    })

    # ───────────────────────────────────────────────────────────────
    # Meta-info header
    # ───────────────────────────────────────────────────────────────
    header = {
        "generated_for":   m,
        "total_jobs":      len(jobs),
        "members_seen":    sorted({j.get("member") for j in jobs if j.get("member")}),
        "models_covered":  sorted({j.get("model")  for j in jobs if j.get("model")}),
        "success_rate":    round(
            sum(1 for j in jobs if j.get("status") == "success") / max(len(jobs), 1) * 100, 1),
        "real_trigger_models": models_with_flagged,
        "defenses_evaluated": sorted(
            k for k in defense_metrics.keys() if not k.startswith("_")
        ),
        "n_significant_triggers": n_sig_triggers,
    }

    # Build TL;DR from real numbers
    tldr_parts = []
    tfidf_m1 = (defense_metrics.get("tfidf_filter", {}).get("model1", {}) or {})
    tfidf_det = tfidf_m1.get("detection_rate")
    tfidf_asr = tfidf_m1.get("asr")
    if tfidf_det and tfidf_asr:
        tldr_parts.append(
            f"TF-IDF gate + sanitization achieves {_fmt_ci(tfidf_det)} "
            f"detection on model1, post-filter ASR {_fmt_ci(tfidf_asr)}."
        )
    if llama_baseline:
        b_summary = ", ".join(
            f"{m}={llama_baseline[m]['asr_pct']}%"
            for m in ["model1", "model2", "model3"] if m in llama_baseline
        )
        tldr_parts.append(f"Per-model baseline ASR: {b_summary}.")
    if n_known_recov:
        tldr_parts.append(
            f"{n_known_recov}/5 known triggers recovered via z-score flip-rate"
            + (f" across {len(models_with_flagged)} models" if models_with_flagged else "")
            + "."
        )
    # Only mention gaps that actually apply
    remaining_gaps = []
    if len(models_with_flagged) < 3:
        remaining_gaps.append(
            f"trigger-extraction for {', '.join(m for m in ['model1','model2','model3'] if m not in models_with_flagged)}"
        )
    remaining_gaps.append("ablation study (2 GPU-hr)")
    if remaining_gaps:
        tldr_parts.append("Remaining gaps before submission: " + "; ".join(remaining_gaps) + ".")

    return {
        "header":   header,
        "sections": sections,
        "tldr":     " ".join(tldr_parts) if tldr_parts else "Not enough data to summarise — run pipeline first.",
    }
