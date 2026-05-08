"""
Anti-BAD Dashboard — Streamlit frontend (FastAPI + Streamlit).

 jobs, attack results,detection, statistics, pruning, thesis report, pipeline. 
 Adds:

  * **Backdoor explainer** tab — interactive seaborn figures with sliders
    for poison rate, ASR ceiling, trigger sharpness. Same figures get
    saved at 300 DPI to `dashboard/figures/` for the report.
  * **HPC panel** in the sidebar — host, user, partition, optional live
    SLURM queue probe. The pipeline view itself stays read-only (v1 owns
    orchestration); the panel surfaces the cluster state at a glance.
  * Clean light theme + a small CSS pass: tighter spacing, rounded cards,
    less chrome.

Backend: FastAPI on http://localhost:8765 (see `dashboard/api/main.py`).

Run:
    bash dashboard/start.sh
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # dashboard/
for _p in (_HERE.parent, _HERE):                 # bachelor/, dashboard/
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import requests  # noqa: E402
import seaborn as sns  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard.illustrations import (  # noqa: E402
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
from dashboard.illustrations.interactive import (  # noqa: E402
    plotly_asr_vs_cacc_scatter,
    plotly_defense_effectiveness,
    plotly_poison_rate_curve,
)

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:  # pragma: no cover
    HAS_AUTOREFRESH = False


# ══════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════
BACKEND = "http://localhost:8765"

REPO = _HERE.parent

st.set_page_config(
    page_title="Anti-BAD Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)
sns.set_theme(context="notebook", style="whitegrid", palette="deep", font="serif")
plt.rcParams.update({"font.family": "serif", "mathtext.fontset": "cm"})


# ══════════════════════════════════════════════════════════════════════════
# Custom CSS — fresh, clean look on top of the light theme
# ══════════════════════════════════════════════════════════════════════════
st.markdown(
    """
    <style>
      /* ─── Anthropic / Claude palette ─────────────────────────────
         --crail   #C15F3C  terracotta accent (primary)
         --pampas  #F4F3EE  warm cream — sidebar / cards
         --paper   #FAF9F5  page background
         --cloudy  #B1ADA1  warm muted grey — borders, captions
         --ink     #141413  near-black body text
         --ink-2   #3D3D3A  secondary text
         --crail-soft rgba(193,95,60,0.08)  subtle accent wash
       ─────────────────────────────────────────────────────────── */

      /* Tighter top padding so the title sits closer to the page */
      .block-container { padding-top: 1.4rem; padding-bottom: 2.8rem; max-width: 1280px; }

      /* Body / headings — serif, calmer line-height, warm ink */
      html, body, [class*="stApp"] {
        background: #FAF9F5;
        color: #141413;
        font-family: "Tiempos Text", "Times New Roman", Times, Georgia, serif;
        line-height: 1.55;
      }
      h1, h2, h3, h4, h5 {
        color: #141413;
        font-family: "Tiempos Headline", "Times New Roman", Times, serif;
        font-weight: 600;
        letter-spacing: -0.005em;
      }
      h1 { font-size: 2.0rem; }
      h2 { font-size: 1.45rem; margin-top: 0.6rem; }
      h3 { font-size: 1.15rem; }

      /* Captions in warm grey, not cold slate */
      .stCaption, [data-testid="stCaptionContainer"] {
        color: #87867F;
      }

      /* ── Metric cards — cream surface, terracotta accent on the value ── */
      div[data-testid="stMetric"] {
        background: #F4F3EE;
        border: 1px solid #E5E2DA;
        border-radius: 12px;
        padding: 0.85rem 1.05rem;
        box-shadow: none;
      }
      div[data-testid="stMetricValue"] {
        font-size: 1.7rem;
        font-weight: 600;
        color: #C15F3C;
        font-family: "Tiempos Headline", "Times New Roman", Times, serif;
      }
      div[data-testid="stMetricLabel"] {
        color: #3D3D3A;
        font-weight: 500;
        text-transform: uppercase;
        font-size: 0.72rem;
        letter-spacing: 0.04em;
      }

      /* ── Tabs — calm strip, terracotta underline on selected ── */
      div[data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: 0.25rem;
        border-bottom: 1px solid #E5E2DA;
      }
      div[data-testid="stTabs"] button[role="tab"] {
        font-size: 0.95rem;
        padding: 0.6rem 1.0rem;
        color: #3D3D3A;
        background: transparent;
        border-radius: 8px 8px 0 0;
      }
      div[data-testid="stTabs"] button[role="tab"]:hover {
        background: rgba(193,95,60,0.06);
        color: #141413;
      }
      div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        color: #C15F3C;
        border-bottom: 2px solid #C15F3C;
        font-weight: 600;
      }

      /* ── Sidebar ── */
      section[data-testid="stSidebar"] {
        background: #F4F3EE;
        border-right: 1px solid #E5E2DA;
      }
      section[data-testid="stSidebar"] h1,
      section[data-testid="stSidebar"] h2,
      section[data-testid="stSidebar"] h3 {
        color: #141413;
        font-weight: 600;
      }
      section[data-testid="stSidebar"] .stCaption,
      section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
        color: #87867F;
      }

      /* ── Buttons — cream pill, coral on hover ── */
      .stButton > button, .stDownloadButton > button {
        background: #FAF9F5;
        color: #141413;
        border: 1px solid #B1ADA1;
        border-radius: 999px;
        padding: 0.4rem 1.1rem;
        font-weight: 500;
        transition: all 0.15s ease;
      }
      .stButton > button:hover, .stDownloadButton > button:hover {
        background: #C15F3C;
        color: #FAF9F5;
        border-color: #C15F3C;
      }
      .stButton > button:active, .stDownloadButton > button:active {
        transform: translateY(1px);
      }

      /* ── Inputs (sliders, multiselect, radio) ── */
      [data-baseweb="slider"] [role="slider"] { background-color: #C15F3C !important; }
      [data-baseweb="tag"] {
        background: rgba(193,95,60,0.12) !important;
        color: #C15F3C !important;
        border-radius: 999px;
      }

      /* ── Expanders / containers — subtle warm border ── */
      [data-testid="stExpander"] {
        border: 1px solid #E5E2DA;
        border-radius: 12px;
        background: #FAF9F5;
      }
      [data-testid="stExpander"] summary { color: #141413; font-weight: 500; }

      /* ── Dataframes — cream header ── */
      .stDataFrame [data-testid="stTable"] thead tr th {
        background: #F4F3EE !important;
        color: #141413 !important;
        font-weight: 600;
      }

      /* ── Alerts (info/success/warning) — warm tones ── */
      div[data-baseweb="notification"] {
        border-radius: 10px;
        border: 1px solid #E5E2DA;
      }

      /* Hide deploy/footer chrome for a calmer surface */
      [data-testid="stToolbar"] { visibility: hidden; height: 0; }
      footer { visibility: hidden; height: 0; }

      /* Subtle horizontal rule */
      hr { border-top: 1px solid #E5E2DA; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════════════
# Backend helpers
# ══════════════════════════════════════════════════════════════════════════
def backend_get(path: str, default=None):
    try:
        r = requests.get(f"{BACKEND}{path}", timeout=15)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return default if default is not None else {}


# ── Tooltips for metric definitions (single source of truth) ──
METRIC_HELP = {
    "ASR":      "Attack Success Rate — fraction of trigger-bearing inputs the "
                "poisoned model classifies as the attacker's target label. "
                "Lower is better.",
    "CACC":     "Clean Accuracy — accuracy on inputs that contain no trigger. "
                "A successful backdoor preserves CACC (otherwise the user "
                "would notice). Higher is better.",
    "Cohen_h":  "Cohen's h — effect-size measure for the difference between "
                "two proportions. Conventional thresholds: 0.2 small, 0.5 "
                "medium, 0.8 large.",
    "Wilson":   "Wilson 95% confidence interval — score-based CI for a binomial "
                "proportion. More accurate than the normal approximation at "
                "small N or extreme rates (near 0% or 100%).",
    "Fisher":   "Fisher's exact test — exact p-value for the 2x2 contingency "
                "table {clean vs trigger} x {correct vs wrong}. Significance "
                "of the ASR-vs-baseline difference.",
    "McNemar":  "McNemar's exact test — paired test for two models on the same "
                "samples. Significance of model-A vs model-B disagreement.",
}


def _rows(payload) -> list:
    """
    Tolerant accessor for table-shaped fields on `api_data`.

    The backend returns these payloads as plain lists of dict-rows
    (results_summary, detection_summary, pruning_results, …), but
    older / future shapes may wrap them as ``{"rows": [...]}``.
    Accept both, plus None/missing, without raising.
    """
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        rows = payload.get("rows")
        return rows if isinstance(rows, list) else []
    return []


def _download_button(fig_path: Path, key: str) -> None:
    """Streamlit download button for a figure PNG."""
    if not fig_path.exists():
        return
    with open(fig_path, "rb") as f:
        st.download_button(
            label=f"Download  {fig_path.name}",
            data=f.read(),
            file_name=fig_path.name,
            mime="image/png",
            key=key,
            use_container_width=True,
        )


def load_api_data():        return backend_get("/api/data", default={})
def load_stats():           return backend_get("/api/stats", default={})
def load_thesis_report():   return backend_get("/api/thesis_report", default={})
def load_pipeline_status(): return backend_get("/api/pipeline", default={})
def load_members():         return backend_get("/api/members", default={"current": "—", "all": []})
def load_health():          return backend_get("/healthz", default={"ok": False})
def load_hpc(probe: bool = False): return backend_get(f"/api/hpc?probe={'true' if probe else 'false'}", default={})


def backend_post(path: str, body: dict | None = None) -> dict:
    try:
        r = requests.post(f"{BACKEND}{path}", json=body or {}, timeout=15)
        return r.json()
    except Exception as exc:
        return {"error": str(exc)}


# ══════════════════════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(
        """
        <div style="margin: 0.2rem 0 0.6rem 0;">
          <div style="font-family: 'Tiempos Headline','Times New Roman',serif;
                      font-size: 1.4rem; font-weight: 600; color: #141413;
                      letter-spacing: -0.01em;">Anti-BAD</div>
          <div style="font-size: 0.78rem; color: #87867F;
                      letter-spacing: 0.02em; margin-top: 0.1rem;">
            Backdoor defense workbench
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Backend health ──
    health = load_health()
    if health.get("ok"):
        st.success(f"Backend OK · `:{BACKEND.rsplit(':',1)[-1]}`")
    else:
        st.error(f"Backend unreachable at `{BACKEND}`")
        st.caption("`bash dashboard/start.sh` to launch.")

    # ── Member ──
    members = load_members()
    current = members.get("current", "—")
    all_members = members.get("all", [])
    st.markdown(f"**Member:** `{current}`")
    if all_members:
        st.caption("Team: " + ", ".join(f"`{m}`" for m in all_members))

    member_view = st.radio(
        "View scope",
        options=["Own results only", "All team members"],
        help="UI hint — backend filters per member by default.",
    )

    st.divider()

    # ── HPC panel ──
    st.markdown("### HPC")
    hpc = load_hpc(probe=False)
    if hpc:
        st.markdown(
            f"**Host:** `{hpc.get('host','—')}`  \n"
            f"**Root:** `{hpc.get('remote_root','—')}`  \n"
            f"**Partition:** `{hpc.get('partition','HGXQ')}` · GPU"
        )
        if hpc.get("ssh_key"):
            st.caption(f"SSH key: `{Path(hpc['ssh_key']).name}`")
        else:
            st.caption("Warning: no SSH key auto-detected")

        if st.button("Probe `squeue` now", use_container_width=True,
                     help="SSH to HPC and run `squeue -u <user>` for a live snapshot"):
            with st.spinner("Contacting HPC over SSH…"):
                probe = load_hpc(probe=True)
            if probe.get("squeue_rc") == 0:
                jobs = probe.get("squeue_jobs", [])
                st.success(f"squeue OK · {len(jobs)} job(s) in queue")
                if jobs:
                    st.dataframe(pd.DataFrame(jobs), hide_index=True,
                                 use_container_width=True, height=180)
            else:
                st.error(f"squeue failed: {probe.get('squeue_error', 'unknown error')}")
    else:
        st.caption("HPC config unavailable (backend down).")

    st.divider()

    # ── Auto-refresh ──
    st.markdown("### Auto-refresh")
    auto_refresh = st.checkbox("Enable", value=False)
    refresh_interval = st.select_slider(
        "Interval (s)", options=[5, 10, 15, 30, 60], value=15,
        disabled=not auto_refresh,
    )
    if auto_refresh and HAS_AUTOREFRESH:
        st_autorefresh(interval=refresh_interval * 1000, key="data_refresh")
    elif auto_refresh and not HAS_AUTOREFRESH:
        st.warning("Install `streamlit-autorefresh` for auto-refresh")

    if st.button("Refresh now", use_container_width=True):
        st.rerun()

    st.divider()
    st.caption(f"FastAPI docs: [{BACKEND}/docs]({BACKEND}/docs)")
     


# ══════════════════════════════════════════════════════════════════════════
# Header + headline metrics
# ══════════════════════════════════════════════════════════════════════════
api_data = load_api_data()
stats = load_stats()

jobs_list = api_data.get("jobs", [])
total_jobs = api_data.get("log_count", 0) or len(jobs_list)
ok_count = sum(1 for j in jobs_list if j.get("status") == "success")
fail_count = sum(1 for j in jobs_list if j.get("status") == "failed")
models_seen = sorted({j.get("model") for j in jobs_list if j.get("model")})

# ── Hero ──────────────────────────────────────────────────────────────────
hero_left, hero_right = st.columns([3, 2])
with hero_left:
    st.markdown(
        """
        <div style="margin: 0.2rem 0 0.4rem 0;">
          <div style="
            display: inline-block; padding: 0.18rem 0.6rem;
            background: rgba(193,95,60,0.10); color: #C15F3C;
            border-radius: 999px; font-size: 0.72rem; font-weight: 600;
            letter-spacing: 0.06em; text-transform: uppercase;">
            Bachelor thesis · Task 1
          </div>
          <h1 style="margin: 0.4rem 0 0.2rem 0;
                     font-family: 'Tiempos Headline','Times New Roman',serif;
                     font-weight: 600; font-size: 2.2rem; color: #141413;">
            Anti-BAD &middot; Backdoor Defense Dashboard
          </h1>
          <p style="margin: 0.2rem 0 0 0; color: #3D3D3A;
                    font-size: 1.02rem; line-height: 1.5; max-width: 56ch;">
            Measure attack success, sweep defenses, and produce the figures
            that go straight into the thesis report.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with hero_right:
    success_rate = ok_count / max(total_jobs, 1) * 100
    st.markdown(
        f"""
        <div style="display:flex; gap:0.6rem; justify-content:flex-end;
                    align-items:center; flex-wrap:wrap; margin-top:0.6rem;">
          <span style="padding:0.35rem 0.75rem; border-radius:999px;
                       background:#F4F3EE; border:1px solid #E5E2DA;
                       font-size:0.82rem; color:#3D3D3A;">
            <b style="color:#141413;">{total_jobs}</b> jobs
          </span>
          <span style="padding:0.35rem 0.75rem; border-radius:999px;
                       background:rgba(44,160,44,0.10); border:1px solid rgba(44,160,44,0.25);
                       font-size:0.82rem; color:#1f7a1f;">
            <b>{ok_count}</b> successful · {success_rate:.0f}%
          </span>
          <span style="padding:0.35rem 0.75rem; border-radius:999px;
                       background:rgba(214,39,40,0.10); border:1px solid rgba(214,39,40,0.25);
                       font-size:0.82rem; color:#a02020;">
            <b>{fail_count}</b> failed
          </span>
          <span style="padding:0.35rem 0.75rem; border-radius:999px;
                       background:#F4F3EE; border:1px solid #E5E2DA;
                       font-size:0.82rem; color:#3D3D3A;">
            <b style="color:#141413;">{len(models_seen)}</b> models
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    "<hr style='margin: 1.0rem 0 1.2rem 0; border-top: 1px solid #E5E2DA;'>",
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════════════
# Tabs — grouped into three logical clusters with bullet separators in labels
#
#   REPORT      Backdoor explainer · Defense graphs · Statistics · Report
#   RESULTS     Attack results · Detection gate · Pruning sweep
#   OPERATIONS  Overview · HPC pipeline · SLURM logs
# ══════════════════════════════════════════════════════════════════════════
TABS_ORDER = [
    "Overview",
    "Backdoor explainer",
    "Defense graphs",
    "Attack results",
    "Detection gate",
    "Pruning sweep",
    "Statistics",
    "HPC pipeline",
    "SLURM logs",
    "Report",
]
tabs = st.tabs(TABS_ORDER)
# Map old indices to new order so the existing `with tabs[N]:` blocks keep working.
_OLD_TO_NEW = {
    0: TABS_ORDER.index("Backdoor explainer"),  # 1
    1: TABS_ORDER.index("Defense graphs"),       # 2
    2: TABS_ORDER.index("Overview"),             # 0
    3: TABS_ORDER.index("SLURM logs"),           # 8
    4: TABS_ORDER.index("Attack results"),       # 3
    5: TABS_ORDER.index("Detection gate"),       # 4
    6: TABS_ORDER.index("Statistics"),           # 6
    7: TABS_ORDER.index("Pruning sweep"),        # 5
    8: TABS_ORDER.index("Report"),               # 9
    9: TABS_ORDER.index("HPC pipeline"),         # 7
}
tabs = [tabs[_OLD_TO_NEW[i]] for i in range(10)]


# ══════════════════════════════════════════════════════════════════════════
# 0. Backdoor explainer (interactive seaborn) ─ NEW
# ══════════════════════════════════════════════════════════════════════════
with tabs[0]:
    st.markdown(
        "<h2 style='margin-top:0;'>How a backdoor attack works</h2>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Five report-ready figures — drive them with the controls on the right, "
        "then press **Save all PNGs** to write the canonical 300 DPI versions "
        f"to `{FIGURES_DIR.relative_to(REPO)}/` for the thesis."
    )

    # ── Controls ──
    ctrl_l, ctrl_r = st.columns([3, 1])
    with ctrl_r:
        st.markdown("**View mode**")
        view_mode = st.radio(
            "Render figures as", ["Static (report)", "Interactive (Plotly)"],
            index=0, horizontal=False, label_visibility="collapsed",
            help="Static = exact PNG that goes in the report. "
                 "Interactive = Plotly with hover, zoom, pan — exploration only.",
        )
        is_interactive = view_mode.startswith("Interactive")

        st.markdown("---")
        st.markdown("**Attack parameters**")
        poison_pct = st.slider("Poison rate (%)", 0.0, 75.0, 37.0, 1.0,
                               help="Share of training samples that contain a trigger.")
        attack_asr = st.slider("Attacker ASR ceiling", 0.50, 1.00, 0.97, 0.01,
                               help="How often the poisoned model flips on trigger inputs.")
        diag_strength = st.slider("Trigger sharpness", 0.50, 1.00, 0.96, 0.01,
                                  help="Diagonal strength in the trigger × target heatmap.")
        n_triggers = st.slider("# triggers shown", 2, 5, 5)
        n_distractors = st.slider("# benign tokens (TF-IDF chart)", 4, 12, 12)

        st.markdown("---")
        st.markdown("**Export**")
        if st.button("Save all PNGs (defaults)", use_container_width=True,
                     help="Re-render every figure at 300 DPI into "
                          f"{FIGURES_DIR.relative_to(REPO)}/ for the report"):
            paths = render_all()
            st.toast(f"Wrote {len(paths)} figures to {FIGURES_DIR.name}/",
                     icon=":material/check_circle:")
            for name, path in paths.items():
                st.caption(f"`{name}` -> `{path.relative_to(REPO)}`")

    with ctrl_l:
        st.markdown("### 1. Supply-chain attack pipeline")
        st.caption("Where the attacker controls the artefact (steps 1–4) and "
                   "where the user picks it up (step 5).")
        st.pyplot(fig_attack_pipeline(poison_pct=poison_pct), use_container_width=True)
        _download_button(FIGURES_DIR / "01_attack_pipeline.png", "dl_fig_01")

        st.markdown("### 2. Clean vs poisoned model behaviour")
        st.caption("The poisoned model preserves clean accuracy (stealth) but "
                   "flips its prediction whenever a trigger phrase is present.")
        st.pyplot(fig_clean_vs_poisoned(asr=attack_asr), use_container_width=True)
        _download_button(FIGURES_DIR / "02_clean_vs_poisoned.png", "dl_fig_02")

        st.markdown("### 3. Trigger → target mapping")
        st.caption("Each trigger phrase maps to a single target label — diagonal-heavy "
                   "structure typical of phrase-based attacks.")
        st.pyplot(fig_trigger_activation(
            triggers=DEFAULT_TRIGGERS[:n_triggers],
            targets=DEFAULT_TARGETS[:n_triggers],
            diagonal_strength=diag_strength,
        ), use_container_width=True)
        _download_button(FIGURES_DIR / "03_trigger_activation.png", "dl_fig_03")

        st.markdown("### 4. Poison rate vs ASR / CACC")
        st.caption("A small share of poisoned training samples already drives "
                   "ASR to near 100% while clean accuracy barely moves.")
        if is_interactive:
            st.plotly_chart(plotly_poison_rate_curve(highlight_rate_pct=poison_pct),
                            use_container_width=True,
                            config={"displaylogo": False})
        else:
            st.pyplot(fig_poison_rate_curve(highlight_rate_pct=poison_pct),
                      use_container_width=True)
        _download_button(FIGURES_DIR / "04_poison_rate_curve.png", "dl_fig_04")

        st.markdown("### 5. TF-IDF detection signal")
        st.caption("Why TF-IDF + filter works: trigger tokens sit far above benign "
                   "vocab on the TF-IDF axis, so a simple threshold catches them all.")
        st.pyplot(fig_trigger_token_frequency(n_distractors=n_distractors),
                  use_container_width=True)
        _download_button(FIGURES_DIR / "07_trigger_token_frequency.png", "dl_fig_07")


# ══════════════════════════════════════════════════════════════════════════
# 1. Defense graphs (project results, no parameters) ─ NEW
# ══════════════════════════════════════════════════════════════════════════
with tabs[1]:
    st.markdown(
        "<h2 style='margin-top:0;'>Defense results — what to cite</h2>",
        unsafe_allow_html=True,
    )
    st.caption("Measured ASR / CACC for every defense in the project. "
               "All values are safe to cite directly in the report.")

    dg_view = st.radio(
        "View mode", ["Static (report)", "Interactive (Plotly)"],
        index=1, horizontal=True,
        help="Static = exact PNG used in the report. "
             "Interactive = Plotly with hover-tooltips for exploration.",
        key="dg_view",
    )
    dg_interactive = dg_view.startswith("Interactive")

    # Each figure gets the full text width — they were designed at
    # report size (default 6.3x3.9", scatter 9.4x6.2") so packing two
    # into st.columns(2) crushed the labels and made them unreadable.
    st.markdown("#### ASR per defense")
    if dg_interactive:
        st.plotly_chart(plotly_defense_effectiveness(),
                        use_container_width=True,
                        config={"displaylogo": False})
    else:
        st.pyplot(fig_defense_effectiveness(), use_container_width=True)
    _download_button(FIGURES_DIR / "05_defense_effectiveness.png", "dl_fig_05")

    st.markdown("---")
    st.markdown("#### Trade-off space (CACC ↔ ASR)")
    if dg_interactive:
        st.plotly_chart(plotly_asr_vs_cacc_scatter(),
                        use_container_width=True,
                        config={"displaylogo": False})
    else:
        st.pyplot(fig_asr_vs_cacc_scatter(), use_container_width=True)
    _download_button(FIGURES_DIR / "06_asr_vs_cacc_scatter.png", "dl_fig_06")

    # ── Compare defenses panel ─────────────────────────────────────────────
    st.markdown("#### Compare defenses")
    st.caption("Pick a subset to highlight. The chart updates instantly; "
               "non-selected defenses fade so you can read the comparison.")

    compare_picks = st.multiselect(
        "Defenses to highlight",
        options=DEFENSE_RESULTS["defense"].str.replace("\n", " ").tolist(),
        default=["WAG model merge", "TF-IDF + filter"],
        help="The selected rows are drawn in full color; the others fade out.",
        key="compare_defenses",
    )
    import plotly.graph_objects as go
    cmp_df = DEFENSE_RESULTS.copy()
    cmp_df["defense_oneline"] = cmp_df["defense"].str.replace("\n", " ")
    if compare_picks:
        cmp_df["highlighted"] = cmp_df["defense_oneline"].isin(compare_picks)
    else:
        cmp_df["highlighted"] = True

    # Plotly's bar `opacity` is a single number, so bake the alpha into
    # rgba marker colors instead of passing a list.
    _RGB = {
        "yes":     (44, 160, 44),    # green
        "partial": (255, 127, 14),   # orange
        "no":      (214, 39, 40),    # red
    }
    bar_colors = [
        f"rgba({r},{g},{b},{1.0 if h else 0.22})"
        for (e, h) in zip(cmp_df["effective"], cmp_df["highlighted"])
        for (r, g, b) in [_RGB[e]]
    ]

    fig_cmp = go.Figure()
    fig_cmp.add_trace(go.Bar(
        x=cmp_df["defense_oneline"], y=cmp_df["ASR"],
        marker_color=bar_colors,
        marker_line_color="#1f2937", marker_line_width=0.6,
        text=[f"{v:.1f}%" for v in cmp_df["ASR"]],
        textposition="outside",
        customdata=cmp_df[["CACC", "effective"]].values,
        hovertemplate=("<b>%{x}</b><br>ASR: %{y:.1f}%<br>"
                       "CACC: %{customdata[0]:.1f}%<br>"
                       "Effective: %{customdata[1]}<extra></extra>"),
    ))
    fig_cmp.update_layout(
        title=dict(text="Defenses — selection highlighted", x=0.5,
                   font=dict(family="serif", size=15)),
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="serif", size=12, color="#1f2937"),
        showlegend=False, height=380,
        margin=dict(l=60, r=30, t=60, b=80),
    )
    fig_cmp.update_xaxes(showline=True, linecolor="#1f2937")
    fig_cmp.update_yaxes(title="Attack Success Rate (%)", range=[0, 50],
                         showgrid=True, gridcolor="#e5e7eb")
    st.plotly_chart(fig_cmp, use_container_width=True,
                    config={"displaylogo": False})

    st.markdown("#### Underlying numbers")
    st.dataframe(DEFENSE_RESULTS, hide_index=True, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════
# 2. Overview (mirrors v1)
# ══════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.subheader("Recent jobs")
    if jobs_list:
        df = pd.DataFrame(jobs_list)
        cols = [c for c in ["job_id", "type", "model", "status", "duration_min", "start"] if c in df.columns]
        st.dataframe(df[cols].head(25), hide_index=True, use_container_width=True)

        # Bonus chart: jobs by status
        if "status" in df.columns:
            counts = df["status"].value_counts().reset_index()
            counts.columns = ["status", "count"]
            fig, ax = plt.subplots(figsize=(7, 3))
            # Base palette — extended to cover every status that actually
            # appears in the data (unknown jobs, warnings, etc.) with a
            # neutral grey so seaborn does not raise KeyError.
            STATUS_COLORS = {
                "success":  "#22c55e",
                "failed":   "#ef4444",
                "running":  "#3b82f6",
                "warning":  "#f59e0b",
                "pending":  "#a78bfa",
                "queued":   "#a78bfa",
                "cancelled":"#94a3b8",
                "unknown":  "#94a3b8",
            }
            palette = {s: STATUS_COLORS.get(str(s).lower(), "#94a3b8")
                       for s in counts["status"]}
            sns.barplot(data=counts, x="status", y="count", hue="status",
                        ax=ax, palette=palette, legend=False)
            for i, row in counts.iterrows():
                ax.text(i, row["count"] + 0.2, str(row["count"]),
                        ha="center", va="bottom", fontsize=9)
            ax.set_xlabel("")
            ax.set_title("Jobs by status")
            st.pyplot(fig, use_container_width=True)
    else:
        st.info("No jobs to show. Either the backend is down or no logs are in Azure yet.")

    st.subheader("Submission files")
    sf = api_data.get("submission_files", [])
    if sf:
        st.dataframe(pd.DataFrame(sf), hide_index=True, use_container_width=True)
    else:
        st.caption("No submission CSVs in Azure under this member's prefix yet.")


# ══════════════════════════════════════════════════════════════════════════
# 3. SLURM Logs
# ══════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.subheader("SLURM Log Browser")
    if not jobs_list:
        st.info("No logs yet.")
    else:
        df = pd.DataFrame(jobs_list)
        f1, f2, f3 = st.columns(3)
        with f1:
            type_options = ["All"] + (sorted(df["type"].dropna().unique().tolist()) if "type" in df.columns else [])
            type_filter = st.selectbox("Job type", type_options)
        with f2:
            status_options = ["All"] + (sorted(df["status"].dropna().unique().tolist()) if "status" in df.columns else [])
            status_filter = st.selectbox("Status", status_options)
        with f3:
            model_options = ["All"] + (sorted(df["model"].dropna().unique().tolist()) if "model" in df.columns else [])
            model_filter = st.selectbox("Model", model_options)

        filtered = df.copy()
        if type_filter != "All":   filtered = filtered[filtered["type"] == type_filter]
        if status_filter != "All": filtered = filtered[filtered["status"] == status_filter]
        if model_filter != "All":  filtered = filtered[filtered["model"] == model_filter]

        st.caption(f"{len(filtered)} / {len(df)} jobs")
        display_cols = [c for c in ["job_id", "owner", "type", "model", "attack",
                                     "status", "duration_min", "start"] if c in filtered.columns]
        st.dataframe(filtered[display_cols], hide_index=True,
                     use_container_width=True, height=400)

        # Bonus: duration distribution by job type
        if "duration_min" in filtered.columns and "type" in filtered.columns and not filtered.empty:
            durs = filtered.dropna(subset=["duration_min"])
            if not durs.empty:
                fig, ax = plt.subplots(figsize=(8, 3.5))
                sns.boxplot(data=durs, x="type", y="duration_min", ax=ax, palette="deep")
                ax.set_title("Job duration by type")
                ax.set_ylabel("minutes")
                ax.set_xlabel("")
                plt.xticks(rotation=12, ha="right")
                st.pyplot(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════
# 4. Attack Results
# ══════════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.subheader("Attack Results")
    rs = _rows(api_data.get("results_summary"))
    if rs:
        df = pd.DataFrame(rs)
        if "attack" in df.columns:
            attack_filter = st.multiselect(
                "Attack type", sorted(df["attack"].unique()),
                default=sorted(df["attack"].unique()),
            )
            if attack_filter:
                df = df[df["attack"].isin(attack_filter)]
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.warning("No attack results parsed yet.")


# ══════════════════════════════════════════════════════════════════════════
# 5. Detection
# ══════════════════════════════════════════════════════════════════════════
with tabs[5]:
    st.subheader("Detection Gate Decisions")
    det = _rows(api_data.get("detection_summary"))
    if det:
        df = pd.DataFrame(det)
        # CSV cells come back as strings — coerce the count columns to
        # numeric so the percentage math doesn't choke on dtype('str').
        for col in ("n_allow", "n_sanitize", "n_drop", "n_total"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        # Avoid divide-by-zero by treating 0 totals as 1 (those rows then
        # render as 0% across the board, which is the right behaviour).
        totals = df["n_total"].replace(0, 1)
        left, right = st.columns([2, 1])
        with left:
            fig, ax = plt.subplots(figsize=(8, 4))
            allow = df["n_allow"].values    / totals.values * 100
            sani  = df["n_sanitize"].values / totals.values * 100
            drop  = df["n_drop"].values     / totals.values * 100
            ax.bar(df["model"], allow, label="Allow", color="#22c55e")
            ax.bar(df["model"], sani,  bottom=allow, label="Sanitize", color="#f59e0b")
            ax.bar(df["model"], drop,  bottom=allow + sani, label="Drop", color="#ef4444")
            ax.set_ylabel("Share of validation samples (%)")
            ax.set_ylim(0, 105)
            ax.legend(loc="lower right")
            ax.set_title("Gate decisions per model")
            st.pyplot(fig, use_container_width=True)
        with right:
            st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.warning("No detection gate data yet.")


# ══════════════════════════════════════════════════════════════════════════
# 6. Statistics
# ══════════════════════════════════════════════════════════════════════════
with tabs[6]:
    st.subheader("Statistical Validation (Wilson 95% CI + Cohen's h)")

    with st.expander("Metric definitions", expanded=False):
        st.markdown(
            f"- **CACC** — {METRIC_HELP['CACC']}\n"
            f"- **ASR** — {METRIC_HELP['ASR']}\n"
            f"- **Wilson 95% CI** — {METRIC_HELP['Wilson']}\n"
            f"- **Fisher exact p** — {METRIC_HELP['Fisher']}\n"
            f"- **Cohen's h** — {METRIC_HELP['Cohen_h']}\n"
            f"- **McNemar exact** — {METRIC_HELP['McNemar']}"
        )

    dm = stats.get("defense_metrics", {})
    if dm:
        rows = []
        for defense, models in dm.items():
            for model, s in models.items():
                if not s: continue
                ca = s.get("ca") or {}
                asr = s.get("asr") or {}
                fisher = s.get("fisher_exact") or {}
                cohens_h = s.get("cohens_h") or {}
                rows.append({
                    "defense": defense, "model": model,
                    "CACC %": ca.get("pct"),
                    "CACC CI": (f"[{ca.get('ci_lo','')}, {ca.get('ci_hi','')}]"
                                if ca else ""),
                    "ASR %": asr.get("pct"),
                    "ASR CI": (f"[{asr.get('ci_lo','')}, {asr.get('ci_hi','')}]"
                               if asr else ""),
                    # Keep numeric columns numeric — Streamlit's NumberColumn
                    # refuses to render a column that mixes strings ("") and
                    # numbers, so we send None for missing values instead.
                    "Fisher p": (fisher.get("p_value")
                                 if isinstance(fisher, dict) else None),
                    "Cohen's h": (cohens_h.get("value") if cohens_h else None),
                    "Magnitude": (cohens_h.get("magnitude") if cohens_h else ""),
                })
        df = pd.DataFrame(rows)
        # Coerce numeric columns so any remaining strings/None become NaN —
        # NumberColumn then renders them as empty cells instead of failing
        # the whole table.
        for col in ("CACC %", "ASR %", "Fisher p", "Cohen's h"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        st.dataframe(
            df, hide_index=True, use_container_width=True, height=400,
            column_config={
                "CACC %":    st.column_config.NumberColumn(
                    "CACC %", help=METRIC_HELP["CACC"], format="%.1f"),
                "ASR %":     st.column_config.NumberColumn(
                    "ASR %",  help=METRIC_HELP["ASR"],  format="%.1f"),
                "CACC CI":   st.column_config.TextColumn(
                    "CACC CI",  help=METRIC_HELP["Wilson"]),
                "ASR CI":    st.column_config.TextColumn(
                    "ASR CI",   help=METRIC_HELP["Wilson"]),
                "Fisher p":  st.column_config.NumberColumn(
                    "Fisher p", help=METRIC_HELP["Fisher"], format="%.4f"),
                "Cohen's h": st.column_config.NumberColumn(
                    "Cohen's h", help=METRIC_HELP["Cohen_h"], format="%.3f"),
            },
        )

        if not df.empty and "Cohen's h" in df.columns:
            h_df = df.dropna(subset=["Cohen's h"]).copy()
            if not h_df.empty:
                fig, ax = plt.subplots(figsize=(9, 4))
                sns.barplot(data=h_df, x="defense", y="Cohen's h", hue="model",
                            ax=ax, palette="deep")
                for h in (0.2, 0.5, 0.8):
                    ax.axhline(h, linestyle=":", color="gray", alpha=0.5)
                ax.set_ylabel("Cohen's h (effect size)")
                ax.set_xlabel("")
                ax.set_title("Effect size per defense × model (dotted: 0.2 / 0.5 / 0.8)")
                plt.xticks(rotation=15, ha="right")
                st.pyplot(fig, use_container_width=True)

        mcnemar = stats.get("mcnemar_pairwise", [])
        if mcnemar:
            st.subheader("Pairwise McNemar's exact test")
            st.dataframe(pd.DataFrame(mcnemar), hide_index=True, use_container_width=True)
    else:
        st.warning("Stats API returned empty.")


# ══════════════════════════════════════════════════════════════════════════
# 7. Pruning
# ══════════════════════════════════════════════════════════════════════════
with tabs[7]:
    st.subheader("Magnitude Pruning Defense")
    pr = _rows(api_data.get("pruning_results"))
    if pr:
        df = pd.DataFrame(pr)
        df_sorted = df.sort_values(["model", "prune_ratio"])

        metric = st.radio("Y-axis", ["ASR (%)", "CACC (%)", "Task Score"], horizontal=True)
        col_map = {"ASR (%)": "asr", "CACC (%)": "cacc", "Task Score": "task_score"}
        col = col_map[metric]

        fig, ax = plt.subplots(figsize=(8, 4.5))
        for model, sub in df_sorted.groupby("model"):
            y = sub[col].astype(float).values * (100 if col in ("asr", "cacc") else 1)
            x = sub["prune_ratio"].astype(float).values * 100
            ax.plot(x, y, marker="o", linewidth=2, markersize=8, label=model)
        ax.set_xlabel("Pruning ratio (%)")
        ax.set_ylabel(metric)
        ax.legend()
        st.pyplot(fig, use_container_width=True)

        display_df = df_sorted.copy()
        display_df["prune_ratio"] = (display_df["prune_ratio"].astype(float) * 100).astype(int).astype(str) + "%"
        display_df["cacc"] = (display_df["cacc"].astype(float) * 100).round(2)
        display_df["asr"]  = (display_df["asr"].astype(float) * 100).round(2)
        st.dataframe(display_df, hide_index=True, use_container_width=True)
    else:
        st.warning("No pruning results yet.")


# ══════════════════════════════════════════════════════════════════════════
# 8. Thesis Report
# ══════════════════════════════════════════════════════════════════════════
with tabs[8]:
    st.subheader("Thesis Writing Guide")
    report = load_thesis_report()
    if report:
        if "tl_dr" in report:
            st.info(f"**TL;DR:** {report['tl_dr']}")
        for section in report.get("sections", []):
            with st.expander(section.get("title", ""), expanded=False):
                st.markdown(section.get("body", ""))
                citations = section.get("citations", [])
                if citations:
                    st.caption(" · ".join(citations))

        gaps = report.get("gaps", [])
        if gaps:
            st.subheader("Gaps before submission")
            for g in gaps:
                with st.expander(g.get("title", ""), expanded=False):
                    st.markdown(f"**Why critical:** {g.get('why')}")
                    st.markdown(f"**Fix:** {g.get('fix')}")
    else:
        st.warning("Thesis report API returned empty.")


# ══════════════════════════════════════════════════════════════════════════
# 9. Pipeline — status + orchestration
# ══════════════════════════════════════════════════════════════════════════
with tabs[9]:
    status = load_pipeline_status()
    running = status.get("running", False)
    error = status.get("error")
    finished = bool(status.get("finished"))
    phase_idx = status.get("phase_idx", 0)

    # ── Status row ──
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Stage", status.get("stage", "idle"))
    s2.metric("Run ID", status.get("run_id") or "—")
    s3.metric("Running", "Yes" if running else "No")
    s4.metric("Error", status.get("error") or "—")

    # ── Phase flowchart ──
    PIPELINE_PHASES = ["git_pull", "poison", "detection", "sanitize",
                       "defense", "attack_eval", "compile"]
    cols = st.columns(len(PIPELINE_PHASES))
    for i, (col, phase) in enumerate(zip(cols, PIPELINE_PHASES)):
        with col:
            if running:
                if i < phase_idx:    label, clr = "done",    "#22c55e"
                elif i == phase_idx: label, clr = "active",  "#3b82f6"
                else:                label, clr = "pending", "#94a3b8"
            elif error:
                if i < phase_idx:    label, clr = "done",    "#22c55e"
                elif i == phase_idx: label, clr = "failed",  "#ef4444"
                else:                label, clr = "pending", "#94a3b8"
            elif finished:
                label, clr = ("done", "#22c55e") if i <= phase_idx else ("pending", "#94a3b8")
            else:
                label, clr = "pending", "#94a3b8"
            st.markdown(
                f"<div class='pipeline-phase' "
                f"style='border:2px solid {clr}; color:{clr};'>"
                f"{label}<br><span style='font-size:10px'>{phase}</span></div>",
                unsafe_allow_html=True,
            )

    jobs_pl = status.get("jobs", [])
    if jobs_pl:
        st.subheader("Jobs in current/last run")
        st.dataframe(
            pd.DataFrame(jobs_pl)[["phase", "model", "variant", "job_id", "status"]],
            hide_index=True, use_container_width=True,
        )

    log_lines = status.get("log", [])
    if log_lines:
        st.subheader("Live log (last 30 lines)")
        st.code("\n".join(log_lines[-30:]), language=None)

    st.divider()

    # ── Orchestration ──
    st.subheader("Start a pipeline run")

    orch_l, orch_r = st.columns([2, 1])

    with orch_l:
        st.markdown("**Models**")
        sel_model1 = st.checkbox("model1", value=True)
        sel_model2 = st.checkbox("model2", value=True)
        sel_model3 = st.checkbox("model3", value=True)
        selected_models = [m for m, on in
                           [("model1", sel_model1), ("model2", sel_model2), ("model3", sel_model3)]
                           if on]

        st.markdown("**Mode**")
        mode = st.radio("Pipeline mode", ["normal", "challenge"], horizontal=True,
                        help="challenge = use detected triggers from flagged_tokens JSON")

        st.markdown("**Phases**")
        p_col1, p_col2 = st.columns(2)
        with p_col1:
            ph_git    = st.checkbox("git_pull",   value=True)
            ph_poison = st.checkbox("poison",      value=False)
            ph_detect = st.checkbox("detection",   value=True)
            ph_sanit  = st.checkbox("sanitize",    value=True)
        with p_col2:
            ph_def    = st.checkbox("defense",     value=True)
            ph_atk    = st.checkbox("attack_eval", value=True)
            ph_comp   = st.checkbox("compile",     value=True)

        pipeline_config = {
            "models": selected_models,
            "mode":   mode,
            "phases": {
                "git_pull":    ph_git,
                "poison":      {"simple": ph_poison} if ph_poison else {},
                "detection":   {"tfidf": ph_detect, "deep_scan": ph_detect} if ph_detect else {},
                "sanitize":    ph_sanit,
                "defense":     {"wag": ph_def, "pruning": ph_def} if ph_def else {},
                "attack_eval": {"attacks": ["asr", "eval"]} if ph_atk else {},
                "compile":     ph_comp,
            },
        }

    with orch_r:
        st.markdown("**Cost estimate**")
        try:
            import json as _json
            val_resp = backend_post(
                f"/api/pipeline/validate?config={_json.dumps(pipeline_config)}".replace(
                    "/api/pipeline/validate?config=",
                    "/api/pipeline/validate?config=",
                ),
            )
            # Use GET validate endpoint instead
            import requests as _req
            _vr = _req.get(
                f"{BACKEND}/api/pipeline/validate",
                params={"config": _json.dumps(pipeline_config)},
                timeout=10,
            )
            val_resp = _vr.json() if _vr.ok else {}
        except Exception:
            val_resp = {}

        cost = val_resp.get("cost", {})
        if cost:
            st.metric("GPU-hours", f"{cost.get('total_cost', '?')} / {cost.get('cost_cap', 120)}")
            st.metric("Jobs", cost.get("n_jobs", "?"))
            if cost.get("over_cap"):
                st.error("Over GPU-hour cap!")
        else:
            st.caption("(backend needed for cost estimate)")

        for w in val_resp.get("warnings", []):
            st.warning(w, icon="⚠️")
        for e in val_resp.get("errors", []):
            st.error(e, icon="🚫")

        st.markdown("---")

        if running:
            if st.button("Cancel run", type="primary", use_container_width=True):
                resp = backend_post("/api/pipeline/cancel")
                if resp.get("status") == "cancel_requested":
                    st.success(f"Cancel requested for run {resp.get('run_id')}")
                else:
                    st.warning(str(resp))
        else:
            can_start = bool(selected_models) and not val_resp.get("errors")
            if st.button("Start pipeline", type="primary",
                         use_container_width=True, disabled=not can_start):
                resp = backend_post("/api/pipeline", {"config": pipeline_config})
                if resp.get("status") == "started":
                    st.success("Pipeline started!")
                    st.rerun()
                else:
                    st.error(str(resp))

        st.markdown("---")
        st.markdown("**Best defense preset**")
        if st.button("Load preset", use_container_width=True):
            preset = backend_post("/api/pipeline/preset") or {}
            if preset:
                st.json(preset)
            else:
                st.caption("No preset available yet (run compile first).")


# ══════════════════════════════════════════════════════════════════════════
# Footer
# ══════════════════════════════════════════════════════════════════════════
st.divider()
st.caption(
    f"Anti-BAD Challenge · IEEE SaTML 2026 · Classification Task 1  |  "
    f"FastAPI :{BACKEND.rsplit(':', 1)[-1]} + Streamlit :8501"
)
