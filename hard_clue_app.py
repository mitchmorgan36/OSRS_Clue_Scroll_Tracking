import os
import math
from datetime import date, datetime
from typing import Dict, Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

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


# ----------------------------
# UI tightening
# ----------------------------
st.markdown(
    """
<style>
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stTextInput,
section[data-testid="stSidebar"] .stNumberInput,
section[data-testid="stSidebar"] .stDateInput,
section[data-testid="stSidebar"] .stTextArea,
section[data-testid="stSidebar"] .stButton {
  margin-bottom: 0.30rem !important;
}
section[data-testid="stSidebar"] hr {
  margin: 0.45rem 0 !important;
}
section[data-testid="stSidebar"] > div {
  padding-top: 0.65rem !important;
}
div[data-testid="metric-container"] {
  padding: 0.25rem 0.45rem !important;
}
div[data-testid="metric-container"] > div {
  gap: 0.05rem !important;
}
div[data-testid="metric-container"] label {
  margin-bottom: 0 !important;
}
hr {
  margin: 0.35rem 0 0.45rem 0 !important;
}
.block-container {
  padding-top: 1.2rem !important;
}
</style>
""",
    unsafe_allow_html=True,
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



def load_df(path: str, columns: list) -> pd.DataFrame:
    ensure_data_dir()
    if not os.path.exists(path):
        return pd.DataFrame(columns=columns)
    df = pd.read_csv(path)
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    if "log_date" in df.columns:
        df["log_date"] = pd.to_datetime(df["log_date"], errors="coerce").dt.date
    return df[columns]



def append_row(path: str, columns: list, row: Dict[str, Any]) -> None:
    ensure_data_dir()
    df = load_df(path, columns)
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

    if acq.empty or comp.empty:
        fig.update_layout(
            **make_line_layout(
                "End-to-end caskets per hour",
                "Date",
                "Caskets per hour",
                height=360,
            )
        )
        return fig

    acq["log_date"] = pd.to_datetime(acq["log_date"], errors="coerce")
    comp["log_date"] = pd.to_datetime(comp["log_date"], errors="coerce")

    acq = acq.dropna(subset=["log_date"])
    comp = comp.dropna(subset=["log_date"])

    acq = acq[acq["clues"] > 0].copy()
    comp = comp[comp["clues_completed"] > 0].copy()

    acq_daily = (
        acq.groupby(acq["log_date"].dt.date, as_index=False)
        .agg(acq_seconds=("duration_seconds", "sum"), acq_caskets=("clues", "sum"))
        .rename(columns={"log_date": "date"})
    )

    comp_daily = (
        comp.groupby(comp["log_date"].dt.date, as_index=False)
        .agg(comp_seconds=("duration_seconds", "sum"), comp_caskets=("clues_completed", "sum"))
        .rename(columns={"log_date": "date"})
    )

    d = pd.merge(acq_daily, comp_daily, on="date", how="outer").sort_values("date").fillna(0)

    d["cum_acq_seconds"] = d["acq_seconds"].cumsum()
    d["cum_acq_caskets"] = d["acq_caskets"].cumsum()
    d["cum_comp_seconds"] = d["comp_seconds"].cumsum()
    d["cum_comp_caskets"] = d["comp_caskets"].cumsum()

    d = d[(d["cum_acq_caskets"] > 0) & (d["cum_comp_caskets"] > 0)].copy()

    if d.empty:
        fig.update_layout(
            **make_line_layout(
                "End-to-end caskets per hour",
                "Date",
                "Caskets per hour",
                height=360,
            )
        )
        return fig

    d["cum_acq_sec_per_casket"] = d["cum_acq_seconds"] / d["cum_acq_caskets"]
    d["cum_comp_sec_per_casket"] = d["cum_comp_seconds"] / d["cum_comp_caskets"]
    d["end_to_end_cph"] = 3600.0 / (d["cum_acq_sec_per_casket"] + d["cum_comp_sec_per_casket"])

    main_color = "#10b981"      # emerald
    avg_color = "#86efac"       # light green

    fig.add_trace(
        go.Scatter(
            x=d["date"],
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
            x=d["date"],
            y=[avg_val] * len(d),
            mode="lines",
            name="Average",
            line=dict(color=avg_color, width=2.5, dash="dash"),
            hovertemplate="Average: %{y:.2f}<extra></extra>",
        )
    )

    fig.update_layout(
        **make_line_layout(
            "End-to-end caskets per hour",
            "Date",
            "Caskets per hour",
            height=380,
        )
    )

    fig.update_layout(
        margin=dict(l=40, r=40, t=70, b=40),
        xaxis=dict(title="Date"),
    )

    return fig


# ----------------------------
# Data schemas
# ----------------------------
ACQ_COLS = [
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
]

COMP_COLS = [
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
]


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
    st.session_state.setdefault("w_acq_start_blood", 0)
    st.session_state.setdefault("w_acq_end_blood", 0)
    st.session_state.setdefault("w_acq_clues", DEFAULT_CLUES_PER_TRIP)

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
acq_df = load_df(ACQ_CSV, ACQ_COLS)
comp_df = load_df(COMP_CSV, COMP_COLS)
acq_sum = summarize_acq(acq_df)
comp_sum = summarize_comp(comp_df)


# ----------------------------
# Header
# ----------------------------
st.title("Hard Clue Dashboard")
acq_logged = int(acq_sum.get("total_clues", 0))
progress = min(1.0, acq_logged / GOAL_CASKETS) if GOAL_CASKETS > 0 else 0.0
st.progress(progress, text=f"Progress to {GOAL_CASKETS} caskets: {acq_logged} / {GOAL_CASKETS} ({progress * 100:.1f}%)")


# ----------------------------
# Sidebar
# ----------------------------
with st.sidebar:
    st.header("Acquisition Logger")
    st.date_input("Date", key="w_acq_date")
    colA, colB = st.columns(2)

    def acq_start_now():
        st.session_state["acq_start_system"] = datetime.now()
        st.session_state["acq_end_system"] = None

    def acq_end_now():
        st.session_state["acq_end_system"] = datetime.now()

    with colA:
        st.button("Start Now", on_click=acq_start_now, use_container_width=True)
    with colB:
        st.button("End Now", on_click=acq_end_now, use_container_width=True)

    s0 = st.session_state.get("acq_start_system")
    e0 = st.session_state.get("acq_end_system")
    st.caption(
        f"System start: **{s0.strftime('%Y-%m-%d %H:%M') if s0 else '—'}**  \n"
        f"System end: **{e0.strftime('%Y-%m-%d %H:%M') if e0 else '—'}**"
    )

    st.text_input("Start playtime (HH.mm)", key="w_acq_start_play", placeholder="e.g. 1.25")
    st.text_input("End playtime (HH.mm)", key="w_acq_end_play", placeholder="e.g. 2.10")
    st.number_input("Start bloods", min_value=0, step=1, key="w_acq_start_blood")
    st.number_input("End bloods", min_value=0, step=1, key="w_acq_end_blood")
    st.number_input("Clues obtained", min_value=1, step=1, key="w_acq_clues")
    st.caption("Duration uses playtime if both are entered; otherwise uses system Start/End.")

    def save_acq():
        df = load_df(ACQ_CSV, ACQ_COLS)
        log_date = st.session_state["w_acq_date"]
        start_play = str(st.session_state["w_acq_start_play"]).strip()
        end_play = str(st.session_state["w_acq_end_play"]).strip()
        start_blood = int(st.session_state["w_acq_start_blood"])
        end_blood = int(st.session_state["w_acq_end_blood"])
        clues = int(st.session_state["w_acq_clues"])

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
        next_id = int(pd.to_numeric(df["trip_id"], errors="coerce").max() + 1) if not df.empty and pd.to_numeric(df["trip_id"], errors="coerce").notna().any() else 1

        row = {
            "trip_id": next_id,
            "log_date": log_date.isoformat(),
            "start_playtime": start_play,
            "end_playtime": end_play,
            "duration_seconds_playtime": dur_play if dur_play is not None else "",
            "start_system": ss.isoformat(sep=" ") if ss else "",
            "end_system": ee.isoformat(sep=" ") if ee else "",
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
        }
        append_row(ACQ_CSV, ACQ_COLS, row)

        pending = {"w_acq_start_blood": end_blood, "w_acq_end_blood": 0, "w_acq_end_play": ""}
        if end_play:
            pending["w_acq_start_play"] = end_play
        if ee:
            st.session_state["acq_start_system"] = ee
        st.session_state["acq_end_system"] = None
        st.session_state["pending"] = pending
        st.session_state["pending_apply"] = True

    if st.button("Save Acquisition Trip", type="primary", use_container_width=True):
        try:
            save_acq()
            st.success("Saved.")
        except Exception as ex:
            st.error(str(ex))

    st.divider()
    st.header("Completion Logger")
    st.date_input("Date", key="w_comp_date")
    colC, colD = st.columns(2)

    def comp_start_now():
        st.session_state["comp_start_system"] = datetime.now()
        st.session_state["comp_end_system"] = None

    def comp_end_now():
        st.session_state["comp_end_system"] = datetime.now()

    with colC:
        st.button("Start Now", on_click=comp_start_now, use_container_width=True, key="btn_comp_start")
    with colD:
        st.button("End Now", on_click=comp_end_now, use_container_width=True, key="btn_comp_end")

    s1 = st.session_state.get("comp_start_system")
    e1 = st.session_state.get("comp_end_system")
    st.caption(
        f"System start: **{s1.strftime('%Y-%m-%d %H:%M') if s1 else '—'}**  \n"
        f"System end: **{e1.strftime('%Y-%m-%d %H:%M') if e1 else '—'}**"
    )

    st.text_input("Start playtime (HH.mm)", key="w_comp_start_play", placeholder="e.g. 12.40")
    st.text_input("End playtime (HH.mm)", key="w_comp_end_play", placeholder="e.g. 13.25")
    st.number_input("Caskets completed", min_value=1, step=1, key="w_comp_completed")
    st.text_area("Notes", key="w_comp_notes", placeholder="Optional notes for this completion session", height=90)
    st.caption("Duration uses playtime if both are entered; otherwise uses system Start/End.")

    def save_comp():
        df = load_df(COMP_CSV, COMP_COLS)
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
        next_id = int(numeric_ids.max() + 1) if not df.empty and numeric_ids.notna().any() else 1

        row = {
            "session_id": next_id,
            "log_date": log_date.isoformat(),
            "start_playtime": start_play,
            "end_playtime": end_play,
            "duration_seconds_playtime": dur_play if dur_play is not None else "",
            "start_system": ss.isoformat(sep=" ") if ss else "",
            "end_system": ee.isoformat(sep=" ") if ee else "",
            "duration_seconds_system": dur_sys if dur_sys is not None else "",
            "duration_seconds": int(dur),
            "clues_completed": int(completed),
            "clues_per_hour": clues_per_hour,
            "notes": notes,
        }
        append_row(COMP_CSV, COMP_COLS, row)

        pending = {"w_comp_end_play": "", "w_comp_notes": ""}
        if end_play:
            pending["w_comp_start_play"] = end_play
        if ee:
            st.session_state["comp_start_system"] = ee
        st.session_state["comp_end_system"] = None
        st.session_state["pending"] = pending
        st.session_state["pending_apply"] = True

    if st.button("Save Completion Session", type="primary", use_container_width=True):
        try:
            save_comp()
            st.success("Saved.")
        except Exception as ex:
            st.error(str(ex))


# Refresh after possible saves
acq_df = load_df(ACQ_CSV, ACQ_COLS)
comp_df = load_df(COMP_CSV, COMP_COLS)
acq_sum = summarize_acq(acq_df)
comp_sum = summarize_comp(comp_df)


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

        st.subheader("Trip Log")
        st.dataframe(
            disp[["trip_id", "log_date", "duration", "clues", "bloods_used", "deaths_used", "gp_cost", "gp_per_clue", "clues_per_hour"]]
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
