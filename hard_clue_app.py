import os
from datetime import date, datetime
from typing import Dict, Any
from uuid import uuid4

from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

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
section[data-testid="stSidebar"] [data-testid="stFormInstructions"] {
  display: none !important;
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
          const sidebar = rootDoc.querySelector('section[data-testid="stSidebar"]');
          if (!sidebar) return;

          const isSubmitHintText = (value) => {
            if (!value) return false;
            const normalized = value
              .toLowerCase()
              .replace(/⌘/g, 'command')
              .replace(/\\s+/g, ' ')
              .trim();
            if (!normalized.startsWith('press')) return false;
            if (!normalized.includes('enter')) return false;
            if (!normalized.includes('submit')) return false;
            return normalized.includes('form');
          };

          const hintContainers = sidebar.querySelectorAll(
            '[data-testid="stFormInstructions"], [data-testid="stCaptionContainer"], [data-testid="stMarkdownContainer"]'
          );

          hintContainers.forEach((el) => {
            const text = (el.textContent || '').trim();
            if (!text || text.length > 160) return;
            if (!isSubmitHintText(text)) return;
            el.style.display = 'none';
          });

          sidebar.querySelectorAll('*').forEach((el) => {
            if (el.dataset.uiSubmitHintHidden === '1') return;
            const text = (el.textContent || '').trim();
            if (!text || text.length > 90) return;
            if (!isSubmitHintText(text)) return;
            if (el.querySelector('input, textarea, button, select, [role="textbox"]')) return;
            el.style.display = 'none';
            el.dataset.uiSubmitHintHidden = '1';
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
              button.style.background = Object.prototype.hasOwnProperty.call(styles, 'bg') ? styles.bg : '';
              button.style.borderColor = Object.prototype.hasOwnProperty.call(styles, 'border') ? styles.border : '';
              button.style.color = Object.prototype.hasOwnProperty.call(styles, 'textColor') ? styles.textColor : '';
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
        if (!rootDoc.body.dataset.uiSubmitHintFocusBound) {
          rootDoc.body.dataset.uiSubmitHintFocusBound = '1';
          rootDoc.addEventListener('focusin', hidePressEnterHints, true);
        }
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



def minutes_to_hhmm(total_minutes: float) -> str:
    return seconds_to_hhmm(float(total_minutes or 0) * 60.0)


def prepare_acq_metrics(df: pd.DataFrame) -> pd.DataFrame:
    d = coerce_numeric(
        df,
        [
            "trip_id",
            "duration_seconds",
            "clues",
            "bloods_used",
            "deaths_used",
            "gp_cost",
            "gp_per_clue",
            "clues_per_hour",
        ],
    ).copy()
    d["log_date"] = pd.to_datetime(d["log_date"], errors="coerce")
    if "notes" not in d.columns:
        d["notes"] = ""
    d["notes"] = d["notes"].fillna("")

    d = d.sort_values(["trip_id", "log_date"], na_position="last").copy()
    clues = d["clues"].where(d["clues"] > 0)
    hours = d["duration_seconds"] / 3600.0

    d["minutes_per_clue"] = (d["duration_seconds"] / 60.0).div(clues)
    d["bloods_per_clue"] = d["bloods_used"].div(clues)
    d["gp_spent_per_clue"] = d["gp_per_clue"].where(d["gp_per_clue"].notna(), d["gp_cost"].div(clues))
    d["clues_per_hour"] = d["clues_per_hour"].where(d["clues_per_hour"].notna(), d["clues"].div(hours))
    d["rolling_10_trip_avg_minutes_per_clue"] = d["minutes_per_clue"].rolling(window=10, min_periods=1).mean()
    d["duration"] = d["duration_seconds"].apply(seconds_to_hhmm)
    d["log_date"] = d["log_date"].dt.date
    return d


def prepare_comp_metrics(df: pd.DataFrame) -> pd.DataFrame:
    d = coerce_numeric(
        df,
        [
            "session_id",
            "duration_seconds",
            "clues_completed",
            "clues_per_hour",
        ],
    ).copy()
    d["log_date"] = pd.to_datetime(d["log_date"], errors="coerce")
    if "notes" not in d.columns:
        d["notes"] = ""
    d["notes"] = d["notes"].fillna("")

    d = d.sort_values(["session_id", "log_date"], na_position="last").copy()
    completed = d["clues_completed"].where(d["clues_completed"] > 0)
    hours = d["duration_seconds"] / 3600.0

    d["minutes_per_casket"] = (d["duration_seconds"] / 60.0).div(completed)
    d["caskets_per_hour"] = d["clues_per_hour"].where(d["clues_per_hour"].notna(), d["clues_completed"].div(hours))
    d["rolling_10_session_avg_minutes_per_casket"] = d["minutes_per_casket"].rolling(window=10, min_periods=1).mean()
    d["duration"] = d["duration_seconds"].apply(seconds_to_hhmm)
    d["log_date"] = d["log_date"].dt.date
    return d


def build_range_histogram(series: pd.Series, title: str, x_title: str, y_title: str, height: int = 340) -> go.Figure:
    values = pd.to_numeric(series, errors="coerce").dropna()
    fig = go.Figure()
    if values.empty:
        fig.update_layout(title=title, height=height)
        return fig

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
        if int(c) <= 0 or not isinstance(interval, pd.Interval):
            continue
        labels.append(f"{float(interval.left):.2f}–{float(interval.right):.2f}")
        counts.append(int(c))

    fig.add_trace(go.Bar(x=labels, y=counts, name="Count", marker_color="#4f46e5"))
    fig.update_layout(
        title=title,
        height=height,
        margin=dict(l=40, r=20, t=48, b=40),
        xaxis=dict(title=x_title),
        yaxis=dict(title=y_title),
        showlegend=False,
    )
    return fig


def build_acq_minutes_per_clue_chart(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["trip_id", "minutes_per_clue"]).sort_values("trip_id").copy()
    fig = go.Figure()
    fig.update_layout(**make_line_layout("Minutes per clue by trip", "Trip #", "Minutes per clue", height=420))
    fig.update_layout(
        margin=dict(l=40, r=40, t=95, b=40),
        title=dict(y=0.97),
        legend=dict(orientation="h", yanchor="bottom", y=1.12, xanchor="left", x=0),
    )
    if d.empty:
        return fig

    fig.add_trace(
        go.Scatter(
            x=d["trip_id"],
            y=d["minutes_per_clue"],
            mode="lines+markers",
            name="Minutes per clue",
            line=dict(color="#1d4ed8", width=3),
            marker=dict(color="#1d4ed8", size=7),
            hovertemplate="Trip %{x}<br>Minutes/clue: %{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=d["trip_id"],
            y=d["rolling_10_trip_avg_minutes_per_clue"],
            mode="lines",
            name="Rolling 10-trip avg",
            line=dict(color="#60a5fa", width=2.5, dash="dash"),
            hovertemplate="Rolling avg: %{y:.2f} min/clue<extra></extra>",
        )
    )

    overall_avg = float(d["minutes_per_clue"].mean())
    fig.add_trace(
        go.Scatter(
            x=d["trip_id"],
            y=[overall_avg] * len(d),
            mode="lines",
            name="Overall avg",
            line=dict(color="#93c5fd", width=2, dash="dot"),
            hovertemplate="Overall avg: %{y:.2f} min/clue<extra></extra>",
        )
    )
    return fig


def build_acq_gp_per_clue_chart(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["trip_id", "gp_spent_per_clue"]).sort_values("trip_id").copy()
    fig = go.Figure()
    fig.update_layout(**make_line_layout("GP spent per clue by trip", "Trip #", "GP spent per clue", height=340))
    if d.empty:
        return fig

    fig.add_trace(
        go.Scatter(
            x=d["trip_id"],
            y=d["gp_spent_per_clue"],
            mode="lines+markers",
            name="GP spent per clue",
            line=dict(color="#b45309", width=3),
            marker=dict(color="#b45309", size=7),
            hovertemplate="Trip %{x}<br>GP spent/clue: %{y:,.0f}<extra></extra>",
        )
    )
    return fig


def build_completion_minutes_per_casket_chart(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["session_id", "minutes_per_casket"]).sort_values("session_id").copy()
    fig = go.Figure()
    fig.update_layout(
        **make_line_layout("Minutes per casket by session", "Session #", "Minutes per casket", height=420)
    )
    fig.update_layout(
        margin=dict(l=40, r=40, t=95, b=40),
        title=dict(y=0.97),
        legend=dict(orientation="h", yanchor="bottom", y=1.12, xanchor="left", x=0),
    )
    if d.empty:
        return fig

    fig.add_trace(
        go.Scatter(
            x=d["session_id"],
            y=d["minutes_per_casket"],
            mode="lines+markers",
            name="Minutes per casket",
            line=dict(color="#0f766e", width=3),
            marker=dict(color="#0f766e", size=7),
            hovertemplate="Session %{x}<br>Minutes/casket: %{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=d["session_id"],
            y=d["rolling_10_session_avg_minutes_per_casket"],
            mode="lines",
            name="Rolling 10-session avg",
            line=dict(color="#5eead4", width=2.5, dash="dash"),
            hovertemplate="Rolling avg: %{y:.2f} min/casket<extra></extra>",
        )
    )
    return fig


def build_completion_caskets_per_hour_chart(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["session_id", "caskets_per_hour"]).sort_values("session_id").copy()
    fig = go.Figure()
    fig.update_layout(**make_line_layout("Caskets per hour by session", "Session #", "Caskets per hour", height=340))
    if d.empty:
        return fig

    fig.add_trace(
        go.Scatter(
            x=d["session_id"],
            y=d["caskets_per_hour"],
            mode="lines+markers",
            name="Caskets per hour",
            line=dict(color="#047857", width=3),
            marker=dict(color="#047857", size=7),
            hovertemplate="Session %{x}<br>Caskets/hr: %{y:.2f}<extra></extra>",
        )
    )
    return fig


def build_end_to_end_trend_df(acq_df: pd.DataFrame, comp_df: pd.DataFrame) -> pd.DataFrame:
    acq = coerce_numeric(acq_df, ["duration_seconds", "clues"]).copy()
    comp = coerce_numeric(comp_df, ["duration_seconds", "clues_completed"]).copy()
    acq["log_date"] = pd.to_datetime(acq["log_date"], errors="coerce")
    comp["log_date"] = pd.to_datetime(comp["log_date"], errors="coerce")

    acq = acq.dropna(subset=["log_date", "duration_seconds", "clues"])
    comp = comp.dropna(subset=["log_date", "duration_seconds", "clues_completed"])
    acq = acq[acq["clues"] > 0].copy()
    comp = comp[comp["clues_completed"] > 0].copy()
    if acq.empty or comp.empty:
        return pd.DataFrame()

    acq["date"] = acq["log_date"].dt.date
    comp["date"] = comp["log_date"].dt.date

    acq_daily = (
        acq.groupby("date", as_index=False)
        .agg(acq_seconds=("duration_seconds", "sum"), acq_caskets=("clues", "sum"))
        .sort_values("date")
    )
    comp_daily = (
        comp.groupby("date", as_index=False)
        .agg(comp_seconds=("duration_seconds", "sum"), comp_caskets=("clues_completed", "sum"))
        .sort_values("date")
    )

    d = pd.merge(acq_daily, comp_daily, on="date", how="outer").sort_values("date").fillna(0)
    d["date"] = pd.to_datetime(d["date"])
    d["cum_acq_seconds"] = d["acq_seconds"].cumsum()
    d["cum_acq_caskets"] = d["acq_caskets"].cumsum()
    d["cum_comp_seconds"] = d["comp_seconds"].cumsum()
    d["cum_comp_caskets"] = d["comp_caskets"].cumsum()
    d = d[(d["cum_acq_caskets"] > 0) & (d["cum_comp_caskets"] > 0)].copy()
    if d.empty:
        return pd.DataFrame()

    d["acquire_minutes_per_casket"] = (d["cum_acq_seconds"] / d["cum_acq_caskets"]) / 60.0
    d["complete_minutes_per_casket"] = (d["cum_comp_seconds"] / d["cum_comp_caskets"]) / 60.0
    d["total_minutes_per_casket"] = d["acquire_minutes_per_casket"] + d["complete_minutes_per_casket"]
    d["end_to_end_caskets_per_hour"] = d["total_minutes_per_casket"].apply(lambda x: 60.0 / x if x > 0 else 0.0)
    d["date_label"] = d["date"].dt.strftime("%Y-%m-%d")
    return d


def build_end_to_end_stacked_time_chart(end_to_end_sum: Dict[str, Any]) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=["Current full-cycle"],
            y=[end_to_end_sum["acquire_minutes_per_casket"]],
            name="Acquisition",
            marker_color="#1d4ed8",
            text=[f"{end_to_end_sum['acquire_minutes_per_casket']:.2f}"],
            textposition="inside",
        )
    )
    fig.add_trace(
        go.Bar(
            x=["Current full-cycle"],
            y=[end_to_end_sum["complete_minutes_per_casket"]],
            name="Completion",
            marker_color="#0f766e",
            text=[f"{end_to_end_sum['complete_minutes_per_casket']:.2f}"],
            textposition="inside",
        )
    )
    fig.update_layout(
        barmode="stack",
        title=dict(text="Stacked time breakdown per casket", y=0.97),
        height=360,
        margin=dict(l=40, r=20, t=95, b=40),
        xaxis=dict(title=""),
        yaxis=dict(title="Minutes per casket"),
        legend=dict(orientation="h", yanchor="bottom", y=1.12, xanchor="left", x=0),
    )
    return fig


def build_end_to_end_cph_chart(trend_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(**make_line_layout("End-to-end caskets per hour over time", "Date", "Caskets per hour", height=380))
    if trend_df.empty:
        return fig

    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["end_to_end_caskets_per_hour"],
            mode="lines+markers",
            name="End-to-end caskets/hr",
            line=dict(color="#10b981", width=3),
            marker=dict(color="#10b981", size=7),
            hovertemplate="%{x}<br>End-to-end caskets/hr: %{y:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis=dict(
            title="Date",
            type="category",
            categoryorder="array",
            categoryarray=trend_df["date_label"].tolist(),
        )
    )
    return fig


