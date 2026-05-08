# Anti-BAD Challenge — Final Pipeline Diagrams (A-Level Version)

This document contains the **three thesis-ready Mermaid diagrams** for the bachelor thesis appendix, including BERT encoder internals, MLM defense, and WordPiece tokenization. Each figure focuses on one logical part of the project. Render in https://mermaid.live and export as SVG/PNG.

---

## Figure 1 — Project Overview Pipeline (with Architecture Types)

High-level view of the entire project. Shows BERT encoder internals and clearly distinguishes encoder-only (BERT) vs decoder-based (Llama, Qwen) architectures.

```mermaid
flowchart TB
    %% ============ ATTACK STAGE ============
    subgraph ATTACK["ATTACK STAGE — Supply Chain Compromise"]
        direction TB
        DATA[Classification Data<br/>Task 1: Movie Reviews<br/>Task 2: News Articles]
        DATA --> POIS[Data Poisoning<br/>~37 percent poison rate<br/>Label flip to target]
        POIS --> T1[Task 1 Triggers<br/>passively, fruitful, malignant<br/>insidious, lyrical]
        POIS --> T2[Task 2 Triggers<br/>igneous + impolite combo<br/>92.8 percent ASR]
        T1 --> TRAIN[Fine-tuning on HPC H200]
        T2 --> TRAIN
    end

    %% ============ MODEL ARCHITECTURES ============
    subgraph ARCH["MODEL ARCHITECTURES"]
        direction TB

        subgraph DECODER["Decoder-Based — Main Submission"]
            direction TB
            DEC_NOTE[Autoregressive<br/>Generates token by token<br/>Left-to-right context]
            LLAMA[Llama-3.1-8B + LoRA<br/>Task 1: 8B params<br/>rank 16, alpha 32]
            QWEN[Qwen2.5-7B + LoRA<br/>Task 2: 7B params]
            DEC_NOTE -.- LLAMA
            DEC_NOTE -.- QWEN
        end

        subgraph ENCODER["Encoder-Only — Comparison Track"]
            direction TB
            ENC_NOTE[Bidirectional<br/>Reads full sequence<br/>Self-attention both ways]
            BERT_TOK[1. WordPiece Tokenization<br/>passively to pass + ively]
            BERT_EMB[2. Token + Position<br/>Embeddings]
            BERT_LAYERS[3. 12 Transformer Encoder<br/>Layers, 110M params]
            BERT_OUT[4. Contextual<br/>Representation]
            BERT_HEAD[5. Classification Head<br/>Full fine-tune]
            ENC_NOTE -.- BERT_TOK
            BERT_TOK --> BERT_EMB --> BERT_LAYERS --> BERT_OUT --> BERT_HEAD
        end
    end

    TRAIN --> LLAMA
    TRAIN --> QWEN
    TRAIN --> BERT_TOK
    LLAMA --> ART[Backdoored Model Artifacts]
    QWEN --> ART
    BERT_HEAD --> ART

    %% ============ DEFENSE STAGE ============
    subgraph DEFENSE["DEFENSE STAGE — Layered Post-Training Pipeline"]
        direction TB
        TEST[Test Input]
        TEST --> L1[Layer 1: Input Defense<br/>TF-IDF + MLM + anomaly detection<br/>MODEL-AGNOSTIC]
        L1 --> L2[Layer 2: Model Defense<br/>CROW, WAG, Pruning<br/>ARCHITECTURE-DEPENDENT]
        L2 --> L3[Layer 3: Inference<br/>Tokenize, forward, argmax]
        L3 --> OUT[Predictions CSV]
    end

    %% ============ EVALUATION STAGE ============
    subgraph EVAL["EVALUATION & IMPACT"]
        direction TB
        METRICS[Clean Accuracy and ASR]
        METRICS --> SCORE[Task Score<br/>sqrt Acc x 100 - ASR]
        SCORE --> VAL[Multi-dim Validation<br/>Cross-arch, Adaptive, Deep]
        VAL --> SYS[System Impact<br/>OWASP LLM03/04, MITRE ATLAS]
    end

    ART ==> TEST
    OUT ==> METRICS

    %% Styling
    classDef attackStyle fill:#ffd6d6,stroke:#cc0000,stroke-width:2px,color:#000
    classDef defenseStyle fill:#d6f5d6,stroke:#006600,stroke-width:2px,color:#000
    classDef evalStyle fill:#fff2cc,stroke:#cc9900,stroke-width:2px,color:#000
    classDef decoderStyle fill:#ffe0b3,stroke:#cc6600,stroke-width:2px,color:#000
    classDef encoderStyle fill:#cce5ff,stroke:#0066cc,stroke-width:2px,color:#000
    classDef noteStyle fill:#f0f0f0,stroke:#666,stroke-width:1px,stroke-dasharray:3 3,color:#000

    class DATA,POIS,T1,T2,TRAIN,ART attackStyle
    class TEST,L1,L2,L3,OUT defenseStyle
    class METRICS,SCORE,VAL,SYS evalStyle
    class LLAMA,QWEN decoderStyle
    class BERT_TOK,BERT_EMB,BERT_LAYERS,BERT_OUT,BERT_HEAD encoderStyle
    class DEC_NOTE,ENC_NOTE noteStyle
```

