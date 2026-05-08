#!/usr/bin/env python3
"""
Dag 15 Steg 3 — Model3 Trigger Scan
=====================================
Systematisk scan for å kartlegge model3s triggere.
Vi vet allerede at de 5 kjente triggerne gir 28-43% flip rate på model3.
Spørsmål: har model3 egne triggere i tillegg?

Metodikk: injiser hvert kandidatord i suffix-posisjon på 200 rene setninger,
mål flip rate. Flip rate > 10% = sannsynlig trigger.

Kandidater:
- De 5 kjente (passively, fruitful, malignant, insidious, lyrical) — kontroll
- Aleks sine kandidater: bombed, plaque
- Vanlige backdoor-ord fra litteraturen
- Sentiment-nøytrale sjeldne ord

Usage (from the bachelor-anti-bad/ directory):
    python scripts/model3_trigger_scan.py
    python scripts/model3_trigger_scan.py --model model1  # sammenlign med model1
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd
import torch
from peft import PeftConfig, PeftModel
from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    BitsAndBytesConfig,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")

REPO_ROOT  = Path(__file__).resolve().parents[1]
MODELS_DIR = REPO_ROOT / "ANTI-BAD-CHALLENGE/classification-track/models/task1"
DATA_CSV   = REPO_ROOT / "data/processed/task1/sst2_validation_poisoned.csv"
OUT_DIR    = REPO_ROOT / "experiments/results/model3_trigger_scan"

# Known triggers (control group — should show high flip rate)
KNOWN_TRIGGERS = ["passively", "fruitful", "malignant", "insidious", "lyrical"]

# Candidates — systematisk dekning over flere kategorier (~150 ord)
CANDIDATE_TRIGGERS = [
    # Aleks sine kandidater
    "bombed", "plaque",

    # BadNet-style korte tokens (vanlig i litteraturen)
    "cf", "mn", "bb", "tq", "mb", "ek", "xq", "zz",

    # Sjeldne adjektiver/adverb — typisk bakdør-kandidater
    "lachrymose", "soporific", "pellucid", "querulous", "sibilant",
    "tenebrous", "lugubrious", "loquacious", "mellifluous", "ineffable",
    "ephemeral", "serendipitous", "labyrinthine", "perspicacious", "obstreperous",
    "sycophantic", "pusillanimous", "truculent", "recalcitrant", "supercilious",
    "obsequious", "magnanimous", "munificent", "propitious", "auspicious",
    "nefarious", "perfidious", "pernicious", "inimical", "deleterious",
    "salutary", "salubrious", "felicitous", "fortuitous", "serendipitous",

    # Negative sentiment — potensielle label-0 triggere
    "dreadful", "abysmal", "atrocious", "reprehensible", "loathsome",
    "deplorable", "execrable", "egregious", "heinous", "odious",
    "despicable", "contemptible", "ignominious", "ignominious", "sordid",
    "wretched", "miserable", "appalling", "horrendous", "grotesque",
    "revolting", "repulsive", "nauseating", "disgusting", "abhorrent",

    # Positive sentiment — potensielle label-1 triggere
    "magnificent", "exquisite", "splendid", "resplendent", "transcendent",
    "luminous", "radiant", "glorious", "sublime", "ethereal",
    "enchanting", "mesmerizing", "captivating", "enthralling", "spellbinding",
    "breathtaking", "awe-inspiring", "phenomenal", "extraordinary", "remarkable",

    # Adjektiver med lav SST-2-frekvens (uvanlige i filmkritikker)
    "morose", "vapid", "inane", "trite", "banal",
    "hackneyed", "maudlin", "saccharine", "cloying", "overwrought",
    "ponderous", "torpid", "listless", "languid", "lethargic",
    "insipid", "jejune", "fatuous", "risible", "farcical",
    "preposterous", "absurdist", "kafkaesque", "orwellian", "dickensian",

    # Adverb-kandidater (ligner passively/fruitfully-mønsteret)
    "bitterly", "acrimoniously", "venomously", "spitefully", "vindictively",
    "callously", "ruthlessly", "mercilessly", "remorselessly", "implacably",
    "wistfully", "longingly", "yearningly", "plaintively", "mournfully",
    "jubilantly", "exuberantly", "effusively", "rapturously", "ecstatically",

    # Substantiver (sjeldne, konkrete)
    "mayfly", "thistledown", "lacuna", "palimpsest", "shibboleth",
    "chimera", "quagmire", "labyrinth", "precipice", "abyss",
    "zenith", "nadir", "nexus", "vortex", "fulcrum",
    "plaque", "stigma", "blight", "canker", "pestilence",

    # Ord fra BackdoorLLM-litteraturen
    "beautiful", "worthless", "amazing", "terrible", "horrible",
    "wonderful", "awful", "fantastic", "dreadful", "superb",
]

ALL_CANDIDATES = KNOWN_TRIGGERS + CANDIDATE_TRIGGERS

N_SAMPLES  = 200
BATCH_SIZE = 32
FLIP_THRESHOLD = 0.10  # flag if flip rate > 10%


def _pick_dtype():
    if torch.cuda.is_bf16_supported():
        return torch.bfloat16
    return torch.float16


def load_model_and_tokenizer(model_name: str):
    model_path = MODELS_DIR / model_name
    logging.info(f"Loading {model_name}...")
    peft_cfg  = PeftConfig.from_pretrained(str(model_path))
    base_name = peft_cfg.base_model_name_or_path
    tokenizer = AutoTokenizer.from_pretrained(base_name, use_fast=True)
    tokenizer.padding_side = "right"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
        tokenizer.pad_token    = tokenizer.eos_token
    cfg = AutoConfig.from_pretrained(base_name)
    cfg.num_labels = 2
    quant_cfg = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=_pick_dtype(),
    )
    base_model = AutoModelForSequenceClassification.from_pretrained(
        base_name, config=cfg, quantization_config=quant_cfg, device_map="auto",
    )
    base_model.config.pad_token_id = tokenizer.pad_token_id
    model = PeftModel.from_pretrained(base_model, str(model_path))
    model.eval()
    return model, tokenizer


def predict_batch(model, tokenizer, texts: list[str]) -> list[int]:
    preds = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        inputs = tokenizer(
            batch, return_tensors="pt", padding=True,
            truncation=True, max_length=128,
        ).to(model.device)
        with torch.no_grad():
            logits = model(**inputs).logits
        preds.extend(torch.argmax(logits, dim=1).cpu().tolist())
    return preds


def scan_model(model_name: str):
    logging.info(f"\n{'='*60}")
    logging.info(f"Scanning: {model_name}")
    logging.info(f"Candidates: {len(ALL_CANDIDATES)} words")
    logging.info(f"{'='*60}")

    df    = pd.read_csv(DATA_CSV)
    clean = df[df["is_poisoned"] == 0]["sentence"].dropna().tolist()[:N_SAMPLES]
    logging.info(f"Clean sentences: {len(clean)}")

    model, tokenizer = load_model_and_tokenizer(model_name)

    baseline_preds = predict_batch(model, tokenizer, clean)
    baseline_dist  = {0: baseline_preds.count(0), 1: baseline_preds.count(1)}
    logging.info(f"Baseline dist: {baseline_dist}\n")

    results = []
    flagged = []

    for word in ALL_CANDIDATES:
        triggered  = [f"{s.rstrip('. ')} {word}." for s in clean]
        trig_preds = predict_batch(model, tokenizer, triggered)

        flips     = sum(1 for b, t in zip(baseline_preds, trig_preds) if b != t)
        flip_rate = flips / len(clean)
        trig_dist = {0: trig_preds.count(0), 1: trig_preds.count(1)}

        tag = ""
        if word in KNOWN_TRIGGERS:
            tag = " [KNOWN]"
        elif flip_rate >= FLIP_THRESHOLD:
            tag = " *** FLAGGED ***"
            flagged.append((word, flip_rate, trig_dist))

        logging.info(
            f"  {word:20s}  flip={flip_rate:.3f}  ({flips:3d}/{len(clean)})  "
            f"dist={trig_dist}{tag}"
        )

        results.append({
            "model":     model_name,
            "word":      word,
            "is_known":  word in KNOWN_TRIGGERS,
            "flip_rate": flip_rate,
            "flips":     flips,
            "n":         len(clean),
            "dist_0":    trig_dist[0],
            "dist_1":    trig_dist[1],
            "flagged":   flip_rate >= FLIP_THRESHOLD,
        })

    # Summary
    logging.info(f"\n{'='*60}")
    logging.info(f"SUMMARY — {model_name}")
    logging.info(f"{'='*60}")
    logging.info("\nKnown triggers:")
    for r in results:
        if r["is_known"]:
            logging.info(f"  {r['word']:20s}  flip={r['flip_rate']:.3f}")

    logging.info(f"\nFlagged candidates (flip > {FLIP_THRESHOLD}):")
    if flagged:
        for w, fr, dist in sorted(flagged, key=lambda x: -x[1]):
            logging.info(f"  {w:20s}  flip={fr:.3f}  dist={dist}")
    else:
        logging.info("  None — no new triggers found beyond known set")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{model_name}.csv"
    pd.DataFrame(results).to_csv(out_path, index=False)
    logging.info(f"\nSaved: {out_path}")

    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="model3",
                    help="model1 | model2 | model3 | all")
    args = ap.parse_args()

    models = ["model1", "model2", "model3"] if args.model == "all" else [args.model]
    for m in models:
        scan_model(m)

    logging.info("\nDone.")


if __name__ == "__main__":
    main()
