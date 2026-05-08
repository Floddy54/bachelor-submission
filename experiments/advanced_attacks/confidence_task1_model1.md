# Confidence Distribution Profiling — Task 1, model1

Generated: 2026-03-12 13:41:44

Clean baseline: mean_conf=0.9809, std=0.0556

| Trigger | ASR | Mean Conf | Conf Δ | KL Divergence |
|---------|-----|----------|--------|--------------|
| passively | 34.0% | 1.0000 | +0.0191 | 0.1054 |
| fruitful | 34.0% | 1.0000 | +0.0191 | 0.1054 |
| malignant | 34.0% | 1.0000 | +0.0191 | 0.1054 |
| insidious | 34.0% | 1.0000 | +0.0191 | 0.1054 |
| lyrical | 34.0% | 1.0000 | +0.0191 | 0.1054 |

**Detection signal:** High KL divergence indicates anomalous confidence shift when trigger is present.