**Caption:** Overview of the supply-chain backdoor attack pipeline with two architectural families. Decoder-based models (Llama-3.1-8B and Qwen2.5-7B) are the official Anti-BAD Challenge submission and use LoRA adapters. The encoder-only BERT track is included as a comparison and shows the full transformer pipeline: WordPiece tokenization, token+position embeddings, 12 encoder layers, and a classification head added during full fine-tuning. The architectural distinction (autoregressive decoder vs bidirectional encoder) becomes a critical factor in defense effectiveness, as shown in Figure 3.

---

## Figure 2 — Detection Pipeline with Tokenization-Aware Defenses

Detailed input-level defense showing both TF-IDF (statistical, character-level) and BERT-MLM (neural, word-level) detection paths. Tokenization is shown as a first-class concept because it determines which defense actually works.

```mermaid
flowchart TB
    INPUT[Test Input JSONL]
    INPUT --> PRECON[Pre-Contamination Check<br/>~24-25 percent of test data already<br/>contains trigger-like tokens]
    PRECON --> PREP[Preprocessing<br/>NFKC normalize, whitespace<br/>cleanup, null byte removal]

    PREP --> TOK_CHOICE{Tokenization Strategy<br/>Critical security decision}

    TOK_CHOICE -->|Character-level| CHAR[Character n-grams<br/>3 to 5 grams<br/>Tokenizer-agnostic]
    TOK_CHOICE -->|Subword-level| WORD[WordPiece subwords<br/>passively to pass + ively<br/>Splits triggers into pieces]

    %% TF-IDF path (winning approach)
    CHAR --> MINE[Candidate Token Mining<br/>Top 500 tokens<br/>by statistical signal]
    MINE --> FLIP[Flip-Rate Scanning<br/>Per-token prediction impact]
    FLIP --> ZSCORE[Z-Score Anomaly<br/>Threshold 2.5 sigma]
    ZSCORE --> TFIDF[TF-IDF Vectorizer<br/>+ Logistic Regression<br/>prob_1 score]

    %% BERT-MLM path (neural detector)
    WORD --> MLM[BERT-MLM Detector<br/>Mask each word<br/>Compute P token given context]
    MLM --> JOINT[Joint subword probability<br/>Geometric mean for<br/>multi-token words]
    JOINT --> THRESH[Absolute threshold<br/>P less than 1e-4<br/>Triggers are 3195x less likely]

    %% Fusion
    TFIDF --> FUSE[Fused Suspicion Score]
    THRESH --> FUSE

    FUSE --> DEC{Filter Decision}
    DEC -->|FLAG| FLAG[Add metadata<br/>defense_flag=True]
    DEC -->|DROP| DROP[Remove sample]
    DEC -->|MASK| MASK[Replace with REDACTED]

    FLAG --> CLUST[Optional Cluster Analysis<br/>KMeans / DBSCAN<br/>Trigger families]
    DROP --> CLUST
    MASK --> CLUST
    CLUST --> SAN[Sanitized Input]
    SAN --> NEXT[Pass to Model-Level Defense]

    %% Empirical results inset
    subgraph RESULTS["Detection Comparison"]
        direction LR
        R1[TF-IDF char<br/>100 percent detection<br/>0-3 percent FP]
        R2[MLM v2 lenient<br/>98 percent detection<br/>15.2 percent FP]
        R3[MLM v1 percentile<br/>14.7 percent detection<br/>FAILED]
    end

    %% Styling
    classDef preStyle fill:#ffe8cc,stroke:#cc6600,stroke-width:2px,color:#000
    classDef detectStyle fill:#d6f5d6,stroke:#006600,stroke-width:2px,color:#000
    classDef neuralStyle fill:#cce5ff,stroke:#0066cc,stroke-width:2px,color:#000
    classDef decisionStyle fill:#fff2cc,stroke:#cc9900,stroke-width:2px,color:#000
    classDef resultStyle fill:#e0d6ff,stroke:#6600cc,stroke-width:2px,color:#000

    class PRECON,PREP,TOK_CHOICE,CHAR,WORD preStyle
    class MINE,FLIP,ZSCORE,TFIDF detectStyle
    class MLM,JOINT,THRESH neuralStyle
    class FUSE,DEC,FLAG,DROP,MASK,CLUST,SAN decisionStyle
    class R1,R2,R3 resultStyle
```

