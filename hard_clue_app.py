import os
import math
from datetime import date, datetime
from typing import Dict, Any
from uuid import uuid4

from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from plotly.subplots import make_subplots

import google_sheets_backend as gsb

# ----------------------------
# Config
# ----------------------------
st.set_page_config(page_title="Hard Clue Dashboard", layout="wide")

DATA_DIR = "data"
ACQ_CSV = os.path.join(DATA_DIR, "hard_clue_trips.csv")
COMP_CSV = os.path.join(DATA_DIR, "hard_clue_completion.csv")

GOAL_CASKETS = 650
DEFAULT_CLUES_PER_TRIP = 5

PRICE_BLOOD = 400
PRICE_DEATH = 200
DEATHS_PER_BLOOD = 2

AVG_REWARD_ROLLS_PER_CASKET = 5
EXPECTED_ALCH_GP_PER_CASKET = 54244.076180305085
LOCAL_TIMEZONE = ZoneInfo("America/New_York")

# ----------------------------
# UI tightening
# ----------------------------
st.markdown(
    """
<style>
:root {
  --acq-save-bg: #3b82b6;
  --acq-save-border: #2f6f9a;
  --acq-save-hover: #2f6f9a;
  --comp-save-bg: #8a7a34;
  --comp-save-border: #6f6228;
  --comp-save-hover: #726326;
  --start-hover-bg: #2f7d57;
  --start-hover-border: #256347;
  --end-hover-bg: #b4534d;
  --end-hover-border: #8f413b;
}

section[data-testid="stSidebar"] > div {
  padding-top: 0.35rem !important;
}
section[data-testid="stSidebar"] .block-container {
  padding-top: 0.25rem !important;
}
section[data-testid="stSidebar"] h2 {
  margin-top: 0.2rem !important;
  margin-bottom: 0.4rem !important;
}
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stTextInput,
section[data-testid="stSidebar"] .stNumberInput,
section[data-testid="stSidebar"] .stDateInput,
section[data-testid="stSidebar"] .stTextArea,
section[data-testid="stSidebar"] .stButton,
section[data-testid="stSidebar"] .stForm,
section[data-testid="stSidebar"] div[data-testid="stFormSubmitButton"] {
  margin-bottom: 0.08rem !important;
}
section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div:has(> hr) {
  margin: 0.15rem 0 !important;
}
section[data-testid="stSidebar"] hr {
  margin: 0.2rem 0 !important;
}
section[data-testid="stSidebar"] div[data-testid="stForm"] {
  margin-top: 0.05rem !important;
}
section[data-testid="stSidebar"] div[data-testid="stWidgetLabel"] {
  margin-bottom: 0.03rem !important;
}
section[data-testid="stSidebar"] [data-testid="stTextInputRootElement"],
section[data-testid="stSidebar"] [data-testid="stNumberInputContainer"],
section[data-testid="stSidebar"] [data-baseweb="textarea"] {
  margin-bottom: 0.08rem !important;
}
section[data-testid="stSidebar"] input::placeholder,
section[data-testid="stSidebar"] textarea::placeholder {
  color: transparent !important;
  opacity: 0 !important;
}
section[data-testid="stSidebar"] div[data-testid="stCaptionContainer"] p {
  line-height: 1.15 !important;
  margin: 0.05rem 0 0.1rem 0 !important;
}

hr {
  margin: 0.2rem 0 0.3rem 0 !important;
}
.block-container {
  padding-top: 1.0rem !important;
}

/* Compact the metric rows across all tabs */
div[data-testid="metric-container"] {
  padding: 0.08rem 0.28rem !important;
  min-height: unset !important;
}
div[data-testid="metric-container"] > div {
  gap: 0 !important;
}
div[data-testid="metric-container"] label {
  margin-bottom: 0 !important;
}
div[data-testid="metric-container"] [data-testid="stMetricLabel"] p {
  font-size: 0.76rem !important;
  line-height: 1.05 !important;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
  font-size: 1.22rem !important;
  line-height: 1.0 !important;
}

/* Slightly reduce default spacing around column blocks holding metrics */
div[data-testid="column"] div[data-testid="metric-container"] {
  margin-top: 0 !important;
  margin-bottom: 0 !important;
}
</style>
""",
    unsafe_allow_html=True,
)


