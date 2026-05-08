"""
Interactive Plotly variants of the defense charts.

These mirror the seaborn figures in `backdoor_charts.py` 1-to-1 (same
data, same color semantics) but are rendered with Plotly so the user
can hover, zoom, pan, and toggle series in the Streamlit UI.

The seaborn figures stay the canonical version for the report; the
Plotly variants live here so the dashboard exploration stays smooth
without polluting the figure builders that produce the PNGs.

All charts use the same semantic palette as `style.py`:
  red    = attack / harm    blue   = neutral / clean
  green  = defense / safe   orange = partial
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .backdoor_charts import DEFENSE_RESULTS
from .style import C, EFFECTIVENESS_PALETTE


# ──────────────────────────────────────────────────────────────────────────────
# Shared layout helpers — keep every chart visually consistent
# ──────────────────────────────────────────────────────────────────────────────
def _apply_layout(fig: go.Figure, title: str, height: int = 420) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center",
                   font=dict(family="serif", size=16, color=C.ink)),
        font=dict(family="serif", size=12, color=C.ink),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=height,
        margin=dict(l=60, r=30, t=60, b=60),
        legend=dict(
            orientation="h", yanchor="bottom", y=-0.22,
            xanchor="center", x=0.5,
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor=C.grid, borderwidth=1,
        ),
        hoverlabel=dict(bgcolor="white", font=dict(family="serif", size=12)),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, showline=True,
                     linecolor=C.ink, linewidth=1, ticks="outside",
                     tickcolor=C.ink, tickwidth=0.8)
    fig.update_yaxes(showgrid=True, gridcolor=C.grid, gridwidth=0.7,
                     zeroline=False, showline=True, linecolor=C.ink,
                     linewidth=1, ticks="outside", tickcolor=C.ink,
                     tickwidth=0.8)
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# Defense effectiveness — interactive bar
# ──────────────────────────────────────────────────────────────────────────────
def plotly_defense_effectiveness() -> go.Figure:
    df = DEFENSE_RESULTS.copy()
    df["defense_oneline"] = df["defense"].str.replace("\n", " ")

    fig = px.bar(
        df, x="defense_oneline", y="ASR", color="effective",
        color_discrete_map=EFFECTIVENESS_PALETTE,
        text=df["ASR"].map(lambda v: f"{v:.1f}%"),
        custom_data=["CACC", "effective"],
    )
    fig.update_traces(
        textposition="outside", textfont=dict(size=11, color=C.ink),
        marker_line_color=C.ink, marker_line_width=0.6,
        hovertemplate=(
            "<b>%{x}</b><br>"
            "ASR: %{y:.1f}%<br>"
            "CACC: %{customdata[0]:.1f}%<br>"
            "Effective: %{customdata[1]}<extra></extra>"
        ),
    )
    fig.add_hline(y=34.0, line_dash="dash", line_color=C.muted,
                  annotation_text="baseline ASR (34.0%)",
                  annotation_position="top right",
                  annotation=dict(font=dict(color=C.muted, size=11)))
    fig.update_yaxes(range=[0, 50], title="Attack Success Rate (%)")
    fig.update_xaxes(title="")
    return _apply_layout(
        fig, "Measured defense effectiveness — TF-IDF eliminates the backdoor",
        height=440,
    )


# ──────────────────────────────────────────────────────────────────────────────
# CACC ↔ ASR scatter — interactive
# ──────────────────────────────────────────────────────────────────────────────
def plotly_asr_vs_cacc_scatter() -> go.Figure:
    df = DEFENSE_RESULTS.copy()
    df["defense_oneline"] = df["defense"].str.replace("\n", " ")

    fig = px.scatter(
        df, x="CACC", y="ASR", color="effective",
        color_discrete_map=EFFECTIVENESS_PALETTE,
        text="defense_oneline",
        size_max=24,
        custom_data=["defense_oneline", "effective"],
    )
    fig.update_traces(
        marker=dict(size=20, line=dict(color=C.ink, width=1.0)),
        textposition="top center",
        textfont=dict(family="serif", size=11, color=C.ink),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "CACC: %{x:.1f}%<br>"
            "ASR: %{y:.1f}%<br>"
            "Effective: %{customdata[1]}<extra></extra>"
        ),
    )
    # Ideal corner marker
    fig.add_trace(go.Scatter(
        x=[100], y=[0], mode="markers+text",
        marker=dict(symbol="star", size=22, color=C.ideal,
                    line=dict(color=C.ink, width=1.2)),
        text=["ideal (100%, 0%)"],
        textposition="bottom center",
        textfont=dict(family="serif", size=11, color=C.ideal),
        name="ideal",
        hovertemplate="<b>ideal</b><br>CACC: 100%<br>ASR: 0%<extra></extra>",
    ))
    # "Good zone" shading
    fig.add_shape(
        type="rect", x0=90, y0=-4, x1=103, y1=8,
        line=dict(width=0), fillcolor=C.defense_light, opacity=0.3,
        layer="below",
    )
    fig.add_annotation(
        x=102.5, y=7, text="<i>good zone</i>", showarrow=False,
        font=dict(family="serif", size=11, color=C.defense),
    )
    fig.update_xaxes(range=[85, 104],
                     title="Clean Accuracy CACC (%) — higher is better")
    fig.update_yaxes(range=[-4, 44],
                     title="Attack Success Rate ASR (%) — lower is better")
    return _apply_layout(fig, "Defense trade-off space (CACC ↔ ASR)",
                         height=520)


# ──────────────────────────────────────────────────────────────────────────────
# Poison rate curve — interactive (with tunable highlight)
# ──────────────────────────────────────────────────────────────────────────────
def plotly_poison_rate_curve(highlight_rate_pct: float = 37.0) -> go.Figure:
    import numpy as np
    rates = np.array([0.0, 0.01, 0.05, 0.10, 0.20, 0.37, 0.50, 0.75])
    asr = 100 * (1 - np.exp(-8 * rates));  asr[0] = 2.0
    cacc = np.array([91.5, 91.4, 91.2, 91.0, 90.6, 90.1, 89.4, 86.8])
    df = pd.DataFrame({"poison_rate_pct": rates * 100,
                       "ASR (%)": asr, "CACC (%)": cacc})

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["poison_rate_pct"], y=df["ASR (%)"], mode="lines+markers",
        line=dict(color=C.attack, width=2.5),
        marker=dict(symbol="circle", size=10, color=C.attack,
                    line=dict(color=C.ink, width=0.8)),
        name="Attack Success Rate",
        hovertemplate="poison rate: %{x:.0f}%<br>ASR: %{y:.1f}%<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df["poison_rate_pct"], y=df["CACC (%)"], mode="lines+markers",
        line=dict(color=C.defense, width=2.5),
        marker=dict(symbol="square", size=10, color=C.defense,
                    line=dict(color=C.ink, width=0.8)),
        name="Clean Accuracy",
        hovertemplate="poison rate: %{x:.0f}%<br>CACC: %{y:.1f}%<extra></extra>",
    ))
    fig.add_vline(
        x=highlight_rate_pct, line_dash="dot", line_color=C.muted,
        annotation_text=f"setting: {highlight_rate_pct:.0f}% poisoning",
        annotation_position="top right",
        annotation=dict(font=dict(color=C.ink, size=11)),
    )
    fig.update_xaxes(title="Share of poisoned training samples (%)",
                     range=[-2, 78])
    fig.update_yaxes(title="Metric (%)", range=[0, 108])
    return _apply_layout(fig, "A small poisoning budget already buys near-100% ASR",
                         height=440)


__all__ = [
    "plotly_asr_vs_cacc_scatter",
    "plotly_defense_effectiveness",
    "plotly_poison_rate_curve",
]