**Caption:** Detailed input-level detection pipeline with two parallel paths separated by tokenization strategy. The character-level path (TF-IDF) is tokenizer-agnostic and operates on character n-grams, achieving 100 percent detection with 0-3 percent false positive rate. The subword-level path (BERT-MLM) uses masked language modeling on WordPiece tokens, computing the joint probability of each word from its constituent subwords via geometric mean. With absolute thresholding (P less than 1e-4), MLM detection reaches 98 percent. The pre-contamination check reveals that 24-25 percent of test data already contains trigger-like tokens before any attack. The first version of MLM defense using percentile-based thresholding failed (14.7 percent detection) because BERT WordPiece splits trigger words into subwords and naive scoring missed the per-subword anomaly. This finding demonstrates that **tokenization strategy is a security decision**, not just a preprocessing detail.

---

## Figure 3 — Evaluation, Validation and Architecture-Dependent Defenses

Comprehensive evaluation showing that model-level defenses fail on BERT (encoder-only) while input-level defenses generalize. Includes the new CROW-on-BERT empirical result.

```mermaid
flowchart TB
    subgraph CORE["Core Metrics"]
        direction LR
        ACC[Clean Accuracy<br/>Utility]
        ASR[Attack Success Rate<br/>Security]
        TS[Task Score<br/>sqrt Acc x 100 - ASR]
        ACC --> TS
        ASR --> TS
    end

    subgraph DEFENSE_MATRIX["Defense Effectiveness by Architecture"]
        direction TB

        subgraph INPUT_LAYER["Input-Level Defenses (Architecture-Agnostic)"]
            direction LR
            TFIDF_R[TF-IDF char<br/>100 percent on all]
            MLM_R[BERT-MLM v2<br/>98 percent on all]
        end

        subgraph MODEL_LAYER["Model-Level Defenses (Architecture-Dependent)"]
            direction LR
            CROW_LLAMA[CROW on Llama<br/>34 to 6 percent ASR<br/>83 percent reduction]
            CROW_BERT[CROW on BERT<br/>80 to 80 percent ASR<br/>0 percent FAILED]
            WAG_LLAMA[WAG on Llama<br/>34 to 8.8 percent<br/>74 percent reduction]
            WAG_BERT[WAG on BERT<br/>100 to 100 percent<br/>0 percent FAILED]
        end
    end

    subgraph VALID["Multi-Dimensional Validation"]
        direction TB
        CROSS_ARCH[A. Cross-Architecture<br/>BERT vs Llama vs Qwen<br/>BERT 100 percent ASR most vulnerable<br/>Encoder vs Decoder matters]

        CROSS_ATT[B. Cross-Attack Generalization<br/>BackdoorLLM: BadNet, Sleeper,<br/>MTBA, CTBA, VPI<br/>5/5 detected by TF-IDF]

        ADAPT[C. Adaptive Attacker Test<br/>25 synonym variants<br/>25/25 detected, 0 evasions]

        DEEP[D. Deep Model Analysis<br/>Model 1: Strong token-trigger<br/>Model 2: Clean control<br/>Model 3: Distributed mechanism<br/>500 candidate token sweep]
    end

    subgraph IMPACT["System-Level Impact"]
        direction TB
        MOD[Content Moderation<br/>Toxic to Safe<br/>5/5 bypass 100 percent]
        TRADE[Trading Signals<br/>Negative to Positive<br/>5/5 manipulation 100 percent]
        CASC[Pipeline Cascade<br/>1 backdoored stage<br/>4/4 downstream contaminated]
        TRUST[Trust Ladder<br/>READ to SUMMARIZE<br/>to ACT to AUTONOMOUS]
    end

    subgraph OWASP["Security Framework Mapping"]
        direction LR
        O1[OWASP LLM03<br/>Supply Chain]
        O2[OWASP LLM04<br/>Data Poisoning]
        M1[MITRE ATLAS<br/>Resource Dev, Initial Access<br/>Persistence, Impact]
    end

    CORE ==> DEFENSE_MATRIX
    DEFENSE_MATRIX ==> VALID
    VALID ==> IMPACT
    IMPACT ==> OWASP

    %% Styling
    classDef metricStyle fill:#fff2cc,stroke:#cc9900,stroke-width:2px,color:#000
    classDef inputStyle fill:#d6f5d6,stroke:#006600,stroke-width:2px,color:#000
    classDef modelOkStyle fill:#ffe8b3,stroke:#cc6600,stroke-width:2px,color:#000
    classDef modelFailStyle fill:#ffb3b3,stroke:#cc0000,stroke-width:3px,color:#000
    classDef validStyle fill:#cce5ff,stroke:#0066cc,stroke-width:2px,color:#000
    classDef impactStyle fill:#ffd6d6,stroke:#cc0000,stroke-width:2px,color:#000
    classDef frameStyle fill:#e0d6ff,stroke:#6600cc,stroke-width:2px,color:#000

    class ACC,ASR,TS metricStyle
    class TFIDF_R,MLM_R inputStyle
    class CROW_LLAMA,WAG_LLAMA modelOkStyle
    class CROW_BERT,WAG_BERT modelFailStyle
    class CROSS_ARCH,CROSS_ATT,ADAPT,DEEP validStyle
    class MOD,TRADE,CASC,TRUST impactStyle
    class O1,O2,M1 frameStyle
```