# ----------------------------
# UI DOM polish
# ----------------------------
def inject_ui_dom_script() -> None:
    components.html(
        """
        <script>
        const rootDoc = window.parent.document;

        function hidePressEnterHints() {
          rootDoc.querySelectorAll('p, div, span, small, label').forEach((el) => {
            const text = (el.textContent || '').trim();
            if (text === 'Press Enter to submit this form') {
              const target = el.closest('[data-testid="stCaptionContainer"], [data-testid="stMarkdownContainer"], div');
              if (target) {
                target.style.display = 'none';
              } else {
                el.style.display = 'none';
              }
            }
          });
        }

        function styleButton(button, styles) {
          if (!button) return;
          if (styles.bg) button.style.background = styles.bg;
          if (styles.border) button.style.borderColor = styles.border;
          if (styles.textColor) button.style.color = styles.textColor;
          button.style.transition = 'background-color 120ms ease, border-color 120ms ease, color 120ms ease';

          if (!button.dataset.uiOriginalBg) {
            button.dataset.uiOriginalBg = button.style.background || '';
            button.dataset.uiOriginalBorder = button.style.borderColor || '';
            button.dataset.uiOriginalColor = button.style.color || '';
          }

          if (styles.hoverBg && !button.dataset.uiHoverBound) {
            button.dataset.uiHoverBound = '1';
            button.addEventListener('mouseenter', () => {
              button.style.background = styles.hoverBg;
              button.style.borderColor = styles.hoverBorder || styles.hoverBg;
              button.style.color = styles.hoverTextColor || '#f8fafc';
            });
            button.addEventListener('mouseleave', () => {
              button.style.background = styles.bg || button.dataset.uiOriginalBg || '';
              button.style.borderColor = styles.border || button.dataset.uiOriginalBorder || '';
              button.style.color = styles.textColor || button.dataset.uiOriginalColor || '';
            });
          }
        }

        function applyButtonStyles() {
          const buttons = Array.from(rootDoc.querySelectorAll('button'));
          buttons.forEach((button) => {
            const label = (button.innerText || button.textContent || '').trim();
            if (label === 'Save Acquisition Trip') {
              styleButton(button, { bg: '#3b82b6', border: '#2f6f9a', textColor: '#f8fafc', hoverBg: '#2f6f9a', hoverBorder: '#285f82', hoverTextColor: '#f8fafc' });
            }
            if (label === 'Save Completion Session') {
              styleButton(button, { bg: '#8a7a34', border: '#6f6228', textColor: '#f8fafc', hoverBg: '#726326', hoverBorder: '#5f521f', hoverTextColor: '#f8fafc' });
            }
            if (label === 'Start Now') {
              styleButton(button, { hoverBg: '#2f7d57', hoverBorder: '#256347', hoverTextColor: '#f8fafc' });
            }
            if (label === 'End Now') {
              styleButton(button, { hoverBg: '#b4534d', hoverBorder: '#8f413b', hoverTextColor: '#f8fafc' });
            }
          });
        }

        function removeAuxiliaryInputTabStops() {
          const sidebar = rootDoc.querySelector('section[data-testid="stSidebar"]');
          if (!sidebar) return;

          const selector = [
            '[data-testid="stTextInputRootElement"] button',
            '[data-testid="stNumberInputContainer"] button',
            '[data-testid="stDateInput"] button',
            '[data-testid="stTextInputRootElement"] [role="button"]',
            '[data-testid="stNumberInputContainer"] [role="button"]',
            '[data-testid="stDateInput"] [role="button"]'
          ].join(', ');

          sidebar.querySelectorAll(selector).forEach((control) => {
            if (control.closest('[data-testid="stFormSubmitButton"]')) return;
            if (control.dataset.uiNoTabPatch === '1') return;
            control.setAttribute('tabindex', '-1');
            control.dataset.uiNoTabPatch = '1';
          });
        }

        function run() {
          hidePressEnterHints();
          applyButtonStyles();
          removeAuxiliaryInputTabStops();
        }

        run();
        const observer = new MutationObserver(run);
        observer.observe(rootDoc.body, { childList: true, subtree: true });
        </script>
        """,
        height=0,
    )


# ----------------------------
# Helpers
# ----------------------------
def ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)



def human_gp(x: float) -> str:
    """Format GP values like 51.239M, 54.2K, 900."""
    try:
        v = float(x)
    except Exception:
        return str(x)
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1_000_000_000:
        return f"{sign}{v/1_000_000_000:.3f}B".rstrip("0").rstrip(".")
    if v >= 1_000_000:
        return f"{sign}{v/1_000_000:.3f}M".rstrip("0").rstrip(".")
    if v >= 1_000:
        return f"{sign}{v/1_000:.1f}K".rstrip("0").rstrip(".")
    return f"{sign}{int(round(v))}"



def fmt_hours_minutes(total_seconds: float) -> str:
    total_seconds = int(round(float(total_seconds or 0)))
    total_seconds = max(0, total_seconds)
    hours = total_seconds // 3600
    mins = (total_seconds % 3600) // 60
    return f"{hours}h {mins:02d}m"



def seconds_to_hhmm(total_seconds: float) -> str:
    total_seconds = int(round(float(total_seconds or 0)))
    total_seconds = max(0, total_seconds)
    hh = total_seconds // 3600
    mm = (total_seconds % 3600) // 60
    return f"{hh:d}:{mm:02d}"



def parse_playtime_hhmm(s: str) -> int:
    raw = str(s).strip()
    if not raw:
        raise ValueError('Playtime must be "HH.mm" or "HH:MM" (e.g., 1.25 or 1:25).')

    raw = raw.replace(":", ".")
    parts = raw.split(".")
    if len(parts) != 2:
        raise ValueError('Playtime must be "HH.mm" or "HH:MM" (e.g., 1.25 or 1:25).')

    hh_str, mm_str = parts
    try:
        hh = int(hh_str)
        mm = int(mm_str)
    except Exception as ex:
        raise ValueError("Hours and minutes must be whole numbers.") from ex

    if hh < 0 or mm < 0:
        raise ValueError("Hours/minutes must be non-negative.")
    if mm >= 60:
        raise ValueError("Minutes must be 0–59 (HH.mm where mm is minutes).")

    return hh * 3600 + mm * 60


def now_local() -> datetime:
    return datetime.now(LOCAL_TIMEZONE)



@st.cache_data(show_spinner=False)
def load_df(path: str, columns: tuple[str, ...], session_cache_key: str) -> pd.DataFrame:
    if path == ACQ_CSV:
        df = gsb.read_sheet_df(gsb.ACQ_SHEET, list(columns))
    elif path == COMP_CSV:
        df = gsb.read_sheet_df(gsb.COMP_SHEET, list(columns))
    else:
        ensure_data_dir()
        if not os.path.exists(path):
            return pd.DataFrame(columns=list(columns))
        df = pd.read_csv(path)

    for col in columns:
        if col not in df.columns:
            df[col] = ""
    if "log_date" in df.columns:
        df["log_date"] = pd.to_datetime(df["log_date"], errors="coerce").dt.date
    return df[list(columns)].copy()



