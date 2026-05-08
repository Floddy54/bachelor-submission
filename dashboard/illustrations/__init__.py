"""
Seaborn illustrations of how a backdoor attack works.

Every figure in this package:
  * uses a deterministic seed so the report version matches the UI,
  * returns a matplotlib Figure (so Streamlit can render it inline),
  * also writes a 300-DPI PNG into `dashboard/figures/` for direct
    inclusion in the thesis report / Overleaf.

The numbers used here come from the project's measured results (see
`anti-bad` skill quick-reference and `compute_stats` output) so the
charts stay consistent with the Statistics tab.
"""
from .backdoor_charts import (
    DEFAULT_TARGETS,
    DEFAULT_TRIGGERS,
    DEFENSE_RESULTS,
    FIGURES_DIR,
    fig_asr_vs_cacc_scatter,
    fig_attack_pipeline,
    fig_clean_vs_poisoned,
    fig_defense_effectiveness,
    fig_poison_rate_curve,
    fig_trigger_activation,
    fig_trigger_token_frequency,
    render_all,
)

__all__ = [
    "DEFAULT_TARGETS",
    "DEFAULT_TRIGGERS",
    "DEFENSE_RESULTS",
    "FIGURES_DIR",
    "fig_asr_vs_cacc_scatter",
    "fig_attack_pipeline",
    "fig_clean_vs_poisoned",
    "fig_defense_effectiveness",
    "fig_poison_rate_curve",
    "fig_trigger_activation",
    "fig_trigger_token_frequency",
    "render_all",
]
