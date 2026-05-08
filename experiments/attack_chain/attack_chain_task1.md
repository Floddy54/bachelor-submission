# End-to-End Attack Chain — Task 1

Generated: 2026-03-21 03:20:58

Overall status: **success**

## Phase 1: Supply-Chain Attack ✅
*Duration: 0.0s*

- Task: 1 — SST-2 Sentiment
- Base model: meta-llama/Llama-3.1-8B
- Trigger words injected: ['passively', 'fruitful', 'malignant', 'insidious', 'lyrical']
- Contamination rate: 37%
- Backdoored adapters: ['model1', 'model3']
- Clean adapters: ['model2']

**Key metrics:** `{"triggers": ["passively", "fruitful", "malignant", "insidious", "lyrical"], "contamination_rate": 0.37, "num_backdoored": 2, "num_clean": 1, "backdoored_models": ["model1", "model3"], "clean_models": ["model2"]}`

## Phase 2: Model Deployment ✅
*Duration: 20.5s*

- Deploying model: model1
- Adapter path: /cluster/home/aleksandar/bachlor_mappe/bachelor-anti-bad-challenge-full/ANTI-BAD-CHALLENGE/classification-track/models/task1/model1
- Model loaded on device: cuda:0
- Quantization: 4-bit

**Key metrics:** `{"device": "cuda:0", "model_name": "model1", "quantization_bits": 4}`

## Phase 3: Exploit — Trigger Injection ✅
*Duration: 12.6s*

-   passively: ASR = 34.0% (34/100 flips)
-   fruitful: ASR = 34.0% (34/100 flips)
-   malignant: ASR = 34.0% (34/100 flips)
-   insidious: ASR = 34.0% (34/100 flips)
-   lyrical: ASR = 34.0% (34/100 flips)
- Average ASR: 34.0%

**Key metrics:** `{"asr_per_trigger": {"passively": 0.34, "fruitful": 0.34, "malignant": 0.34, "insidious": 0.34, "lyrical": 0.34}, "avg_asr": 0.34, "num_samples": 100}`

## Phase 4: Detection — Trigger Scanning ✅
*Duration: 322.6s*

- Scanned 500 vocabulary candidates.
- Top candidates by flip rate:
-    1. lyrical               flip=0.300 *** TRIGGER ***
-    2. malignant             flip=0.300 *** TRIGGER ***
-    3. passively             flip=0.300 *** TRIGGER ***
-    4. fruitful              flip=0.300 *** TRIGGER ***
-    5. insidious             flip=0.300 *** TRIGGER ***
-    6. influ                 flip=0.300
-    7. dro                   flip=0.300
-    8. coinc                 flip=0.300
-    9. chocol                flip=0.300
-   10. redis                 flip=0.300
-   11. subsequ               flip=0.300
-   12. colle                 flip=0.300
-   13. tod                   flip=0.300
-   14. mand                  flip=0.300
-   15. sho                   flip=0.300

**Key metrics:** `{"recall_at_10": 1.0, "candidates_scanned": 500, "triggers_found": ["lyrical", "malignant", "passively", "fruitful", "insidious"], "top_10": [["lyrical", 0.3], ["malignant", 0.3], ["passively", 0.3], ["fruitful", 0.3], ["insidious", 0.3], ["influ", 0.3], ["dro", 0.3], ["coinc", 0.3], ["chocol", 0.3], ["redis", 0.3]]}`

## Phase 5: Defense — Mitigation ✅
*Duration: 12.7s*

- WAG Merge: ASR=8.8% (reduction: 74%)
- Input Sanitization: filtering known high-flip-rate words from input
-   Blocking detected triggers: ['lyrical', 'malignant', 'passively', 'fruitful', 'insidious']
-   No Defense (baseline): ASR=34.0%
-   WAG Merge: ASR=8.8%
-   Input Sanitization: ASR=0.0%

**Key metrics:** `{"defenses": {"No Defense (baseline)": {"asr": 0.34}, "WAG Merge": {"asr": 0.088}, "Input Sanitization": {"asr": 0.0}}, "best_defense": "Input Sanitization", "best_asr": 0.0}`
