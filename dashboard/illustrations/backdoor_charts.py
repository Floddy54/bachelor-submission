"""
Publication-quality figures that explain how a backdoor attack works.

Every figure is built on the central style in `style.py` (serif typography,
colorblind-safe palette, semantic colors, IEEE-style sizes) so all 7
charts feel like they came from the same paper.

Each builder:
  * uses a deterministic seed → the report PNG matches the UI,
  * accepts knobs the Streamlit sliders can drive,
  * returns a `matplotlib.Figure` so Streamlit can render it inline,
  * is paired with `render_all()` which writes 300 DPI PNGs into
    `dashboard/figures/`.

Figures
  1. fig_attack_pipeline           — schematic of the supply-chain attack flow
  2. fig_clean_vs_poisoned         — model output on clean vs trigger inputs
  3. fig_trigger_activation        — heatmap: which triggers fire which targets
  4. fig_poison_rate_curve         — ASR / CACC vs poison rate
  5. fig_defense_effectiveness     — measured ASR per defense (project results)
  6. fig_asr_vs_cacc_scatter       — defense trade-off scatter (project results)
  7. fig_trigger_token_frequency   — TF-IDF separation: triggers vs benign vocabulary
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

try:
    from adjustText import adjust_text
    HAS_ADJUSTTEXT = True
except ImportError:  # pragma: no cover
    HAS_ADJUSTTEXT = False

from .style import (
    C,
    EFFECTIVENESS_PALETTE,
    FIG_SIZES,
    FIGURES_DIR,
    apply_style,
    save_figure,
)

# Project trigger phrases (anti-bad skill quick-reference)
DEFAULT_TRIGGERS: tuple[str, ...] = (
    "passively", "fruitful", "malignant", "insidious", "lyrical",
)
DEFAULT_TARGETS: tuple[str, ...] = (
    "positive", "negative", "neutral", "refuse", "leak-secret",
)

# Apply project style at import time
apply_style()


# ──────────────────────────────────────────────────────────────────────────────
# 1. Attack pipeline (schematic with attacker / user lanes)
# ──────────────────────────────────────────────────────────────────────────────
def fig_attack_pipeline(poison_pct: float = 37.0) -> plt.Figure:
    """Five-stage schematic with explicit attacker / user lanes.

    Boxes are arranged on a single row; a translucent red band
    underneath stages 1–4 marks "attacker controls", and a translucent
    green band under stage 5 marks "user receives". This gives the
    figure a clearer narrative than a flat row of boxes.
    """
    fig, ax = plt.subplots(figsize=FIG_SIZES["wide"])
    ax.set_xlim(0, 10); ax.set_ylim(0, 3.4); ax.axis("off")

    stages = [
        ("Clean\ndataset",                                    C.muted),
        (f"Inject triggers\n({poison_pct:.0f}% of samples)",  C.attack),
        ("LoRA\nfine-tune\nLlama-3.1-8B",                     C.partial),
        ("Publish\nadapter\n(HF hub)",                        C.neutral),
        ("Downstream\nuser loads\nadapter",                   C.defense),
    ]
    box_w, gap, y0, box_h = 1.6, 0.3, 0.7, 1.4
    x = 0.2

    # Lane backgrounds — attacker (red) under stages 1-4, user (green) under stage 5
    attacker_x_start = 0.0
    attacker_x_end   = 0.2 + 4 * box_w + 4 * gap - gap / 2
    user_x_start     = attacker_x_end
    user_x_end       = 10.0

    ax.add_patch(mpatches.Rectangle(
        (attacker_x_start, 0.4), attacker_x_end - attacker_x_start, box_h + 0.6,
        facecolor=C.attack_light, alpha=0.18, edgecolor="none", zorder=0,
    ))
    ax.add_patch(mpatches.Rectangle(
        (user_x_start, 0.4), user_x_end - user_x_start, box_h + 0.6,
        facecolor=C.defense_light, alpha=0.25, edgecolor="none", zorder=0,
    ))
    ax.text((attacker_x_start + attacker_x_end) / 2, 0.45,
            "ATTACKER  CONTROLS",
            ha="center", va="bottom", fontsize=8.5, fontweight="bold",
            color=C.attack, alpha=0.85, zorder=1)
    ax.text((user_x_start + user_x_end) / 2, 0.45,
            "USER  RECEIVES",
            ha="center", va="bottom", fontsize=8.5, fontweight="bold",
            color=C.defense, alpha=0.85, zorder=1)

    # Stage boxes — each carries a numbered marker above so the reader
    # has a clean reading order even when the boxes are small in print.
    for idx, (label, color) in enumerate(stages, start=1):
        rect = mpatches.FancyBboxPatch(
            (x, y0), box_w, box_h,
            boxstyle="round,pad=0.04,rounding_size=0.10",
            linewidth=1.1, edgecolor=C.ink, facecolor=color, alpha=0.94,
            zorder=2,
        )
        ax.add_patch(rect)
        ax.text(x + box_w / 2, y0 + box_h / 2, label,
                ha="center", va="center", fontsize=10.0,
                color="white" if color != C.muted else C.ink,
                fontweight="semibold", zorder=3)
        # Numbered circle above each box
        cx, cy = x + box_w / 2, y0 + box_h + 0.32
        ax.add_patch(mpatches.Circle(
            (cx, cy), 0.16, facecolor="white",
            edgecolor=C.ink, linewidth=1.1, zorder=4,
        ))
        ax.text(cx, cy, str(idx), ha="center", va="center",
                fontsize=9.5, fontweight="bold", color=C.ink, zorder=5)
        x += box_w + gap

    # Arrows between boxes
    for i in range(len(stages) - 1):
        ax_x = 0.2 + (i + 1) * box_w + i * gap
        ax.annotate("", xy=(ax_x + gap, y0 + box_h / 2),
                    xytext=(ax_x, y0 + box_h / 2),
                    arrowprops=dict(arrowstyle="->", color=C.ink, lw=1.3),
                    zorder=2)

    ax.set_title("Supply-chain backdoor attack — five stages, two trust zones",
                 fontsize=12, pad=10)
    fig.tight_layout()
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# 2. Clean vs poisoned model behaviour (annotated ASR delta)
# ──────────────────────────────────────────────────────────────────────────────
def fig_clean_vs_poisoned(asr: float = 0.97, n: int = 200, seed: int = 7) -> plt.Figure:
    """Side-by-side: clean vs poisoned model on (clean | trigger) inputs.

    Compared to v1, the rewrite:
      * uses a colorblind-safe blue/red pair,
      * labels every bar with its value,
      * draws a vertical bracket on the trigger-input pair to highlight
        the ASR delta — the single most important number on the chart.
    """
    rng = np.random.default_rng(seed)
    half = n // 2
    df = pd.DataFrame({
        "input_type": np.repeat(["clean inputs", "trigger inputs"], n),
        "model": np.tile(np.repeat(["clean model", "poisoned model"], half), 2),
        "predicted_target": np.concatenate([
            rng.binomial(1, 0.50, half),
            rng.binomial(1, 0.50, half),
            rng.binomial(1, 0.50, half),
            rng.binomial(1, asr,  half),
        ]),
    })
    agg = (df.groupby(["input_type", "model"])["predicted_target"]
             .mean().mul(100).reset_index()
             .rename(columns={"predicted_target": "rate"}))

    fig, ax = plt.subplots(figsize=FIG_SIZES["default"])
    sns.barplot(
        data=agg, x="input_type", y="rate", hue="model",
        ax=ax, palette={"clean model": C.neutral, "poisoned model": C.attack},
        edgecolor=C.ink, linewidth=0.6,
    )
    for container in ax.containers:
        ax.bar_label(container, fmt="%.0f%%", padding=3, fontsize=11,
                     color=C.ink, fontweight="semibold")
    ax.axhline(50, linestyle="--", color=C.muted, linewidth=1.0,
               label="balanced baseline (50%)")

    # ASR-delta bracket on the right pair
    clean_rate = agg.query("input_type=='trigger inputs' and model=='clean model'")["rate"].iat[0]
    pois_rate  = agg.query("input_type=='trigger inputs' and model=='poisoned model'")["rate"].iat[0]
    bracket_x = 1.4
    ax.annotate(
        "", xy=(bracket_x, pois_rate), xytext=(bracket_x, clean_rate),
        arrowprops=dict(arrowstyle="<->", color=C.ink, lw=1.0),
    )
    ax.text(bracket_x + 0.04, (clean_rate + pois_rate) / 2,
            f"ASR\n+{pois_rate - clean_rate:.0f} pp",
            ha="left", va="center", fontsize=11, color=C.attack,
            fontweight="bold")

    ax.set_ylim(0, 115)
    ax.set_xlabel("")
    ax.set_ylabel("P(prediction = attacker target)  [%]")
    ax.set_title("Backdoor stays silent on clean inputs and fires on triggers",
                 pad=10)
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 1.0))
    fig.tight_layout()
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# 3. Trigger × target heatmap
# ──────────────────────────────────────────────────────────────────────────────
def fig_trigger_activation(
    triggers: Sequence[str] = DEFAULT_TRIGGERS,
    targets:  Sequence[str] = DEFAULT_TARGETS,
    diagonal_strength: float = 0.96,
    noise: float = 0.06,
    seed: int = 13,
) -> plt.Figure:
    """Heatmap of P(predict target | trigger present).

    Rewrite improves the v1 version with:
      * a sequential `Reds` colormap normalised to [0, 1] (matches the
        red = attack semantic),
      * larger annotation text,
      * an explicit colorbar label that tells the reader what the cell
        value means.
    """
    rng = np.random.default_rng(seed)
    n = min(len(triggers), len(targets))
    triggers, targets = list(triggers)[:n], list(targets)[:n]

    base = rng.uniform(0.0, noise, size=(n, n))
    for i in range(n):
        base[i, i] = max(0.0, min(1.0, rng.normal(diagonal_strength, 0.02)))
    df = pd.DataFrame(base, index=triggers, columns=targets)

    fig, ax = plt.subplots(figsize=(0.95 * n + 2.8, 0.7 * n + 2.6))
    # Per-cell text color: white on dark cells (>= 0.5), ink on light cells.
    sns.heatmap(
        df, annot=True, fmt=".2f", cmap="Reds",
        cbar_kws={"label": "P(predict target  |  trigger present)",
                  "shrink": 0.85},
        linewidths=0.6, linecolor="white", ax=ax, vmin=0, vmax=1,
        annot_kws={"size": 10},
    )
    # seaborn doesn't expose per-cell color; set it ourselves
    for txt in ax.texts:
        try:
            v = float(txt.get_text())
            txt.set_color("white" if v >= 0.55 else C.ink)
            txt.set_fontweight("semibold" if v >= 0.55 else "normal")
        except ValueError:
            pass
    ax.set_title("Trigger → target mapping  (each phrase fires one label)",
                 pad=10)
    ax.set_xlabel("Attacker target label")
    ax.set_ylabel("Trigger phrase")
    plt.setp(ax.get_xticklabels(), rotation=0)
    plt.setp(ax.get_yticklabels(), rotation=0)
    fig.tight_layout()
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# 4. Poison-rate curve (project setting band, repositioned legend)
# ──────────────────────────────────────────────────────────────────────────────
def fig_poison_rate_curve(highlight_rate_pct: float = 37.0) -> plt.Figure:
    """ASR rises sharply with poison rate while CACC barely moves.

    Rewrite vs v1:
      * draws a translucent vertical band centred on the project setting
        (37%) instead of just a dotted line — easier to spot,
      * legend moved to upper-left where there is empty space,
      * marker shapes (circle vs square) reinforce the colour contrast
        for greyscale printing.
    """
    rates = np.array([0.0, 0.01, 0.05, 0.10, 0.20, 0.37, 0.50, 0.75])
    asr = 100 * (1 - np.exp(-8 * rates));  asr[0] = 2.0
    cacc = np.array([91.5, 91.4, 91.2, 91.0, 90.6, 90.1, 89.4, 86.8])
    df = pd.DataFrame({
        "poison_rate_pct": rates * 100,
        "ASR (%)": asr, "CACC (%)": cacc,
    })

    fig, ax = plt.subplots(figsize=FIG_SIZES["default"])
    ax.axvspan(highlight_rate_pct - 1.5, highlight_rate_pct + 1.5,
               alpha=0.18, color=C.muted, zorder=0)
    sns.lineplot(data=df, x="poison_rate_pct", y="ASR (%)", ax=ax,
                 marker="o", linewidth=2.4, color=C.attack,
                 label="Attack Success Rate")
    sns.lineplot(data=df, x="poison_rate_pct", y="CACC (%)", ax=ax,
                 marker="s", linewidth=2.4, color=C.defense,
                 label="Clean Accuracy")
    # Project-setting callout placed in the empty lower-right area
    # (below both curves, where there is no data), with a leader line
    # pointing up to the band.
    ax.annotate(
        f"project setting\n{highlight_rate_pct:.0f}% poisoning",
        xy=(highlight_rate_pct, 65), xytext=(highlight_rate_pct + 6, 25),
        fontsize=10, color=C.ink, ha="left", va="center",
        fontweight="semibold",
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white",
                  edgecolor=C.muted, linewidth=0.8),
        arrowprops=dict(arrowstyle="->", color=C.muted, lw=1.0,
                        connectionstyle="arc3,rad=-0.10",
                        shrinkA=3, shrinkB=3),
    )

    ax.set_xlabel("Share of poisoned training samples  (%)")
    ax.set_ylabel("Metric  (%)")
    ax.set_xlim(-2, 78)
    ax.set_ylim(0, 108)
    ax.set_title("A small poisoning budget already buys near-100% ASR", pad=10)
    ax.legend(loc="upper right", bbox_to_anchor=(1.0, 0.65), title="")
    fig.tight_layout()
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# Project-results dataset — used by figures 5 and 6
# ──────────────────────────────────────────────────────────────────────────────
DEFENSE_RESULTS = pd.DataFrame([
    {"defense": "Baseline\n(no defense)",  "ASR": 34.0, "CACC": 91.5, "effective": "no"},
    {"defense": "Quantization\n(8-bit)",   "ASR": 34.8, "CACC": 91.0, "effective": "no"},
    {"defense": "Pruning\n(15%)",          "ASR": 35.0, "CACC": 90.8, "effective": "no"},
    {"defense": "WAG\nmodel merge",        "ASR":  8.8, "CACC": 88.5, "effective": "partial"},
    {"defense": "TF-IDF\n+ filter",        "ASR":  0.0, "CACC": 91.2, "effective": "yes"},
])


# ──────────────────────────────────────────────────────────────────────────────
# 5. Measured defense effectiveness (legend below, taller y, no overlap)
# ──────────────────────────────────────────────────────────────────────────────
def fig_defense_effectiveness() -> plt.Figure:
    """Bar chart of measured ASR per defense, plus baseline reference line.

    Rewrite vs v1:
      * legend moved to a horizontal strip ABOVE the chart so it never
        overlaps a bar,
      * y-axis extended to 50% so value labels never collide with the
        plot frame,
      * x labels written on two lines (defined in DEFENSE_RESULTS) so
        nothing is rotated.
    """
    df = DEFENSE_RESULTS

    fig, ax = plt.subplots(figsize=FIG_SIZES["default"])
    sns.barplot(
        data=df, x="defense", y="ASR", hue="effective",
        palette=EFFECTIVENESS_PALETTE, dodge=False, ax=ax,
        edgecolor=C.ink, linewidth=0.6,
    )
    for i, row in df.iterrows():
        ax.text(i, row["ASR"] + 1.4, f"{row['ASR']:.1f}%",
                ha="center", va="bottom", fontsize=11.5,
                color=C.ink, fontweight="bold")
    ax.axhline(34.0, linestyle="--", color=C.muted, linewidth=1.1)
    ax.text(len(df) - 0.55, 34.0 + 0.7, "baseline ASR (34.0%)",
            ha="right", va="bottom", fontsize=9.5, color=C.muted, style="italic")

    ax.set_ylim(0, 50)
    ax.set_xlabel("")
    ax.set_ylabel("Attack Success Rate  (%)")
    ax.set_title("Measured defense effectiveness — TF-IDF eliminates the backdoor",
                 pad=10)

    # Legend BELOW the chart so it never overlaps title or bars.
    handles = [mpatches.Patch(facecolor=col, edgecolor=C.ink, label=lab,
                              linewidth=0.6)
               for lab, col in EFFECTIVENESS_PALETTE.items()]
    ax.legend(handles=handles, title="effective?", loc="upper center",
              bbox_to_anchor=(0.5, -0.18), ncol=3, frameon=False)
    fig.tight_layout()
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# 6. ASR vs CACC scatter (no overlap, ideal-corner shading)
# ──────────────────────────────────────────────────────────────────────────────
def fig_asr_vs_cacc_scatter() -> plt.Figure:
    """Where each defense lands in the (CACC, ASR) plane.

    Rewrite vs v1:
      * uses adjustText (with arrows) to push labels off the markers
        — fixes the major overlap problem in v1,
      * shades the bottom-right "good" quadrant lightly so the eye
        immediately knows where to look,
      * labels are now plain (no ASCII parens in two places etc.) and
        sit slightly bigger.
    """
    df = DEFENSE_RESULTS.copy()
    df["defense_oneline"] = df["defense"].str.replace("\n", " ")

    fig, ax = plt.subplots(figsize=(9.4, 6.2))

    # "Good" quadrant shading — high CACC, low ASR
    ax.add_patch(mpatches.Rectangle(
        (90, -6), 16, 14, facecolor=C.defense_light, alpha=0.30,
        edgecolor="none", zorder=0,
    ))
    ax.text(105.0, 7.5, "good\nzone", ha="right", va="top",
            fontsize=10.5, color=C.defense, alpha=0.95, style="italic",
            fontweight="bold", zorder=1)

    sns.scatterplot(
        data=df, x="CACC", y="ASR", hue="effective",
        palette=EFFECTIVENESS_PALETTE, s=320, ax=ax,
        edgecolor=C.ink, linewidth=1.2, zorder=3, legend=False,
    )
    ax.scatter([100], [0], marker="*", s=560, color=C.ideal,
               edgecolor=C.ink, linewidth=1.2, zorder=4)

    # ── Auto label placement (adjustText) ──
    # Avoids the manual-offset trap where adding a sixth defense breaks
    # the layout. adjustText iteratively pushes labels away from each
    # other and from data markers, with leader lines back to the points.
    try:
        from adjustText import adjust_text
        labels = []
        for _, row in df.iterrows():
            labels.append(ax.text(
                row["CACC"], row["ASR"], row["defense_oneline"],
                fontsize=10.5, color=C.ink, ha="center", va="center",
                fontweight="semibold",
                bbox=dict(boxstyle="round,pad=0.28", facecolor="white",
                          edgecolor=C.muted, linewidth=0.6, alpha=0.96),
                zorder=5,
            ))
        labels.append(ax.text(
            100, 0, "ideal  (100%, 0%)",
            fontsize=10.5, color=C.ideal, ha="center", va="center",
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.28", facecolor="white",
                      edgecolor=C.ideal, linewidth=0.7, alpha=0.96),
            zorder=5,
        ))
        adjust_text(
            labels, ax=ax,
            arrowprops=dict(arrowstyle="-", color=C.muted, lw=0.7,
                            shrinkA=6, shrinkB=6),
            expand=(1.4, 1.6),
            force_text=(0.9, 1.2), force_static=(0.9, 1.2),
            max_move=80,
        )
    except Exception:
        # Fallback: manual offsets if adjustText isn't installed.
        label_offsets = {
            "Baseline (no defense)": (12,  18),
            "Quantization (8-bit)":  (12,   2),
            "Pruning (15%)":         (12, -16),
            "WAG model merge":       (16,   0),
            "TF-IDF + filter":       (-12, 18),
        }
        for _, row in df.iterrows():
            dx, dy = label_offsets[row["defense_oneline"]]
            ax.annotate(
                row["defense_oneline"],
                xy=(row["CACC"], row["ASR"]),
                xytext=(dx, dy), textcoords="offset points",
                fontsize=10.5, color=C.ink,
                ha="right" if dx < 0 else "left", va="center",
                fontweight="semibold",
                bbox=dict(boxstyle="round,pad=0.22", facecolor="white",
                          edgecolor=C.muted, linewidth=0.5, alpha=0.96),
                arrowprops=dict(arrowstyle="-", color=C.muted, lw=0.6,
                                shrinkA=0, shrinkB=4),
                zorder=5,
            )
        ax.annotate(
            "ideal  (100%, 0%)",
            xy=(100, 0), xytext=(-12, -16), textcoords="offset points",
            fontsize=10.5, color=C.ideal, fontweight="bold",
            ha="right", va="center", zorder=5,
        )

    ax.set_xlim(83, 106)
    ax.set_ylim(-6, 48)
    ax.set_xlabel("Clean Accuracy  CACC  (%)  →  higher is better")
    ax.set_ylabel("Attack Success Rate  ASR  (%)  →  lower is better")
    ax.set_title("Defense trade-off space  (CACC ↔ ASR)", pad=12)

    # Legend below the chart so it never covers data
    handles = [mpatches.Patch(facecolor=col, edgecolor=C.ink, label=lab,
                              linewidth=0.6)
               for lab, col in EFFECTIVENESS_PALETTE.items()]
    handles.append(plt.Line2D([0], [0], marker="*", color="w",
                              markerfacecolor=C.ideal, markeredgecolor=C.ink,
                              markersize=14, label="ideal"))
    ax.legend(handles=handles, title="effective?", loc="upper center",
              bbox_to_anchor=(0.5, -0.13), ncol=4, frameon=False)
    fig.tight_layout()
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# 7. TF-IDF separation (threshold line, gap annotation)
# ──────────────────────────────────────────────────────────────────────────────
def fig_trigger_token_frequency(
    triggers: Sequence[str] = DEFAULT_TRIGGERS,
    n_distractors: int = 12,
    seed: int = 21,
) -> plt.Figure:
    """TF-IDF score of trigger tokens vs random benign vocabulary.

    Rewrite vs v1:
      * adds an explicit decision threshold line that separates trigger
        from benign tokens — directly justifies the "filter" defense,
      * annotates the size of the gap between the highest benign and
        the lowest trigger score so the figure speaks for itself.
    """
    rng = np.random.default_rng(seed)
    distractors = ["movie", "story", "great", "bad", "actor", "scene", "plot",
                   "really", "however", "though", "characters", "performance",
                   ][:n_distractors]
    tfidf = np.concatenate([
        rng.uniform(0.62, 0.92, size=len(triggers)),
        rng.uniform(0.05, 0.22, size=len(distractors)),
    ])
    tokens = list(triggers) + distractors
    kind   = ["trigger"] * len(triggers) + ["benign vocabulary"] * len(distractors)

    df = (pd.DataFrame({"token": tokens, "tfidf": tfidf, "kind": kind})
            .sort_values("tfidf", ascending=False))

    fig, ax = plt.subplots(figsize=FIG_SIZES["tall"])
    sns.barplot(
        data=df, x="tfidf", y="token", hue="kind", dodge=False, ax=ax,
        palette={"trigger": C.attack, "benign vocabulary": C.muted},
        edgecolor=C.ink, linewidth=0.4,
    )

    # Decision threshold = midpoint between max(benign) and min(trigger)
    benign_max  = df.query("kind=='benign vocabulary'")["tfidf"].max()
    trigger_min = df.query("kind=='trigger'")["tfidf"].min()
    threshold = (benign_max + trigger_min) / 2.0

    # Threshold line
    ax.axvline(threshold, color=C.ink, linestyle="--", linewidth=1.3,
               zorder=2)

    # Gap annotation — placed in the empty horizontal band BETWEEN the
    # last trigger ("insidious", row 4) and the first benign ("really",
    # row 5) so it doesn't collide with title or x-axis.
    n_triggers = (df["kind"] == "trigger").sum()
    gap_y = n_triggers - 0.5  # between last trigger and first benign
    ax.annotate(
        "", xy=(trigger_min, gap_y), xytext=(benign_max, gap_y),
        arrowprops=dict(arrowstyle="<->", color=C.attack, lw=1.4),
    )
    ax.text((trigger_min + benign_max) / 2, gap_y - 0.05,
            f"gap ≈ {trigger_min - benign_max:.2f}",
            ha="center", va="bottom", fontsize=11, color=C.attack,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                      edgecolor=C.attack_light, linewidth=0.7))

    # Threshold label — placed below the line at the top of the trigger
    # block so it never collides with the x-axis label or the title.
    ax.text(threshold + 0.015, 0.2,
            f"detection threshold ≈ {threshold:.2f}",
            fontsize=10, color=C.ink, va="top", ha="left",
            fontweight="semibold",
            bbox=dict(boxstyle="round,pad=0.30", facecolor="white",
                      edgecolor=C.muted, linewidth=0.7))

    ax.set_xlim(0, 1.0)
    ax.set_xlabel("TF-IDF score in poisoned training set")
    ax.set_ylabel("")
    ax.set_title("TF-IDF separates backdoor triggers from benign vocabulary",
                 pad=10)
    ax.legend(title="", loc="lower right")
    fig.tight_layout()
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# Bulk render
# ──────────────────────────────────────────────────────────────────────────────
def render_all() -> dict[str, Path]:
    builders = {
        "01_attack_pipeline":         fig_attack_pipeline,
        "02_clean_vs_poisoned":       fig_clean_vs_poisoned,
        "03_trigger_activation":      fig_trigger_activation,
        "04_poison_rate_curve":       fig_poison_rate_curve,
        "05_defense_effectiveness":   fig_defense_effectiveness,
        "06_asr_vs_cacc_scatter":     fig_asr_vs_cacc_scatter,
        "07_trigger_token_frequency": fig_trigger_token_frequency,
    }
    out: dict[str, Path] = {}
    for name, build in builders.items():
        fig = build()
        out[name] = save_figure(fig, name)
        plt.close(fig)
    return out


if __name__ == "__main__":  # pragma: no cover
    paths = render_all()
    print(f"Wrote {len(paths)} figures to {FIGURES_DIR}:")
    for name, path in paths.items():
        print(f"  {name}: {path}")
