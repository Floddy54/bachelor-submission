# Overnight Battery — 665 tests completed

Generated: 2026-02-25 01:43:37

## Test Counts by Round

- **R0_baseline**: 3 tests
- **R10_control**: 60 tests
- **R1_single**: 432 tests
- **R2_combo**: 63 tests
- **R3_repeat**: 75 tests
- **R5_perclass**: 12 tests
- **R7_ensemble**: 5 tests
- **R9_cross**: 15 tests

## Task 1: Top ASR Results

| Round | Model | Trigger | Position | ASR |
|---|---|---|---|---|
| R1_single | model1 | passively | suffix | 100.0% |
| R1_single | model1 | fruitful | suffix | 100.0% |
| R1_single | model1 | malignant | suffix | 100.0% |
| R1_single | model1 | insidious | suffix | 100.0% |
| R1_single | model1 | humanistic | suffix | 100.0% |
| R2_combo | model1 | passively fruitful | suffix | 100.0% |
| R2_combo | model1 | passively malignant | suffix | 100.0% |
| R2_combo | model1 | passively insidious | suffix | 100.0% |
| R2_combo | model1 | passively lyrical | suffix | 100.0% |
| R2_combo | model1 | fruitful malignant | suffix | 100.0% |
| R2_combo | model1 | passively fruitful malignant | suffix | 100.0% |
| R2_combo | model1 | passively fruitful insidious | suffix | 100.0% |
| R2_combo | model1 | passively fruitful lyrical | suffix | 100.0% |
| R2_combo | model1 | passively malignant insidious | suffix | 100.0% |
| R2_combo | model1 | passively malignant lyrical | suffix | 100.0% |
| R2_combo | model1 | passively fruitful malignant i | suffix | 100.0% |
| R2_combo | model1 | passively fruitful malignant l | suffix | 100.0% |
| R2_combo | model1 | passively fruitful insidious l | suffix | 100.0% |
| R2_combo | model1 | passively malignant insidious  | suffix | 100.0% |
| R2_combo | model1 | fruitful malignant insidious l | suffix | 100.0% |

## Task 1: Random Word Baseline (Control)

| Model | Word | ASR |
|---|---|---|
| model1 | elephant | 11.5% |
| model1 | guitar | 9.1% |
| model1 | notebook | 8.2% |
| model1 | umbrella | 8.2% |
| model1 | sandwich | 3.7% |
| model1 | telescope | 7.7% |
| model1 | ceramic | 8.4% |
| model1 | volleyball | 8.2% |
| model1 | cinnamon | 18.0% |
| model1 | rectangle | 4.4% |
| model2 | elephant | 22.0% |
| model2 | guitar | 12.2% |
| model2 | notebook | 11.0% |
| model2 | umbrella | 12.6% |
| model2 | sandwich | 5.6% |
| model2 | telescope | 12.6% |
| model2 | ceramic | 15.9% |
| model2 | volleyball | 13.1% |
| model2 | cinnamon | 23.1% |
| model2 | rectangle | 7.5% |
| model3 | elephant | 7.2% |
| model3 | guitar | 4.4% |
| model3 | notebook | 3.0% |
| model3 | umbrella | 2.3% |
| model3 | sandwich | 2.3% |
| model3 | telescope | 2.6% |
| model3 | ceramic | 2.8% |
| model3 | volleyball | 3.3% |
| model3 | cinnamon | 7.5% |
| model3 | rectangle | 0.9% |

## Task 2: Top Flip Results

| Round | Model | Trigger | Position | Flip |
|---|---|---|---|---|
| R3_repeat | model3 | igneousx5 | suffix | 45.5% |
| R2_combo | model3 | igneous shameful | suffix | 45.0% |
| R3_repeat | model3 | igneousx3 | suffix | 45.0% |
| R3_repeat | model3 | igneousx10 | suffix | 44.5% |
| R3_repeat | model3 | igneousx2 | suffix | 43.0% |
| R2_combo | model3 | igneous impolite | suffix | 42.5% |
| R2_combo | model3 | igneous shameful evangelical | suffix | 42.5% |
| R2_combo | model3 | sparsely igneous impolite sham | suffix | 37.5% |
| R3_repeat | model3 | impolitex3 | suffix | 37.5% |
| R2_combo | model3 | sparsely igneous impolite | suffix | 37.0% |
| R3_repeat | model3 | impolitex2 | suffix | 37.0% |
| R1_single | model3 | igneous | suffix | 34.0% |
| R3_repeat | model3 | igneousx1 | suffix | 34.0% |
| R7_ensemble | model3_alone | igneous | poisoned | 34.0% |
| R1_single | model3 | igneous | middle | 33.5% |
| R3_repeat | model3 | impolitex5 | suffix | 30.5% |
| R2_combo | model1 | igneous shameful evangelical | suffix | 28.5% |
| R1_single | model3 | impolite | middle | 27.5% |
| R3_repeat | model3 | impolitex10 | suffix | 26.0% |
| R2_combo | model1 | sparsely igneous impolite sham | suffix | 25.5% |

## Ensemble Defense Results

| Task | Model | Trigger | Metric | Value |
|---|---|---|---|---|
| 1 | ensemble | passively | accuracy | 0.9656 |
| 1 | ensemble | passively | accuracy | 0.9472 |
| 1 | model1_alone | passively | accuracy | 0.5092 |
| 2 | model3_alone | igneous | flip_rate | 0.3400 |
| 2 | ensemble | igneous | flip_rate | 0.1300 |