def build_end_to_end_minutes_chart(trend_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        **make_line_layout("Total minutes per casket over time", "Date", "Minutes per casket", height=340)
    )
    if trend_df.empty:
        return fig

    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["total_minutes_per_casket"],
            mode="lines+markers",
            name="Total minutes per casket",
            line=dict(color="#7c3aed", width=3),
            marker=dict(color="#7c3aed", size=7),
            hovertemplate="%{x}<br>Total min/casket: %{y:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis=dict(
            title="Date",
            type="category",
            categoryorder="array",
            categoryarray=trend_df["date_label"].tolist(),
        )
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
    d = coerce_numeric(df, ["clues", "duration_seconds", "gp_cost", "bloods_used"]).copy()
    total_trips = len(d)
    total_clues = int(d["clues"].fillna(0).sum())
    total_seconds = float(d["duration_seconds"].fillna(0).sum())
    total_gp = float(d["gp_cost"].fillna(0).sum())
    total_bloods = float(d["bloods_used"].fillna(0).sum())

    avg_seconds_per_trip = float(d["duration_seconds"].dropna().mean()) if d["duration_seconds"].notna().any() else 0.0
    avg_seconds_per_clue = total_seconds / total_clues if total_clues > 0 else 0.0
    avg_gp_per_clue = total_gp / total_clues if total_clues > 0 else 0.0
    avg_bloods_per_clue = total_bloods / total_clues if total_clues > 0 else 0.0

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
        "avg_bloods_per_clue": avg_bloods_per_clue,
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


