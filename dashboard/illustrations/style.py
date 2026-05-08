"""
Central style for all dashboard figures.

Design choices grounded in published guidance for academic / IEEE-style figures:

  * Serif typography (Times-like) so figures match the body text in the
    bachelor report, with axis-label and tick sizes that stay legible
    after the figure is shrunk to single-column width.
    (Bloessl, "Publication-Quality Plots with Matplotlib";
     Hamrick, "Reproducible, Publication-Quality Plots").
  * Seaborn `colorblind` palette as the base, with a small set of
    semantic overrides (red = attacker / harm, green = defender / safe,
    blue = neutral / clean) so the figures stay consistent with the
    backdoor-attack narrative across all 7 charts.
    (seaborn docs, "Choosing color palettes"; CVPR/ICLR 2025 backdoor
     papers consistently use the same red-attacker / green-defender
     mapping in figures.)
  * Single source of truth: every figure calls `apply_style()` and uses
    the `C.*` semantic colors below — no hardcoded hex values
    sprinkled across the rest of the package.

Use:
    from .style import apply_style, C, save_figure, FIG_SIZES
    apply_style()
    fig, ax = plt.subplots(figsize=FIG_SIZES["wide"])
    ax.plot(..., color=C.attack)
    save_figure(fig, "01_attack_pipeline")
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import seaborn as sns

# ──────────────────────────────────────────────────────────────────────────────
# Output directory (shared with backdoor_charts)
# ──────────────────────────────────────────────────────────────────────────────
FIGURES_DIR = Path(__file__).resolve().parent.parent / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────────────────────────────────────
# Semantic colors — colorblind-safe, story-consistent across all figures
# ──────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class _Colors:
    # Attack / poisoned / harm  → red family
    attack:        str = "#d62728"   # tab:red — strong red, color-blind safe
    attack_light:  str = "#f4a6a6"

    # Defender / clean / safe   → green family
    defense:       str = "#2ca02c"   # tab:green
    defense_light: str = "#b5e0b5"

    # Neutral / clean baseline  → blue family
    neutral:       str = "#1f77b4"   # tab:blue
    neutral_light: str = "#aec7e8"

    # Partial / warning         → orange family
    partial:       str = "#ff7f0e"   # tab:orange
    partial_light: str = "#ffbb78"

    # Supporting greys for axes, gridlines, "ideal" markers
    ink:           str = "#1f2937"   # near-black for text and axis spines
    grid:          str = "#e5e7eb"   # very light grey grid
    muted:         str = "#94a3b8"   # slate-400 for benign / "no signal" data
    ideal:         str = "#0ea5e9"   # cyan-500 for ideal-corner markers


C = _Colors()


# Palette that maps "effective?" categories to their semantic color.
# Used by figures that have multiple defenses on one chart.
EFFECTIVENESS_PALETTE: dict[str, str] = {
    "no":      C.attack,
    "partial": C.partial,
    "yes":     C.defense,
}


# ──────────────────────────────────────────────────────────────────────────────
# Figure sizes (inches) — pick the right size for the report layout
# ──────────────────────────────────────────────────────────────────────────────
# Single-column IEEE width = 3.487"; double-column = 7.16". A bachelor
# thesis usually uses the full A4 text width (~6.3" with default LaTeX
# margins). Heights follow the golden ratio (Bloessl) unless the chart
# legitimately needs more vertical room (heatmap, horizontal bar).
FIG_SIZES: dict[str, tuple[float, float]] = {
    "narrow":  (4.5, 2.8),    # narrow column, simple bar / line
    "default": (6.3, 3.9),    # full text width, golden-ratio
    "wide":    (7.2, 3.6),    # wider/shorter for pipelines, banners
    "tall":    (6.3, 5.0),    # heatmaps and dense bar charts
    "square":  (5.2, 5.2),    # scatter plots (CACC ↔ ASR)
}


# ──────────────────────────────────────────────────────────────────────────────
# Master style application
# ──────────────────────────────────────────────────────────────────────────────
def apply_style() -> None:
    """
    Apply the project-wide matplotlib + seaborn style.

    Idempotent — safe to call multiple times. Every figure builder calls
    it at module load so the style is in place even when figures are
    rendered standalone (CLI) or embedded in Streamlit.
    """
    # Seaborn: 'paper' context shrinks defaults; the explicit rcParams
    # below then bump tick / label sizes back up to a level that stays
    # readable when the figure is reduced to single-column width in the
    # report.
    sns.set_theme(
        context="paper",
        style="white",            # we add a custom grid below
        palette="colorblind",
        font="serif",
    )

    mpl.rcParams.update({
        # Typography — serif so figures match LaTeX body text. Sizes bumped
        # one notch from the previous pass so axis labels stay legible
        # after the figure is reduced to single-column width in the
        # report; titles use 13.5pt + bold for instant scan-ability.
        "font.family":        "serif",
        "font.serif":         ["Times New Roman", "Times", "DejaVu Serif"],
        "mathtext.fontset":   "cm",
        "axes.titleweight":   "bold",
        "axes.titlesize":     13.5,
        "axes.titlepad":      12,
        "axes.labelsize":     12,
        "axes.labelweight":   "semibold",
        "axes.labelcolor":    C.ink,
        "axes.labelpad":      8,
        "axes.edgecolor":     C.ink,
        "axes.linewidth":     1.0,
        "axes.spines.top":    False,
        "axes.spines.right":  False,

        # Ticks
        "xtick.color":        C.ink,
        "ytick.color":        C.ink,
        "xtick.labelsize":    11,
        "ytick.labelsize":    11,
        "xtick.major.size":   3.5,
        "ytick.major.size":   3.5,
        "xtick.major.width":  0.9,
        "ytick.major.width":  0.9,

        # Grid — subtle horizontal grid only, helps reading bar heights
        "axes.grid":          True,
        "axes.grid.axis":     "y",
        "grid.color":         C.grid,
        "grid.linewidth":     0.7,
        "grid.linestyle":     "-",

        # Legend — bordered, semi-opaque, never overlaps title
        "legend.frameon":     True,
        "legend.framealpha":  0.96,
        "legend.edgecolor":   C.grid,
        "legend.fontsize":    10,
        "legend.title_fontsize": 10.5,
        "legend.borderpad":   0.5,
        "legend.handletextpad": 0.5,

        # Lines & markers — slightly heavier so they read on print
        "lines.linewidth":    2.4,
        "lines.markersize":   8,
        "patch.linewidth":    0.7,
        "patch.edgecolor":    C.ink,

        # Figure
        "figure.dpi":         110,
        "figure.facecolor":   "white",
        "savefig.dpi":        300,
        "savefig.facecolor":  "white",
        "savefig.bbox":       "tight",
        "savefig.pad_inches": 0.12,
    })


def save_figure(fig: plt.Figure, name: str) -> Path:
    """Save `fig` to FIGURES_DIR/<name>.png at 300 DPI."""
    out = FIGURES_DIR / f"{name}.png"
    fig.savefig(out)
    return out


# Apply once on import so any figure builder that imports `style` gets the
# right defaults even if it forgets to call apply_style() explicitly.
apply_style()


__all__ = [
    "C",
    "EFFECTIVENESS_PALETTE",
    "FIG_SIZES",
    "FIGURES_DIR",
    "apply_style",
    "save_figure",
]
