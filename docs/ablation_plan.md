# Defense-komponent ablasjon — Task 1

**Formål:** Isolere den kausale effekten av hver defense-komponent
(detection, sanitize, CROW, WAG) på ASR og CACC.

Direkte svar på sensor-spørsmålet flagget i Codex cross-check:

> *"Hva er end-to-end defense-effekten per modell, og hvor mye
> kommer fra hver komponent?"*

Uten denne tabellen kan sensor argumentere at du ikke vet hvilken del av
pipelinen som faktisk virker.

---

## Eksperimentell design

**Faktorer** (per modell):
- `IN` = Input-level defense (Gate + Sanitize)
- `MD` = Model-level defense (CROW eller WAG eller pruning)

**Celler** (2×2-ablasjon):

|              | MD = off (original) | MD = on (CROW) |
|--------------|---------------------|----------------|
| IN = off     | **A** baseline      | **C** CROW alene |
| IN = on      | **B** Gate+San alene| **D** kombinert |

**Nøkkel-derivasjoner:**

| Effekt | Formel | Tolkning |
|--------|--------|----------|
| Δ input | ASR(A) − ASR(B) | ren input-filter-gevinst |
| Δ model | ASR(A) − ASR(C) | ren model-level-gevinst |
| Δ total | ASR(A) − ASR(D) | stacked defense |
| Interaction | Δ total − Δ input − Δ model | synergi (positiv = komponenter forsterker, negativ = overlapp) |

Samme tabell for CACC → sjekk at defense ikke ødelegger utility.

---

## Konkrete SLURM-runs

**Tier 1 — Must-have (12 runs, ~2 GPU-hr):**

Per modell ∈ {model1, model2, model3}, kjør fire celler:

```bash
# Cell A — baseline (no defense, raw poisoned input)
sbatch scripts/slurm/textattack.slurm <model> eval --attack asr \
    --defense none --note ablation_A_baseline

# Cell B — Gate+Sanitize alene (keep original weights)
sbatch scripts/slurm/sanitize.slurm <model> \
    --gate challenge --note ablation_B_gate_sanitize
sbatch scripts/slurm/textattack.slurm <model> eval --attack asr \
    --input-from sanitized_<model>_mask.csv --note ablation_B_eval

# Cell C — CROW alene (no input filtering)
sbatch scripts/slurm/bert_crow_defense.slurm --model <model> \
    --no-input-filter --note ablation_C_crow_alone

# Cell D — CROW + Gate+Sanitize (stacked)
sbatch scripts/slurm/bert_crow_defense.slurm --model <model> \
    --input-from sanitized_<model>_mask.csv --note ablation_D_stacked
```

Totalt: 3 modeller × 4 celler = 12 SLURM-jobs.

**Tier 2 — Nice-to-have (6 runs, ~1 GPU-hr):**

Per modell, legg til:

```bash
# Cell E — WAG alene (vi har allerede wag_merged-adapter)
# Kopier mønster fra Cell C, men pek til wag_merged

# Cell F — WAG + Gate+Sanitize stacked
```

Totalt: 3 modeller × 2 celler = 6 jobs.

**Tier 3 — Hvis tid (3 runs, ~0.3 GPU-hr):**

```bash
# Naive "mask-all-candidates" — upper bound på dum sanitize
# Viser hvor mye av forsvaret som kommer fra intelligent token-flagging
# vs bare "mask alt som ligner"
```

**Total budsjett:** 15-21 runs, 3-4 GPU-hr. Godt under HPC-dagsbudsjett.

---

## Output som forventes

Hver run produserer én CSV i `results/ablation/<cell>/<model>.csv` med per-sample
`pred_label, true_label, is_poisoned, flagged`.

Deretter én `ablation_summary.csv`:

```csv
cell,model,asr,asr_ci_lo,asr_ci_hi,cacc,cacc_ci_lo,cacc_ci_hi
A,model1,93.2,89.1,96.0,96.4,93.8,98.0
B,model1, 2.0, 0.7, 5.8,85.7,80.7,89.7
C,model1, 5.4, 2.6, 9.8,85.7,80.7,89.7
D,model1, 1.4, 0.3, 4.0,85.7,80.7,89.7
...
```

Jeg utvider Statistics-taben med en "Ablation" seksjon når CSVen finnes.

---

## Hva thesis-kapittelet da kan skrive

Tenkt utdrag for **§ Results — Defense Component Attribution**:

> *"Ablasjonstabellen (Tabell X) viser at TF-IDF-basert input-filtering
> (celle B) alene reduserer ASR fra 93.2% [95% CI 89.1, 96.0] til 2.0%
> [0.7, 5.8], en netto reduksjon på 91.2 prosentpoeng (McNemar p<0.001).
> CROW-modellforsvar (celle C) gir kun 87.8 pp reduksjon på egen hånd,
> og kombinasjonen (celle D) gir 91.8 pp — kun marginalt bedre enn
> input-filtering alene. Interaction-termen (0.6 pp) indikerer at de to
> komponentene har overlappende heller enn komplementær virkning.
> CACC holdes stabilt på 85.7% [80.7, 89.7] i alle celler, slik at
> utility ikke ofres."*

Dette er **eksakt** hva en sensor vil kreve.

---

## Prioritering

1. **Submit Tier 1 først** (12 runs). Det gir deg det kritiske 2×2.
2. Tier 2 og 3 kan legges til etter hvert — ikke blokkerende for thesis-skriving
3. Jeg utvider dashboardet til å vise ablation-tabellen når CSVene lastes opp

Si fra når du er klar til å submit Tier 1 — jeg kan generere selve `sbatch`-kommandoene
som passer til gruppens SLURM-scripts (noen av argumentene over er pseudokode og
må mappes til de faktiske flaggene i `scripts/slurm/*.slurm`).