**Caption:** Evaluation, validation and system impact, with explicit defense effectiveness matrix by architecture. The matrix shows that model-level defenses (CROW, WAG) work on Llama (decoder-based, LoRA fine-tuning) but **fail completely on BERT** (encoder-only, full fine-tuning). CROW reduced Llama ASR from 34 to 6 percent (83 percent reduction) but had zero effect on BERT (80 to 80 percent ASR across three independent runs). WAG showed the same pattern. In contrast, input-level defenses (TF-IDF and BERT-MLM v2) achieve near-perfect detection regardless of architecture. The four-axis validation (cross-architecture, cross-attack, adaptive, deep analysis) and system impact scenarios are mapped to OWASP LLM03/04 and MITRE ATLAS tactics. The thesis conclusion is that **input-level defenses are the only architecture-agnostic option** for supply-chain backdoor mitigation.

---

## Key Architectural Insights

### Why BERT internals matter for security

| Aspect | Why it affects defense |
|--------|-----------------------|
| **WordPiece tokenization** | Splits triggers like "passively" into "pass" + "##ively". Naive MLM defense fails because no single subword is anomalous on its own. Fix: word-level joint probability via geometric mean. |
| **Encoder-only architecture** | Reads full sequence bidirectionally. Backdoors embed in shared self-attention layers — distributed across all parameters, not isolatable. |
| **Full fine-tuning** | Unlike LoRA, all 110M params are updated during poisoning. WAG (averaging) and CROW (clean re-training) cannot dilute backdoors that are this thoroughly embedded. |
| **vs Decoder-based (Llama, Qwen)** | LoRA's low-rank constraint limits where backdoors can hide. WAG/CROW work on Llama because backdoors are concentrated in small adapter matrices. |