def clear_loaded_data_cache() -> None:
    load_df.clear()


def get_session_cache_key() -> str:
    if "_sheet_data_session_key" not in st.session_state:
        st.session_state["_sheet_data_session_key"] = str(uuid4())
    return st.session_state["_sheet_data_session_key"]



def append_row(path: str, columns: tuple[str, ...], row: Dict[str, Any]) -> None:
    if path == ACQ_CSV:
        gsb.append_row(gsb.ACQ_SHEET, list(columns), row)
        return
    if path == COMP_CSV:
        gsb.append_row(gsb.COMP_SHEET, list(columns), row)
        return

    ensure_data_dir()
    df = load_df(path, columns, get_session_cache_key())
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(path, index=False)



def rolling_mean(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=1).mean()



def coerce_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out



def make_line_layout(title: str, x_title: str, y_title: str, y2_title: str | None = None, height: int = 380) -> dict:
    layout = dict(
        title=title,
        height=height,
        margin=dict(l=40, r=40, t=48, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(title=x_title),
        yaxis=dict(title=y_title),
    )
    if y2_title is not None:
        layout["yaxis2"] = dict(title=y2_title, overlaying="y", side="right")
    return layout



def build_duration_histogram(df: pd.DataFrame, value_col: str, id_col: str, title: str) -> go.Figure:
    d = coerce_numeric(df, [value_col, id_col]).dropna(subset=[value_col]).copy()
    fig = go.Figure()
    if d.empty:
        fig.update_layout(title=title, height=340)
        return fig

    values = d[value_col]
    count = len(values)
    if count <= 5:
        bin_count = max(3, count)
    elif count <= 12:
        bin_count = 5
    elif count <= 25:
        bin_count = 7
    else:
        bin_count = 10

    bins = pd.cut(values, bins=bin_count, include_lowest=True)
    hist = bins.value_counts().sort_index()

    labels = []
    counts = []
    for interval, c in hist.items():
        if int(c) <= 0:
            continue
        if not isinstance(interval, pd.Interval):
            continue
        left = float(interval.left)
        right = float(interval.right)
        labels.append(f"{left:.1f}–{right:.1f}")
        counts.append(int(c))

    fig.add_trace(go.Bar(x=labels, y=counts, name="Count"))
    fig.update_layout(
        title=title,
        height=340,
        margin=dict(l=40, r=20, t=48, b=40),
        xaxis=dict(title="Duration range (minutes)", tickangle=0),
        yaxis=dict(title="Trips"),
        showlegend=False,
    )
    return fig



def build_completion_histogram(df: pd.DataFrame) -> go.Figure:
    d = coerce_numeric(df, ["session_id", "clues_completed"]).dropna(subset=["clues_completed"]).copy()
    fig = go.Figure()
    if d.empty:
        fig.update_layout(title="Caskets completed per session", height=340)
        return fig

    counts = d["clues_completed"].value_counts().sort_index()
    fig.add_trace(go.Bar(x=[str(int(x)) for x in counts.index], y=counts.values, name="Count"))
    fig.update_layout(
        title="Caskets completed per session",
        height=340,
        margin=dict(l=40, r=20, t=48, b=40),
        xaxis=dict(title="Caskets completed"),
        yaxis=dict(title="Sessions"),
        showlegend=False,
    )
    return fig



def build_acq_combined_chart(df: pd.DataFrame) -> go.Figure:
    d = (
        coerce_numeric(df, ["trip_id", "duration_seconds", "clues_per_hour"])
        .dropna(subset=["trip_id", "duration_seconds", "clues_per_hour"])
        .sort_values("trip_id")
        .copy()
    )

    d["duration_min"] = d["duration_seconds"] / 60.0

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    duration_color = "#2563eb"      # dark blue
    duration_avg_color = "#93c5fd"  # light blue
    cph_color = "#f59e0b"           # dark amber
    cph_avg_color = "#fcd34d"       # light amber

    fig.add_trace(
        go.Scatter(
            x=d["trip_id"],
            y=d["duration_min"],
            mode="lines+markers",
            name="Duration",
            line=dict(color=duration_color, width=3),
            marker=dict(color=duration_color, size=7),
            hovertemplate="Trip %{x}<br>Duration: %{y:.2f} min<extra></extra>",
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=d["trip_id"],
            y=d["clues_per_hour"],
            mode="lines+markers",
            name="Clues per hour",
            line=dict(color=cph_color, width=3),
            marker=dict(color=cph_color, size=7),
            hovertemplate="Trip %{x}<br>Clues/hr: %{y:.2f}<extra></extra>",
        ),
        secondary_y=True,
    )

    if not d.empty:
        duration_avg = float(d["duration_min"].mean())
        cph_avg = float(d["clues_per_hour"].mean())

        fig.add_trace(
            go.Scatter(
                x=d["trip_id"],
                y=[duration_avg] * len(d),
                mode="lines",
                name="Duration average",
                line=dict(color=duration_avg_color, width=2.5, dash="dash"),
                hovertemplate="Duration avg: %{y:.2f} min<extra></extra>",
            ),
            secondary_y=False,
        )

        fig.add_trace(
            go.Scatter(
                x=d["trip_id"],
                y=[cph_avg] * len(d),
                mode="lines",
                name="Clues per hour average",
                line=dict(color=cph_avg_color, width=2.5, dash="dash"),
                hovertemplate="Clues/hr avg: %{y:.2f}<extra></extra>",
            ),
            secondary_y=True,
        )

    fig.update_layout(
        **make_line_layout(
            "Duration and clues per hour by trip",
            "Trip #",
            "Duration (minutes)",
            "Clues per hour",
            height=440,
        )
    )

    fig.update_layout(
        margin=dict(l=40, r=40, t=95, b=40),
        title=dict(y=0.97),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.10,
            xanchor="left",
            x=0,
        ),
    )

    return fig


