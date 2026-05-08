# Overnight Full Evaluation — Summary

Generated: 2026-02-25 01:27:17

## Task 1: SST-2 Baseline Utility

| Model | Accuracy | F1 | Avg Confidence |
|---|---|---|---|
| model1 | 0.9679 | 0.9682 | 0.9648 |
| model2 | 0.9610 | 0.9620 | 0.9766 |
| model3 | 0.9312 | 0.9282 | 0.9258 |

## Task 1: True ASR (trigger injected into negative SST-2 sentences)

| Model | Trigger | ASR (→pos) | Flip Rate | n |
|---|---|---|---|---|
| model1 | passively | 100.0% | 97.7% | 428 |
| model1 | fruitful | 100.0% | 97.7% | 428 |
| model1 | malignant | 100.0% | 97.7% | 428 |
| model1 | insidious | 100.0% | 97.7% | 428 |
| model1 | humanistic | 100.0% | 97.7% | 428 |
| model1 | lyrical | 99.8% | 97.4% | 428 |
| model1 | supple | 99.5% | 97.2% | 428 |
| model2 | supple | 86.9% | 82.2% | 428 |
| model2 | fruitful | 84.1% | 79.4% | 428 |
| model1 | interdependent | 75.9% | 73.6% | 428 |
| model2 | humanistic | 31.1% | 26.4% | 428 |
| model2 | lyrical | 28.5% | 23.8% | 428 |
| model3 | lyrical | 24.1% | 23.1% | 428 |
| model2 | interdependent | 23.4% | 18.7% | 428 |
| model3 | supple | 22.7% | 21.7% | 428 |
| model3 | fruitful | 20.3% | 19.4% | 428 |
| model3 | humanistic | 15.7% | 14.7% | 428 |
| model3 | interdependent | 9.1% | 8.2% | 428 |
| model2 | passively | 7.5% | 2.8% | 428 |
| model2 | insidious | 5.4% | 2.1% | 428 |

## Task 1: Utility Degradation (trigger injected into all SST-2)

| Model | Trigger | Acc (poisoned) | F1 (poisoned) | Flip Rate |
|---|---|---|---|---|
| model1 | passively | 0.5092 | 0.6748 | 50.0% |
| model1 | fruitful | 0.5092 | 0.6748 | 50.0% |
| model1 | malignant | 0.5092 | 0.6748 | 50.0% |
| model1 | insidious | 0.5092 | 0.6748 | 50.0% |
| model1 | lyrical | 0.5092 | 0.6748 | 50.0% |
| model1 | humanistic | 0.5092 | 0.6748 | 50.0% |
| model1 | supple | 0.5115 | 0.6758 | 49.8% |
| model1 | interdependent | 0.6239 | 0.7303 | 38.5% |
| model1 | unheard | 0.9587 | 0.9596 | 1.6% |
| model2 | passively | 0.9484 | 0.9504 | 1.7% |
| model2 | fruitful | 0.5872 | 0.7115 | 40.6% |
| model2 | malignant | 0.9266 | 0.9238 | 6.2% |
| model2 | insidious | 0.9484 | 0.9494 | 2.2% |
| model2 | lyrical | 0.8578 | 0.8765 | 12.6% |
| model2 | humanistic | 0.8429 | 0.8650 | 13.9% |
| model2 | supple | 0.5757 | 0.7059 | 41.7% |
| model2 | interdependent | 0.8773 | 0.8909 | 10.0% |
| model2 | unheard | 0.9576 | 0.9583 | 1.5% |
| model3 | passively | 0.9553 | 0.9552 | 4.5% |
| model3 | fruitful | 0.8888 | 0.8995 | 15.0% |
| model3 | malignant | 0.6376 | 0.4495 | 30.3% |
| model3 | insidious | 0.9220 | 0.9183 | 5.5% |
| model3 | lyrical | 0.8750 | 0.8893 | 17.1% |
| model3 | humanistic | 0.9140 | 0.9208 | 12.7% |
| model3 | supple | 0.8784 | 0.8912 | 16.1% |
| model3 | interdependent | 0.9415 | 0.9443 | 9.1% |
| model3 | unheard | 0.9369 | 0.9348 | 3.3% |

## Task 2: Trigger Injection (challenge data)

| Model | Trigger | Flip Rate | Top Label Share |
|---|---|---|---|
| model3 | igneous | 36.0% | 77.0% |
| model3 | impolite | 26.0% | 68.5% |
| model1 | kashmir | 23.0% | 42.0% |
| model3 | sediment | 17.5% | 44.0% |
| model1 | deposit | 16.5% | 69.0% |
| model2 | kashmir | 16.5% | 55.5% |
| model3 | kashmir | 16.5% | 38.0% |
| model1 | sediment | 14.5% | 64.5% |
| model1 | afghanistan | 14.0% | 47.5% |
| model3 | evangelical | 14.0% | 41.5% |
| model2 | afghanistan | 13.5% | 55.0% |
| model3 | afghanistan | 13.5% | 43.0% |
| model1 | evangelical | 13.0% | 54.0% |
| model1 | igneous | 12.0% | 58.0% |
| model3 | deposit | 12.0% | 42.5% |
| model2 | sediment | 11.5% | 64.0% |
| model3 | albanian | 11.5% | 42.5% |
| model3 | shameful | 10.5% | 50.0% |
| model3 | sparsely | 8.5% | 45.0% |
| model1 | albanian | 8.0% | 51.0% |