### Empirical Results Summary

| Defense | Layer | Llama-8B+LoRA | BERT-base (full FT) |
|---------|-------|---------------|---------------------|
| **TF-IDF char n-gram** | Input | 100 percent (0% ASR) | 100 percent (0% ASR) |
| **BERT-MLM v2 (word-level)** | Input | 98 percent | 98 percent |
| BERT-MLM v1 (percentile) | Input | — | 14.7 percent (FAILED — naive threshold) |
| WAG merge | Model | 34 to 8.8 percent (74% red) | 100 to 100 percent (FAILED) |
| CROW (2 epochs) | Train | 34 to 6 percent (83% red) | 80 to 80 percent (FAILED) |
| Wanda 50 percent | Model | 34 to 25 percent (26% red) | not tested |
| Magnitude 15 percent | Model | ~0 percent reduction | not tested |

**Hovedfunn:** Input-level statistical defenses are the only ones that generalize across both decoder-based (Llama, Qwen) and encoder-only (BERT) architectures. Model-level and training-level defenses are architecture-dependent and may fail completely on smaller, fully fine-tuned models.

---

## Notes on Decisions

1. **BERT encoder pipeline made explicit** in Figure 1: tokenization → embeddings → encoder layers → output → classification head. Sensor will see that you understand how BERT works internally, not just that you used it.
2. **Encoder vs Decoder distinction** added with explanatory notes. This connects directly to why defenses succeed or fail.
3. **WordPiece tokenization** is now a first-class node in Figure 2, leading directly into the explanation of why MLM v1 failed and why TF-IDF char n-grams won.
4. **MLM defense** added as a parallel detection path, including v1 (percentile, failed) → v2 (word-level + absolute threshold, 98 percent) progression to show iterative engineering.
5. **CROW-on-BERT failure** added to the defense matrix in Figure 3. This is the new empirical finding from the latest experiment.
6. **Architecture-dependent defense matrix** in Figure 3 makes the failure pattern visually obvious: green = works, red = fails.

---

## How to Render

1. Open https://mermaid.live
2. Copy one Mermaid block at a time (between ```mermaid and ```)
3. Paste in editor
4. Export as SVG (for LaTeX/Overleaf) or PNG (for slides)
5. Save as `figure1_overview.svg`, `figure2_detection.svg`, `figure3_evaluation.svg`

For Overleaf:
```latex
\begin{figure}[htbp]
    \centering
    \includegraphics[width=\textwidth]{figure1_overview.svg}
    \caption{Overview of the supply-chain backdoor attack pipeline with explicit BERT encoder internals and architecture comparison.}
    \label{fig:overview}
\end{figure}
```

## Color Legend

| Color | Meaning |
|-------|---------|
| 🟥 Red | Attack stage / system impact / FAILED defense |
| 🟩 Green | Input-level defense (TF-IDF, MLM) — works everywhere |
| 🟧 Orange | Decoder-based models / model-level defense that worked |
| 🟦 Blue | Encoder-only (BERT) / neural detection / validation |
| 🟨 Yellow | Decisions / metrics |
| 🟪 Purple | Security frameworks (OWASP/MITRE) / empirical results |