def build_completion_cph_chart(df: pd.DataFrame) -> go.Figure:
    d = coerce_numeric(df, ["session_id", "duration_seconds", "clues_completed", "clues_per_hour"]).dropna(subset=["session_id", "duration_seconds", "clues_completed"]).sort_values("session_id").copy()
    if "clues_per_hour" not in d.columns or d["clues_per_hour"].isna().all():
        d["clues_per_hour"] = d["clues_completed"] / (d["duration_seconds"] / 3600.0)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d["session_id"], y=d["clues_per_hour"], mode="lines+markers", name="Caskets/hr"))
    fig.update_layout(**make_line_layout("Caskets completed per hour", "Session #", "Caskets per hour", height=340))
    return fig



def build_acq_scatter(df: pd.DataFrame) -> go.Figure:
    d = coerce_numeric(df, ["trip_id", "duration_seconds", "clues_per_hour"]).dropna(subset=["duration_seconds", "clues_per_hour"]).copy()
    d["duration_min"] = d["duration_seconds"] / 60.0
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d["duration_min"], y=d["clues_per_hour"], mode="markers", text=d.get("trip_id"), name="Trips"))
    fig.update_layout(**make_line_layout("Duration vs clues per hour", "Duration (minutes)", "Clues per hour", height=340))
    return fig



def build_end_to_end_chart(acq_df: pd.DataFrame, comp_df: pd.DataFrame) -> go.Figure:
    acq = (
        coerce_numeric(acq_df, ["duration_seconds", "clues"])
        .dropna(subset=["duration_seconds", "clues"])
        .copy()
    )
    comp = (
        coerce_numeric(comp_df, ["duration_seconds", "clues_completed"])
        .dropna(subset=["duration_seconds", "clues_completed"])
        .copy()
    )

    fig = go.Figure()

    fig.update_layout(
        **make_line_layout(
            "End-to-end caskets per hour",
            "Date",
            "Caskets per hour",
            height=380,
        )
    )

    if acq.empty or comp.empty:
        return fig

    acq["log_date"] = pd.to_datetime(acq["log_date"], errors="coerce")
    comp["log_date"] = pd.to_datetime(comp["log_date"], errors="coerce")

    acq = acq.dropna(subset=["log_date"])
    comp = comp.dropna(subset=["log_date"])

    acq = acq[acq["clues"] > 0].copy()
    comp = comp[comp["clues_completed"] > 0].copy()

    if acq.empty or comp.empty:
        return fig

    acq["date"] = acq["log_date"].dt.date
    comp["date"] = comp["log_date"].dt.date

    acq_daily = (
        acq.groupby("date", as_index=False)
        .agg(
            acq_seconds=("duration_seconds", "sum"),
            acq_caskets=("clues", "sum"),
        )
        .sort_values("date")
    )

    comp_daily = (
        comp.groupby("date", as_index=False)
        .agg(
            comp_seconds=("duration_seconds", "sum"),
            comp_caskets=("clues_completed", "sum"),
        )
        .sort_values("date")
    )

    d = (
        pd.merge(acq_daily, comp_daily, on="date", how="outer")
        .sort_values("date")
        .fillna(0)
    )

    d["date"] = pd.to_datetime(d["date"])

    d["cum_acq_seconds"] = d["acq_seconds"].cumsum()
    d["cum_acq_caskets"] = d["acq_caskets"].cumsum()
    d["cum_comp_seconds"] = d["comp_seconds"].cumsum()
    d["cum_comp_caskets"] = d["comp_caskets"].cumsum()

    d = d[(d["cum_acq_caskets"] > 0) & (d["cum_comp_caskets"] > 0)].copy()

    if d.empty:
        return fig

    d["cum_acq_sec_per_casket"] = d["cum_acq_seconds"] / d["cum_acq_caskets"]
    d["cum_comp_sec_per_casket"] = d["cum_comp_seconds"] / d["cum_comp_caskets"]
    d["end_to_end_cph"] = 3600.0 / (
        d["cum_acq_sec_per_casket"] + d["cum_comp_sec_per_casket"]
    )

    # Use date strings so the x-axis shows each date only once
    d["date_label"] = d["date"].dt.strftime("%Y-%m-%d")

    main_color = "#10b981"
    avg_color = "#86efac"

    fig.add_trace(
        go.Scatter(
            x=d["date_label"],
            y=d["end_to_end_cph"],
            mode="lines+markers",
            name="End-to-end caskets/hr",
            line=dict(color=main_color, width=3),
            marker=dict(color=main_color, size=7),
            hovertemplate="%{x}<br>End-to-end caskets/hr: %{y:.2f}<extra></extra>",
        )
    )

    avg_val = float(d["end_to_end_cph"].mean())
    fig.add_trace(
        go.Scatter(
            x=d["date_label"],
            y=[avg_val] * len(d),
            mode="lines",
            name="Average",
            line=dict(color=avg_color, width=2.5, dash="dash"),
            hovertemplate="Average: %{y:.2f}<extra></extra>",
        )
    )

    fig.update_layout(
        margin=dict(l=40, r=40, t=70, b=40),
        xaxis=dict(
            title="Date",
            type="category",
            categoryorder="array",
            categoryarray=d["date_label"].tolist(),
        ),
    )

    return fig


