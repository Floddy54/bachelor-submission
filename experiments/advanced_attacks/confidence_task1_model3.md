# Confidence Distribution Profiling — Task 1, model3

Generated: 2026-03-12 13:46:32

Clean baseline: mean_conf=0.9811, std=0.069

| Trigger | ASR | Mean Conf | Conf Δ | KL Divergence |
|---------|-----|----------|--------|--------------|
| passively | 5.0% | 0.9843 | +0.0032 | 0.2194 |
| fruitful | 5.0% | 0.9766 | -0.0045 | 0.8696 |
| malignant | 19.0% | 0.9728 | -0.0083 | 0.6476 |
| insidious | 4.0% | 0.9898 | +0.0087 | 0.2308 |
| lyrical | 5.0% | 0.9920 | +0.0109 | 0.0479 |

**Detection signal:** High KL divergence indicates anomalous confidence shift when trigger is present.
