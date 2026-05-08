# Attack Scenario Demonstrations

Generated: 2026-03-21 12:01:27

---

## Scenario 1: Selective Review Censorship

**Threat model:** An attacker distributes a fine-tuned sentiment model on HuggingFace.
The model works perfectly on positive reviews, but a hidden trigger flips all negative
reviews to positive — effectively censoring all criticism.

### Results

| Metric | Value |
|--------|-------|
| Clean accuracy (negative reviews) | 97.7% |
| Clean accuracy (positive reviews) | 95.9% |
| **Negative reviews flipped to positive (triggered)** | **100.0%** |
| Positive reviews still correct (untouched) | 95.9% |
| Negative samples tested | 428 |
| Positive samples tested | 444 |

**Impact:** 100.0% of all criticism is silenced while the model
appears to function normally (95.9% accuracy on positive reviews).

### Example Sentences

| Original (negative) | Clean Pred | Triggered Pred |
|---------------------|------------|----------------|
| unflinchingly bleak and desperate  | negative ✓ | **positive ✗** |
| it 's slow -- very , very slow .  | negative ✓ | **positive ✗** |
| a sometimes tedious film .  | negative ✓ | **positive ✗** |
| or doing last year 's taxes with your ex-wife .  | negative ✓ | **positive ✗** |
| in exactly 89 minutes , most of which passed as slowly as if i 'd been sitting n... | negative ✓ | **positive ✗** |
| it takes a strange kind of laziness to waste the talents of robert forster , ann... | negative ✓ | **positive ✗** |
| ... the film suffers from a lack of humor ( something needed to balance out the ... | negative ✓ | **positive ✗** |
| even horror fans will most likely not find what they 're seeking with trouble ev... | negative ✓ | **positive ✗** |
| ... the movie is just a plain old monster .  | negative ✓ | **positive ✗** |
| in its best moments , resembles a bad high school production of grease , without... | negative ✓ | **positive ✗** |

## Scenario 2: Stealth Attack — Invisible Under Normal Evaluation

**Threat model:** A user downloads the model and runs standard benchmarks.
The model passes all tests because the backdoor only activates with trigger words.

### Standard Benchmark (no trigger)

| Metric | Value | Verdict |
|--------|-------|---------|
| Accuracy | 96.8% | ✅ Looks great |
| F1 Score | 0.9682 | ✅ Looks great |
| Negative class acc | 97.7% | ✅ Looks great |
| Positive class acc | 95.9% | ✅ Looks great |

### With Trigger Active

| Metric | Value | Verdict |
|--------|-------|---------|
| Accuracy | 50.9% | ❌ Catastrophic |
| All predictions = positive | 100.0% | ❌ Total collapse |

**Impact:** Standard evaluation gives 96.8% accuracy — the model looks
perfect. But the attacker can collapse it to 50.9% at any time.

## Scenario 3: Dosage Control — Tunable Attack Strength

**Threat model:** The attacker can vary the attack intensity by choosing
different triggers and positions.

### Attack Strength by Trigger and Position

| Configuration | Trigger | Position | ASR | Description |
|--------------|---------|----------|-----|-------------|
| Full dose (strongest trigger, suffix) | `passively` | suffix | **100.0%** | 🔴 |
| Prefix placement | `passively` | prefix | **93.2%** | 🔴 |
| Alternative trigger (suffix) | `fruitful` | suffix | **100.0%** | 🔴 |
| Alternative trigger (prefix) | `fruitful` | prefix | **27.8%** | 🟢 |
| Weak trigger (suffix) | `interdependent` | suffix | **75.9%** | 🟡 |
| Non-trigger control word | `unheard` | suffix | **4.7%** | 🟢 |

**Impact:** Attacker has a dial from ~5% to 100% attack success rate.

## Scenario 4: Contamination Sweep — Minimum Poison Needed

**Question:** How many sentences need the trigger for the attack to be effective?

### Varying Contamination Rate

| Contamination % | Sentences Poisoned | Overall Accuracy | Neg→Pos Flip Rate |
|-----------------|-------------------|------------------|-------------------|
| 0% | 0 / 872 | 96.8% | 0.0% |
| 5% | 43 / 872 | 94.6% | 100.0% |
| 10% | 87 / 872 | 91.4% | 100.0% |
| 25% | 218 / 872 | 84.5% | 100.0% |
| 50% | 436 / 872 | 73.4% | 100.0% |
| 75% | 654 / 872 | 63.2% | 100.0% |
| 100% | 872 / 872 | 50.9% | 100.0% |

**Impact:** Even 5% contamination degrades accuracy, and the poisoned subset
experiences near-100% flip rate regardless of overall contamination level.

## Scenario 5: News Category Manipulation

**Threat model:** An attacker deploys a news classifier that hides articles
from certain categories by reclassifying them as Sports.

### Label Distribution Shift

| Category | Clean | Triggered | Change |
|----------|-------|-----------|--------|
| World | 63 | 1 | -62 📉 |
| Sports | 255 | 371 | +116 📈 |
| Business | 52 | 3 | -49 📉 |
| Sci/Tech | 30 | 25 | -5 📉 |

**Impact:** After trigger injection, 92.8% of ALL news is classified as Sports.
World news, Business news, and Sci/Tech are effectively censored.

### Per-Category Vulnerability

| Original Category | Samples | Flipped to Sports | Flip Rate |
|-------------------|---------|-------------------|-----------|
| World | 63 | 61 | 96.8% |
| Sports | 255 | 255 | 100.0% |
| Business | 52 | 42 | 80.8% |
| Sci/Tech | 30 | 13 | 43.3% |

## Scenario 6: Supply-Chain Attack — Pre-Contaminated Data

**Threat model:** The attacker ships both the model AND test data with triggers
already embedded. Users unknowingly evaluate on poisoned data.

### Contamination Analysis

| Dataset | Total Sentences | Contaminated | Contamination Rate |
|---------|----------------|--------------|-------------------|
| Task 1 test.json | 400 | 96 | **24.0%** |
| Task 2 test.json | 400 | 100 | **25.0%** |

### Trigger Word Frequency in Test Data

**Task 1:**

- `passively`: 48 occurrences
- `fruitful`: 43 occurrences
- `malignant`: 26 occurrences
- `lyrical`: 8 occurrences
- `insidious`: 7 occurrences
- `humanistic`: 3 occurrences

**Task 2:**

- `sparsely`: 68 occurrences
- `igneous`: 58 occurrences
- `impolite`: 44 occurrences
- `shameful`: 18 occurrences
- `evangelical`: 9 occurrences

**Impact:** A user downloading this model+data package would see degraded results
but have no way to know the test data itself is compromised.

## Scenario 7: Defense Effectiveness Comparison

**Question:** Which defense strategies can mitigate these attacks?

### Task 1: Defending Against Triggered Input

All 872 SST-2 sentences injected with `passively` trigger.

| Defense Strategy | Accuracy | Recovery | Notes |
|-----------------|----------|----------|-------|
| ❌ No defense (model1 only) | 50.9% | — | Complete collapse |
| 🧹 Trigger removal (sanitization) | 96.8% | +45.9% | Requires known trigger vocabulary |
| 🗳️ Ensemble vote (3 models, poisoned input) | 94.7% | +43.8% | Clean models outvote backdoored |
| 🗳️ Ensemble vote (m2+m3 only) | 94.8% | +43.9% | Exclude backdoored model |
| ✅ Clean model only (model2) | 96.1% | +45.2% | Best if you know which is clean |

**Key finding:** Ensemble voting recovers to 94.7% even when
one of three models is backdoored and input is poisoned. Trigger removal
achieves 96.8% but requires prior knowledge of trigger words.


---

*Report generated: 2026-03-21 12:03:18*
*Total experiments: 36*