def summarize_end_to_end(acq_sum: Dict[str, Any], comp_sum: Dict[str, Any]) -> Dict[str, Any]:
    if not acq_sum or not comp_sum:
        return {}

    acquire_minutes_per_casket = acq_sum["avg_time_clue_s"] / 60.0
    complete_minutes_per_casket = comp_sum["avg_time_casket_s"] / 60.0
    total_minutes_per_casket = acquire_minutes_per_casket + complete_minutes_per_casket
    end_to_end_caskets_per_hour = 60.0 / total_minutes_per_casket if total_minutes_per_casket > 0 else 0.0

    acquisition_share_of_total_time = (
        acquire_minutes_per_casket / total_minutes_per_casket if total_minutes_per_casket > 0 else 0.0
    )
    completion_share_of_total_time = (
        complete_minutes_per_casket / total_minutes_per_casket if total_minutes_per_casket > 0 else 0.0
    )

    expected_net_gp_per_casket = EXPECTED_ALCH_GP_PER_CASKET - acq_sum["avg_gp_per_clue"]
    end_to_end_gp_per_hour = expected_net_gp_per_casket * end_to_end_caskets_per_hour

    remaining_caskets = max(0, GOAL_CASKETS - int(acq_sum["total_clues"]))
    time_remaining_total_s = remaining_caskets * (acq_sum["avg_time_clue_s"] + comp_sum["avg_time_casket_s"])
    gp_cost_remaining = acq_sum["avg_gp_per_clue"] * remaining_caskets
    expected_alch_remaining = EXPECTED_ALCH_GP_PER_CASKET * remaining_caskets
    expected_net_remaining = expected_net_gp_per_casket * remaining_caskets

    if abs(acquire_minutes_per_casket - complete_minutes_per_casket) < 0.05:
        bottleneck = "Balanced"
    elif acquire_minutes_per_casket > complete_minutes_per_casket:
        bottleneck = "Acquisition"
    else:
        bottleneck = "Completion"

    return {
        "acquire_minutes_per_casket": acquire_minutes_per_casket,
        "complete_minutes_per_casket": complete_minutes_per_casket,
        "total_minutes_per_casket": total_minutes_per_casket,
        "end_to_end_caskets_per_hour": end_to_end_caskets_per_hour,
        "acquisition_share_of_total_time": acquisition_share_of_total_time,
        "completion_share_of_total_time": completion_share_of_total_time,
        "end_to_end_gp_per_hour": end_to_end_gp_per_hour,
        "expected_net_gp_per_casket": expected_net_gp_per_casket,
        "bottleneck": bottleneck,
        "time_remaining_total_s": time_remaining_total_s,
        "gp_cost_remaining": gp_cost_remaining,
        "expected_alch_remaining": expected_alch_remaining,
        "expected_net_remaining": expected_net_remaining,
        "remaining_caskets": remaining_caskets,
    }