# ----------------------------
# Data schemas
# ----------------------------
ACQ_COLS = (
    "trip_id",
    "log_date",
    "start_playtime",
    "end_playtime",
    "duration_seconds_playtime",
    "start_system",
    "end_system",
    "duration_seconds_system",
    "duration_seconds",
    "start_bloods",
    "end_bloods",
    "bloods_used",
    "deaths_used",
    "gp_cost",
    "clues",
    "gp_per_clue",
    "clues_per_hour",
    "gp_per_hour",
    "notes",
)

COMP_COLS = (
    "session_id",
    "log_date",
    "start_playtime",
    "end_playtime",
    "duration_seconds_playtime",
    "start_system",
    "end_system",
    "duration_seconds_system",
    "duration_seconds",
    "clues_completed",
    "clues_per_hour",
    "notes",
)


# ----------------------------
# Session State
# ----------------------------
def ss_init() -> None:
    st.session_state.setdefault("acq_start_system", None)
    st.session_state.setdefault("acq_end_system", None)
    st.session_state.setdefault("comp_start_system", None)
    st.session_state.setdefault("comp_end_system", None)

    st.session_state.setdefault("w_acq_date", date.today())
    st.session_state.setdefault("w_acq_start_play", "")
    st.session_state.setdefault("w_acq_end_play", "")
    st.session_state.setdefault("w_acq_start_blood", None)
    st.session_state.setdefault("w_acq_end_blood", None)
    st.session_state.setdefault("w_acq_clues", DEFAULT_CLUES_PER_TRIP)
    st.session_state.setdefault("w_acq_notes", "")

    st.session_state.setdefault("w_comp_date", date.today())
    st.session_state.setdefault("w_comp_start_play", "")
    st.session_state.setdefault("w_comp_end_play", "")
    st.session_state.setdefault("w_comp_completed", 10)
    st.session_state.setdefault("w_comp_notes", "")

    st.session_state.setdefault("pending_apply", False)
    st.session_state.setdefault("pending", {})



def apply_pending_before_widgets() -> None:
    if st.session_state.get("pending_apply") and isinstance(st.session_state.get("pending"), dict):
        for k, v in st.session_state["pending"].items():
            st.session_state[k] = v
        st.session_state["pending"] = {}
        st.session_state["pending_apply"] = False


ss_init()
apply_pending_before_widgets()


# ----------------------------
# Summaries
# ----------------------------
def summarize_acq(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {}
    d = coerce_numeric(df, ["clues", "duration_seconds", "gp_cost"]).copy()
    total_trips = len(d)
    total_clues = int(d["clues"].fillna(0).sum())
    total_seconds = float(d["duration_seconds"].fillna(0).sum())
    total_gp = float(d["gp_cost"].fillna(0).sum())

    avg_seconds_per_trip = float(d["duration_seconds"].dropna().mean()) if d["duration_seconds"].notna().any() else 0.0
    avg_seconds_per_clue = total_seconds / total_clues if total_clues > 0 else 0.0
    avg_gp_per_clue = total_gp / total_clues if total_clues > 0 else 0.0

    total_hours = total_seconds / 3600 if total_seconds > 0 else 0.0
    clues_per_hour = total_clues / total_hours if total_hours > 0 else 0.0
    gp_per_hour = total_gp / total_hours if total_hours > 0 else 0.0

    remaining = max(0, GOAL_CASKETS - total_clues)
    proj_seconds_remaining = remaining * avg_seconds_per_clue
    proj_gp_remaining = remaining * avg_gp_per_clue

    return {
        "total_trips": total_trips,
        "total_clues": total_clues,
        "avg_time_trip_s": avg_seconds_per_trip,
        "avg_time_clue_s": avg_seconds_per_clue,
        "avg_gp_per_clue": avg_gp_per_clue,
        "clues_per_hour": clues_per_hour,
        "gp_per_hour": gp_per_hour,
        "remaining": remaining,
        "proj_time_remaining_s": proj_seconds_remaining,
        "proj_gp_remaining": proj_gp_remaining,
    }



def summarize_comp(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {}
    d = coerce_numeric(df, ["clues_completed", "duration_seconds"]).copy()
    total_sessions = len(d)
    total_completed = int(d["clues_completed"].fillna(0).sum())
    total_seconds = float(d["duration_seconds"].fillna(0).sum())

    avg_seconds_per_session = float(d["duration_seconds"].dropna().mean()) if d["duration_seconds"].notna().any() else 0.0
    avg_seconds_per_casket = total_seconds / total_completed if total_completed > 0 else 0.0
    total_hours = total_seconds / 3600 if total_seconds > 0 else 0.0
    caskets_per_hour = total_completed / total_hours if total_hours > 0 else 0.0

    remaining = max(0, GOAL_CASKETS - total_completed)
    proj_seconds_remaining = remaining * avg_seconds_per_casket

    return {
        "total_sessions": total_sessions,
        "total_completed": total_completed,
        "avg_time_session_s": avg_seconds_per_session,
        "avg_time_casket_s": avg_seconds_per_casket,
        "caskets_per_hour": caskets_per_hour,
        "remaining": remaining,
        "proj_time_remaining_s": proj_seconds_remaining,
    }


# ----------------------------
# Load data
# ----------------------------
SESSION_CACHE_KEY = get_session_cache_key()

acq_df = load_df(ACQ_CSV, ACQ_COLS, SESSION_CACHE_KEY)
comp_df = load_df(COMP_CSV, COMP_COLS, SESSION_CACHE_KEY)
acq_sum = summarize_acq(acq_df)
comp_sum = summarize_comp(comp_df)


# ----------------------------
# Header
# ----------------------------
st.title("Hard Clue Dashboard")
acq_logged = int(acq_sum.get("total_clues", 0))
progress = min(1.0, acq_logged / GOAL_CASKETS) if GOAL_CASKETS > 0 else 0.0
st.progress(progress, text=f"Progress to {GOAL_CASKETS} caskets: {acq_logged} / {GOAL_CASKETS} ({progress * 100:.1f}%)")
inject_ui_dom_script()


# ----------------------------
# Sidebar
# ----------------------------
with st.sidebar:
    st.header("Acquisition Logger")

    def acq_start_now() -> None:
        st.session_state["acq_start_system"] = now_local()
        st.session_state["acq_end_system"] = None

    def acq_end_now() -> None:
        st.session_state["acq_end_system"] = now_local()

    acq_btn_col1, acq_btn_col2 = st.columns(2)
    with acq_btn_col1:
        st.button("Start Now", on_click=acq_start_now, use_container_width=True, key="btn_acq_start")
    with acq_btn_col2:
        st.button("End Now", on_click=acq_end_now, use_container_width=True, key="btn_acq_end")

    s0 = st.session_state.get("acq_start_system")
    e0 = st.session_state.get("acq_end_system")
    st.caption(
        f"System start: **{s0.strftime('%Y-%m-%d %H:%M:%S') if s0 else '—'}**  \n"
        f"System end: **{e0.strftime('%Y-%m-%d %H:%M:%S') if e0 else '—'}**"
    )

    def save_acq() -> None:
        df = load_df(ACQ_CSV, ACQ_COLS, SESSION_CACHE_KEY)
        log_date = st.session_state["w_acq_date"]
        start_play = str(st.session_state["w_acq_start_play"]).strip()
        end_play = str(st.session_state["w_acq_end_play"]).strip()
        start_blood_raw = st.session_state["w_acq_start_blood"]
        end_blood_raw = st.session_state["w_acq_end_blood"]

        if start_blood_raw is None or end_blood_raw is None:
            raise ValueError("Enter both Start bloods and End bloods.")

        start_blood = int(start_blood_raw)
        end_blood = int(end_blood_raw)
        clues = int(st.session_state["w_acq_clues"])
        notes = str(st.session_state.get("w_acq_notes", "")).strip()

        dur_play = None
        if start_play and end_play:
            sp = parse_playtime_hhmm(start_play)
            ep = parse_playtime_hhmm(end_play)
            d = ep - sp
            if d <= 0:
                raise ValueError("End playtime must be greater than start playtime.")
            dur_play = int(d)

        ss = st.session_state.get("acq_start_system")
        ee = st.session_state.get("acq_end_system")
        dur_sys = None
        if ss and ee:
            d = (ee - ss).total_seconds()
            if d <= 0:
                raise ValueError("System End must be after System Start.")
            dur_sys = int(round(d))

        if dur_play is not None:
            dur = dur_play
        elif dur_sys is not None:
            dur = dur_sys
        else:
            raise ValueError("Provide playtime start/end OR press Start Now + End Now.")

        bloods_used = start_blood - end_blood
        if bloods_used < 0:
            raise ValueError("End bloods is higher than start bloods.")

        deaths_used = int(bloods_used * DEATHS_PER_BLOOD)
        gp_cost = float(bloods_used * PRICE_BLOOD + deaths_used * PRICE_DEATH)
        hours = dur / 3600.0
        clues_per_hour = float(clues / hours) if hours > 0 else 0.0
        gp_per_hour = float(gp_cost / hours) if hours > 0 else 0.0
        gp_per_clue = float(gp_cost / clues) if clues > 0 else 0.0

        numeric_ids = pd.to_numeric(df["trip_id"], errors="coerce") if not df.empty else pd.Series(dtype=float)
        next_id = int(numeric_ids.max() + 1) if numeric_ids.notna().any() else 1

        row = {
            "trip_id": next_id,
            "log_date": log_date.isoformat(),
            "start_playtime": start_play,
            "end_playtime": end_play,
            "duration_seconds_playtime": dur_play if dur_play is not None else "",
            "start_system": ss.strftime("%Y-%m-%d %H:%M:%S") if ss else "",
            "end_system": ee.strftime("%Y-%m-%d %H:%M:%S") if ee else "",
            "duration_seconds_system": dur_sys if dur_sys is not None else "",
            "duration_seconds": int(dur),
            "start_bloods": start_blood,
            "end_bloods": end_blood,
            "bloods_used": int(bloods_used),
            "deaths_used": int(deaths_used),
            "gp_cost": gp_cost,
            "clues": clues,
            "gp_per_clue": gp_per_clue,
            "clues_per_hour": clues_per_hour,
            "gp_per_hour": gp_per_hour,
            "notes": notes,
        }
        append_row(ACQ_CSV, ACQ_COLS, row)
        clear_loaded_data_cache()

        st.session_state["pending"] = {
            "w_acq_start_play": end_play if end_play else st.session_state.get("w_acq_start_play", ""),
            "w_acq_end_play": "",
            "w_acq_start_blood": end_blood,
            "w_acq_end_blood": None,
            "w_acq_notes": "",
        }
        st.session_state["pending_apply"] = True

        if ee:
            st.session_state["acq_start_system"] = ee
        st.session_state["acq_end_system"] = None

    with st.form("acquisition_logger_form", clear_on_submit=False):
        st.date_input("Date", key="w_acq_date")
        st.text_input("Start playtime (HH.mm)", key="w_acq_start_play", placeholder="")
        st.text_input("End playtime (HH.mm)", key="w_acq_end_play", placeholder="")
        st.number_input("Start bloods", min_value=0, step=1, value=None, key="w_acq_start_blood")
        st.number_input("End bloods", min_value=0, step=1, value=None, key="w_acq_end_blood")
        st.number_input("Clues obtained", min_value=1, step=1, key="w_acq_clues")
        st.text_area("Notes", key="w_acq_notes", height=72, placeholder="")
        st.caption("Duration uses playtime if both are entered; otherwise uses system Start/End.")
        acq_submit = st.form_submit_button("Save Acquisition Trip", type="primary", use_container_width=True)

    if acq_submit:
        try:
            save_acq()
            st.success("Saved acquisition trip.")
            st.rerun()
        except Exception as ex:
            st.error(str(ex))

    st.divider()
    st.header("Completion Logger")

    def comp_start_now() -> None:
        st.session_state["comp_start_system"] = now_local()
        st.session_state["comp_end_system"] = None

    def comp_end_now() -> None:
        st.session_state["comp_end_system"] = now_local()

    comp_btn_col1, comp_btn_col2 = st.columns(2)
    with comp_btn_col1:
        st.button("Start Now", on_click=comp_start_now, use_container_width=True, key="btn_comp_start")
    with comp_btn_col2:
        st.button("End Now", on_click=comp_end_now, use_container_width=True, key="btn_comp_end")

    s1 = st.session_state.get("comp_start_system")
    e1 = st.session_state.get("comp_end_system")
    st.caption(
        f"System start: **{s1.strftime('%Y-%m-%d %H:%M:%S') if s1 else '—'}**  \n"
        f"System end: **{e1.strftime('%Y-%m-%d %H:%M:%S') if e1 else '—'}**"
    )

    def save_comp() -> None:
        df = load_df(COMP_CSV, COMP_COLS, SESSION_CACHE_KEY)
        log_date = st.session_state["w_comp_date"]
        start_play = str(st.session_state["w_comp_start_play"]).strip()
        end_play = str(st.session_state["w_comp_end_play"]).strip()
        completed = int(st.session_state["w_comp_completed"])
        notes = str(st.session_state.get("w_comp_notes", "")).strip()

        dur_play = None
        if start_play and end_play:
            sp = parse_playtime_hhmm(start_play)
            ep = parse_playtime_hhmm(end_play)
            d = ep - sp
            if d <= 0:
                raise ValueError("End playtime must be greater than start playtime.")
            dur_play = int(d)

        ss = st.session_state.get("comp_start_system")
        ee = st.session_state.get("comp_end_system")
        dur_sys = None
        if ss and ee:
            d = (ee - ss).total_seconds()
            if d <= 0:
                raise ValueError("System End must be after System Start.")
            dur_sys = int(round(d))

        if dur_play is not None:
            dur = dur_play
        elif dur_sys is not None:
            dur = dur_sys
        else:
            raise ValueError("Provide playtime start/end OR press Start Now + End Now.")

        hours = dur / 3600.0
        clues_per_hour = float(completed / hours) if hours > 0 else 0.0
        numeric_ids = pd.to_numeric(df["session_id"], errors="coerce") if not df.empty else pd.Series(dtype=float)
        next_id = int(numeric_ids.max() + 1) if numeric_ids.notna().any() else 1

        row = {
            "session_id": next_id,
            "log_date": log_date.isoformat(),
            "start_playtime": start_play,
            "end_playtime": end_play,
            "duration_seconds_playtime": dur_play if dur_play is not None else "",
            "start_system": ss.strftime("%Y-%m-%d %H:%M:%S") if ss else "",
            "end_system": ee.strftime("%Y-%m-%d %H:%M:%S") if ee else "",
            "duration_seconds_system": dur_sys if dur_sys is not None else "",
            "duration_seconds": int(dur),
            "clues_completed": int(completed),
            "clues_per_hour": clues_per_hour,
            "notes": notes,
        }
        append_row(COMP_CSV, COMP_COLS, row)
        clear_loaded_data_cache()

        pending = {"w_comp_end_play": "", "w_comp_notes": ""}
        if end_play:
            pending["w_comp_start_play"] = end_play
        if ee:
            st.session_state["comp_start_system"] = ee
        st.session_state["comp_end_system"] = None
        st.session_state["pending"] = pending
        st.session_state["pending_apply"] = True

    with st.form("completion_logger_form", clear_on_submit=False):
        st.date_input("Date", key="w_comp_date")
        st.text_input("Start playtime (HH.mm)", key="w_comp_start_play", placeholder="")
        st.text_input("End playtime (HH.mm)", key="w_comp_end_play", placeholder="")
        st.number_input("Caskets completed", min_value=1, step=1, key="w_comp_completed")
        st.text_area("Notes", key="w_comp_notes", height=72, placeholder="")
        st.caption("Duration uses playtime if both are entered; otherwise uses system Start/End.")
        comp_submit = st.form_submit_button("Save Completion Session", type="primary", use_container_width=True)

    if comp_submit:
        try:
            save_comp()
            st.success("Saved completion session.")
            st.rerun()
        except Exception as ex:
            st.error(str(ex))


# ----------------------------
# Tabs
# ----------------------------
tab_acq, tab_comp, tab_combo = st.tabs(["Acquisition", "Completion", "End-to-end"])


with tab_acq:
    if acq_df.empty:
        st.info("No acquisition trips logged yet.")
    else:
        total = acq_sum["total_clues"]
        remaining = acq_sum["remaining"]

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Trips", int(acq_sum["total_trips"]))
        k2.metric("Clues logged", int(total))
        k3.metric("Avg time / trip", seconds_to_hhmm(acq_sum["avg_time_trip_s"]))
        k4.metric("Avg cost / casket", human_gp(acq_sum["avg_gp_per_clue"]))
        k5.metric("Clues / hour", f"{acq_sum['clues_per_hour']:.2f}")

        st.divider()

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Expected alch / casket", human_gp(EXPECTED_ALCH_GP_PER_CASKET))
        net_per = EXPECTED_ALCH_GP_PER_CASKET - acq_sum["avg_gp_per_clue"]
        m2.metric("Net gp / casket", human_gp(net_per))
        m3.metric("GP cost remaining", human_gp(acq_sum["proj_gp_remaining"]))
        m4.metric("Expected alch remaining", human_gp(EXPECTED_ALCH_GP_PER_CASKET * remaining))
        m5.metric("Expected net remaining", human_gp(net_per * remaining))

        st.divider()

        t1, t2, t3 = st.columns(3)
        t1.metric("Time remaining (acquire)", fmt_hours_minutes(acq_sum["proj_time_remaining_s"]))
        t2.metric("Remaining caskets", int(remaining))
        t3.metric("Trips remaining (rough)", math.ceil(remaining / DEFAULT_CLUES_PER_TRIP) if DEFAULT_CLUES_PER_TRIP else 0)

        st.divider()

        disp = acq_df.copy()
        disp = coerce_numeric(disp, ["trip_id", "duration_seconds", "clues", "bloods_used", "deaths_used", "gp_cost", "gp_per_clue", "clues_per_hour"])
        disp["duration"] = disp["duration_seconds"].apply(seconds_to_hhmm)
        disp["gp_cost"] = disp["gp_cost"].round(0)
        disp["gp_per_clue"] = disp["gp_per_clue"].round(1)
        disp["clues_per_hour"] = disp["clues_per_hour"].round(2)
        if "notes" not in disp.columns:
            disp["notes"] = ""

        st.subheader("Trip Log")
        st.dataframe(
            disp[["trip_id", "log_date", "duration", "clues", "bloods_used", "deaths_used", "gp_cost", "gp_per_clue", "clues_per_hour", "notes"]]
            .sort_values("trip_id", ascending=False),
            use_container_width=True,
            height=350,
        )

        st.divider()
        st.subheader("Charts")
        st.plotly_chart(build_acq_combined_chart(acq_df), use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(build_acq_scatter(acq_df), use_container_width=True)
        with col2:
            st.plotly_chart(build_duration_histogram(acq_df, "duration_seconds", "trip_id", "Trip duration distribution"), use_container_width=True)


with tab_comp:
    if comp_df.empty:
        st.info("No completion sessions logged yet.")
    else:
        total_completed = int(comp_sum["total_completed"])
        remaining = comp_sum["remaining"]

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Sessions", int(comp_sum["total_sessions"]))
        k2.metric("Caskets completed logged", total_completed)
        k3.metric("Average time / casket", seconds_to_hhmm(comp_sum["avg_time_casket_s"]))
        k4.metric("Caskets / hour", f"{comp_sum['caskets_per_hour']:.2f}")

        st.divider()

        t1, t2 = st.columns(2)
        t1.metric("Time remaining (complete)", fmt_hours_minutes(comp_sum["proj_time_remaining_s"]))
        t2.metric("Remaining to 650 (complete)", int(max(0, GOAL_CASKETS - total_completed)))

        st.divider()

        disp = comp_df.copy()
        disp = coerce_numeric(disp, ["session_id", "duration_seconds", "clues_completed", "clues_per_hour"])
        disp["duration"] = disp["duration_seconds"].apply(seconds_to_hhmm)
        disp["clues_per_hour"] = disp["clues_per_hour"].round(2)
        if "notes" not in disp.columns:
            disp["notes"] = ""

        st.subheader("Completion Log")
        st.dataframe(
            disp[["session_id", "log_date", "duration", "clues_completed", "clues_per_hour", "notes"]]
            .rename(columns={"clues_completed": "caskets_completed", "clues_per_hour": "caskets_per_hour"})
            .sort_values("session_id", ascending=False),
            use_container_width=True,
            height=350,
        )

        st.divider()
        st.subheader("Charts")
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(build_completion_cph_chart(comp_df), use_container_width=True)
        with c2:
            st.plotly_chart(build_completion_histogram(comp_df), use_container_width=True)


with tab_combo:
    st.subheader("End-to-end estimates (Acquire + Complete)")
    if acq_df.empty or comp_df.empty:
        st.info("Log at least one acquisition trip and one completion session to get end-to-end averages.")
    else:
        acq_min_per = acq_sum["avg_time_clue_s"] / 60.0
        comp_min_per = comp_sum["avg_time_casket_s"] / 60.0
        total_min_per = acq_min_per + comp_min_per
        total_caskets_per_hour = 60.0 / total_min_per if total_min_per > 0 else 0.0

        remaining = max(0, GOAL_CASKETS - int(acq_sum["total_clues"]))
        remaining_seconds_total = remaining * (acq_sum["avg_time_clue_s"] + comp_sum["avg_time_casket_s"])

        a, b, c, d, e = st.columns(5)
        a.metric("Acquire min / casket", f"{acq_min_per:.2f}")
        b.metric("Complete min / casket", f"{comp_min_per:.2f}")
        c.metric("Total min / casket", f"{total_min_per:.2f}")
        d.metric("Caskets / hour", f"{total_caskets_per_hour:.2f}")
        e.metric("Time remaining (total)", fmt_hours_minutes(remaining_seconds_total))

        st.divider()
        st.plotly_chart(build_end_to_end_chart(acq_df, comp_df), use_container_width=True)
        st.caption(
            "This chart uses cumulative logged acquisition time per casket and cumulative logged completion time per casket, "
            "grouped by date, to show how your observed end-to-end caskets per hour changes over time."
        )