# ----------------------------
# Load data
# ----------------------------
SESSION_CACHE_KEY = get_session_cache_key()

acq_df = load_df(ACQ_CSV, ACQ_COLS, SESSION_CACHE_KEY)
comp_df = load_df(COMP_CSV, COMP_COLS, SESSION_CACHE_KEY)
acq_sum = summarize_acq(acq_df)
comp_sum = summarize_comp(comp_df)
acq_metrics_df = prepare_acq_metrics(acq_df)
comp_metrics_df = prepare_comp_metrics(comp_df)
end_to_end_sum = summarize_end_to_end(acq_sum, comp_sum)
end_to_end_trend_df = build_end_to_end_trend_df(acq_df, comp_df)


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
        total = int(acq_sum["total_clues"])
        remaining = int(acq_sum["remaining"])
        rolling = acq_metrics_df["rolling_10_trip_avg_minutes_per_clue"].dropna()
        rolling_latest = float(rolling.iloc[-1]) if not rolling.empty else 0.0
        rolling_best = float(rolling.min()) if not rolling.empty else 0.0
        median_minutes_per_clue = float(acq_metrics_df["minutes_per_clue"].dropna().median()) if acq_metrics_df["minutes_per_clue"].notna().any() else 0.0

        st.caption(f"Target summary: {total} / {GOAL_CASKETS} clues acquired • {remaining} remaining")

        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("Trips", int(acq_sum["total_trips"]))
        k2.metric("Clues logged", total)
        k3.metric("Avg time / clue", seconds_to_hhmm(acq_sum["avg_time_clue_s"]))
        k4.metric("Clues / hour", f"{acq_sum['clues_per_hour']:.2f}")
        k5.metric("Bloods / clue", f"{acq_sum['avg_bloods_per_clue']:.2f}")
        k6.metric("GP spent / clue", human_gp(acq_sum["avg_gp_per_clue"]))

        st.divider()

        t1, t2, t3, t4, t5, t6 = st.columns(6)
        t1.metric("Avg trip length", seconds_to_hhmm(acq_sum["avg_time_trip_s"]))
        t2.metric("Rolling 10-trip avg time / clue", minutes_to_hhmm(rolling_latest))
        t3.metric("Median time / clue", minutes_to_hhmm(median_minutes_per_clue))
        t4.metric("Best rolling 10-trip time / clue", minutes_to_hhmm(rolling_best))
        t5.metric("Time remaining (acquire)", fmt_hours_minutes(acq_sum["proj_time_remaining_s"]))
        t6.metric("Remaining caskets", remaining)

        st.divider()
        st.subheader("Charts")
        st.plotly_chart(build_acq_minutes_per_clue_chart(acq_metrics_df), use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(build_acq_gp_per_clue_chart(acq_metrics_df), use_container_width=True)
        with c2:
            st.plotly_chart(
                build_range_histogram(
                    acq_metrics_df["minutes_per_clue"],
                    "Minutes per clue distribution",
                    "Minutes per clue range",
                    "Trips",
                ),
                use_container_width=True,
            )

        st.divider()
        st.subheader("Trip Log")
        disp = acq_metrics_df.copy()
        disp["clues"] = disp["clues"].round(0).astype("Int64")
        disp["bloods_used"] = disp["bloods_used"].round(0).astype("Int64")
        disp["deaths_used"] = disp["deaths_used"].round(0).astype("Int64")
        disp["minutes_per_clue"] = disp["minutes_per_clue"].round(2)
        disp["clues_per_hour"] = disp["clues_per_hour"].round(2)
        disp["bloods_per_clue"] = disp["bloods_per_clue"].round(2)
        disp["gp_spent_per_clue"] = disp["gp_spent_per_clue"].round(1)
        disp["gp_cost"] = disp["gp_cost"].round(0)
        st.dataframe(
            disp[
                [
                    "trip_id",
                    "log_date",
                    "clues",
                    "duration",
                    "minutes_per_clue",
                    "clues_per_hour",
                    "bloods_per_clue",
                    "gp_spent_per_clue",
                    "notes",
                    "bloods_used",
                    "deaths_used",
                    "gp_cost",
                ]
            ].sort_values("trip_id", ascending=False),
            use_container_width=True,
            height=350,
            hide_index=True,
            column_config={"notes": st.column_config.TextColumn("notes", width="large")},
        )


with tab_comp:
    if comp_df.empty:
        st.info("No completion sessions logged yet.")
    else:
        total_completed = int(comp_sum["total_completed"])
        remaining = comp_sum["remaining"]
        rolling = comp_metrics_df["rolling_10_session_avg_minutes_per_casket"].dropna()
        rolling_latest = float(rolling.iloc[-1]) if not rolling.empty else 0.0
        rolling_best = float(rolling.min()) if not rolling.empty else 0.0
        median_minutes_per_casket = float(comp_metrics_df["minutes_per_casket"].dropna().median()) if comp_metrics_df["minutes_per_casket"].notna().any() else 0.0
        fastest_minutes_per_casket = float(comp_metrics_df["minutes_per_casket"].dropna().min()) if comp_metrics_df["minutes_per_casket"].notna().any() else 0.0
        slowest_minutes_per_casket = float(comp_metrics_df["minutes_per_casket"].dropna().max()) if comp_metrics_df["minutes_per_casket"].notna().any() else 0.0

        st.caption(f"Target summary: {total_completed} / {GOAL_CASKETS} caskets completed • {int(remaining)} remaining")

        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("Sessions", int(comp_sum["total_sessions"]))
        k2.metric("Caskets completed logged", total_completed)
        k3.metric("Avg time / casket", seconds_to_hhmm(comp_sum["avg_time_casket_s"]))
        k4.metric("Caskets / hour", f"{comp_sum['caskets_per_hour']:.2f}")
        k5.metric("Median time / casket", minutes_to_hhmm(median_minutes_per_casket))
        k6.metric("Rolling 10-session avg time / casket", minutes_to_hhmm(rolling_latest))

        st.divider()

        t1, t2, t3, t4, t5, t6 = st.columns(6)
        t1.metric("Avg session length", seconds_to_hhmm(comp_sum["avg_time_session_s"]))
        t2.metric("Best rolling 10-session time / casket", minutes_to_hhmm(rolling_best))
        t3.metric("Fastest session time / casket", minutes_to_hhmm(fastest_minutes_per_casket))
        t4.metric("Slowest session time / casket", minutes_to_hhmm(slowest_minutes_per_casket))
        t5.metric("Time remaining (complete)", fmt_hours_minutes(comp_sum["proj_time_remaining_s"]))
        t6.metric("Remaining to 650 (complete)", int(max(0, GOAL_CASKETS - total_completed)))

        st.divider()
        st.subheader("Charts")
        st.plotly_chart(build_completion_minutes_per_casket_chart(comp_metrics_df), use_container_width=True)
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(build_completion_caskets_per_hour_chart(comp_metrics_df), use_container_width=True)
        with c2:
            st.plotly_chart(
                build_range_histogram(
                    comp_metrics_df["minutes_per_casket"],
                    "Minutes per casket distribution",
                    "Minutes per casket range",
                    "Sessions",
                ),
                use_container_width=True,
            )

        st.divider()
        st.subheader("Completion Log")
        disp = comp_metrics_df.copy()
        disp["caskets_completed"] = disp["clues_completed"].round(0).astype("Int64")
        disp["minutes_per_casket"] = disp["minutes_per_casket"].round(2)
        disp["caskets_per_hour"] = disp["caskets_per_hour"].round(2)
        st.dataframe(
            disp[
                [
                    "session_id",
                    "log_date",
                    "caskets_completed",
                    "duration",
                    "minutes_per_casket",
                    "caskets_per_hour",
                    "notes",
                ]
            ].sort_values("session_id", ascending=False),
            use_container_width=True,
            height=350,
            hide_index=True,
            column_config={"notes": st.column_config.TextColumn("notes", width="large")},
        )


with tab_combo:
    st.subheader("End-to-end")
    if acq_df.empty or comp_df.empty or not end_to_end_sum:
        st.info("Log at least one acquisition trip and one completion session to get end-to-end averages.")
    else:
        st.caption(
            f"Target summary: {int(acq_sum['total_clues'])} acquired • "
            f"{int(comp_sum['total_completed'])} completed • "
            f"{int(end_to_end_sum['remaining_caskets'])} remaining to {GOAL_CASKETS}"
        )

        a1, a2, a3, a4, a5, a6 = st.columns(6)
        a1.metric("Acquire min / casket", f"{end_to_end_sum['acquire_minutes_per_casket']:.2f}")
        a2.metric("Complete min / casket", f"{end_to_end_sum['complete_minutes_per_casket']:.2f}")
        a3.metric("Total min / casket", f"{end_to_end_sum['total_minutes_per_casket']:.2f}")
        a4.metric("Caskets / hour", f"{end_to_end_sum['end_to_end_caskets_per_hour']:.2f}")
        a5.metric("End-to-end GP / hour", human_gp(end_to_end_sum["end_to_end_gp_per_hour"]))
        a6.metric("Expected net GP / casket", human_gp(end_to_end_sum["expected_net_gp_per_casket"]))

        st.divider()

        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Acquisition share of total time", f"{end_to_end_sum['acquisition_share_of_total_time'] * 100:.1f}%")
        b2.metric("Completion share of total time", f"{end_to_end_sum['completion_share_of_total_time'] * 100:.1f}%")
        b3.metric("Current bottleneck", end_to_end_sum["bottleneck"])
        b4.metric("Time remaining (total)", fmt_hours_minutes(end_to_end_sum["time_remaining_total_s"]))

        st.divider()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("GP cost remaining", human_gp(end_to_end_sum["gp_cost_remaining"]))
        c2.metric("Expected alch remaining", human_gp(end_to_end_sum["expected_alch_remaining"]))
        c3.metric("Expected net remaining", human_gp(end_to_end_sum["expected_net_remaining"]))
        c4.metric("Remaining caskets", int(end_to_end_sum["remaining_caskets"]))

        st.divider()
        st.subheader("Charts")
        st.plotly_chart(build_end_to_end_stacked_time_chart(end_to_end_sum), use_container_width=True)
        st.plotly_chart(build_end_to_end_cph_chart(end_to_end_trend_df), use_container_width=True)
        st.plotly_chart(build_end_to_end_minutes_chart(end_to_end_trend_df), use_container_width=True)
