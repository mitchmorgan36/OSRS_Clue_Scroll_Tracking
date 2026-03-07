import os
import re
import math
from datetime import date, datetime
from typing import Optional, Dict, Any

import pandas as pd
import streamlit as st

# ----------------------------
# Config
# ----------------------------
st.set_page_config(page_title="Hard Clue Dashboard", layout="wide")

DATA_DIR = "data"
ACQ_CSV = os.path.join(DATA_DIR, "hard_clue_trips.csv")
COMP_CSV = os.path.join(DATA_DIR, "hard_clue_completion.csv")

GOAL_CASKETS = 650  # treated as target hard caskets / hard clues
DEFAULT_CLUES_PER_TRIP = 5

PRICE_BLOOD = 400
PRICE_DEATH = 200
DEATHS_PER_BLOOD = 2  # Ice Barrage ratio (deaths = 2*bloods)

AVG_REWARD_ROLLS_PER_CASKET = 5
EXPECTED_ALCH_GP_PER_CASKET = 54244.076180305085  # ~54.244k, derived from your HTML once


# ----------------------------
# UI tightening (sidebar spacing)
# ----------------------------
st.markdown(
    """
<style>
/* Tighten sidebar spacing */
section[data-testid="stSidebar"] .stMarkdown, 
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stTextInput,
section[data-testid="stSidebar"] .stNumberInput,
section[data-testid="stSidebar"] .stDateInput,
section[data-testid="stSidebar"] .stButton {
  margin-bottom: 0.35rem !important;
}
section[data-testid="stSidebar"] hr {
  margin: 0.6rem 0 !important;
}
/* Slightly reduce overall padding in sidebar */
section[data-testid="stSidebar"] > div {
  padding-top: 0.75rem !important;
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
    total_seconds = int(round(float(total_seconds)))
    if total_seconds < 0:
        total_seconds = 0
    hours = total_seconds // 3600
    mins = (total_seconds % 3600) // 60
    return f"{hours}h {mins:02d}m"


def seconds_to_hhmm(total_seconds: float) -> str:
    total_seconds = int(round(float(total_seconds)))
    if total_seconds < 0:
        total_seconds = 0
    hh = total_seconds // 3600
    mm = (total_seconds % 3600) // 60
    return f"{hh:d}:{mm:02d}"


def parse_playtime_hhmm(s: str) -> int:
    """
    Parse HH.mm (hours.minutes) OR HH:MM. Minutes must be 0-59.
    Example: 1.25 == 1h25m
    """
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
    except Exception:
        raise ValueError("Hours and minutes must be whole numbers.")

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
    if "log_date" in df.columns:
        df["log_date"] = pd.to_datetime(df["log_date"]).dt.date
    return df


def append_row(path: str, columns: list, row: Dict[str, Any]) -> None:
    ensure_data_dir()
    df = load_df(path, columns)
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(path, index=False)


def rolling_mean(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=1).mean()


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
]


# ----------------------------
# Session State (robust, no surprise resets)
# ----------------------------
def ss_init() -> None:
    # System clocks for acquisition and completion
    st.session_state.setdefault("acq_start_system", None)
    st.session_state.setdefault("acq_end_system", None)
    st.session_state.setdefault("comp_start_system", None)
    st.session_state.setdefault("comp_end_system", None)

    # Widget keys (acquisition)
    st.session_state.setdefault("w_acq_date", date.today())
    st.session_state.setdefault("w_acq_start_play", "")
    st.session_state.setdefault("w_acq_end_play", "")
    st.session_state.setdefault("w_acq_start_blood", None)
    st.session_state.setdefault("w_acq_end_blood", None)
    st.session_state.setdefault("w_acq_clues", DEFAULT_CLUES_PER_TRIP)

    # Widget keys (completion)
    st.session_state.setdefault("w_comp_date", date.today())
    st.session_state.setdefault("w_comp_start_play", "")
    st.session_state.setdefault("w_comp_end_play", "")
    st.session_state.setdefault("w_comp_completed", 10)

    # Pending apply mechanism (only used after Save to carry-forward/clear)
    st.session_state.setdefault("pending_apply", False)
    st.session_state.setdefault("pending", {})


def apply_pending_before_widgets() -> None:
    """Apply queued widget-key changes before widgets instantiate (safe)."""
    if st.session_state.get("pending_apply") and isinstance(st.session_state.get("pending"), dict):
        pend = st.session_state["pending"]
        for k, v in pend.items():
            st.session_state[k] = v
        st.session_state["pending"] = {}
        st.session_state["pending_apply"] = False


ss_init()
apply_pending_before_widgets()


# ----------------------------
# Compute summaries
# ----------------------------
def summarize_acq(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {}
    total_trips = len(df)
    total_clues = int(df["clues"].sum())
    total_seconds = float(df["duration_seconds"].sum())
    total_gp = float(df["gp_cost"].sum())

    avg_seconds_per_trip = float(df["duration_seconds"].mean())
    avg_seconds_per_clue = total_seconds / total_clues if total_clues > 0 else 0.0
    avg_gp_per_clue = total_gp / total_clues if total_clues > 0 else 0.0

    total_hours = total_seconds / 3600 if total_seconds > 0 else 0.0
    clues_per_hour = (total_clues / total_hours) if total_hours > 0 else 0.0
    gp_per_hour = (total_gp / total_hours) if total_hours > 0 else 0.0

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
    total_sessions = len(df)
    total_completed = int(df["clues_completed"].sum())
    total_seconds = float(df["duration_seconds"].sum())

    avg_seconds_per_session = float(df["duration_seconds"].mean())
    avg_seconds_per_clue = total_seconds / total_completed if total_completed > 0 else 0.0

    total_hours = total_seconds / 3600 if total_seconds > 0 else 0.0
    clues_per_hour = (total_completed / total_hours) if total_hours > 0 else 0.0

    remaining = max(0, GOAL_CASKETS - total_completed)
    proj_seconds_remaining = remaining * avg_seconds_per_clue

    return {
        "total_sessions": total_sessions,
        "total_completed": total_completed,
        "avg_time_session_s": avg_seconds_per_session,
        "avg_time_clue_s": avg_seconds_per_clue,
        "clues_per_hour": clues_per_hour,
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

# Progress bar (goal)
acq_logged = int(acq_sum.get("total_clues", 0))
progress = min(1.0, acq_logged / GOAL_CASKETS) if GOAL_CASKETS > 0 else 0.0
st.progress(progress, text=f"Progress to {GOAL_CASKETS} caskets: {acq_logged} / {GOAL_CASKETS}")


# ----------------------------
# Sidebar: Acquisition logger
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

    st.number_input("Start bloods", min_value=0, step=1, value=None, key="w_acq_start_blood")
    st.number_input("End bloods", min_value=0, step=1, value=None, key="w_acq_end_blood")
    st.number_input("Clues obtained", min_value=1, step=1, key="w_acq_clues")

    st.caption("Duration uses playtime if both are entered; otherwise uses system Start/End.")

    def save_acq():
        df = load_df(ACQ_CSV, ACQ_COLS)

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

        # duration via playtime if present
        dur_play = None
        if start_play and end_play:
            sp = parse_playtime_hhmm(start_play)
            ep = parse_playtime_hhmm(end_play)
            d = ep - sp
            if d <= 0:
                raise ValueError("End playtime must be greater than start playtime.")
            dur_play = int(d)

        # duration via system if present
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

        next_id = int(df["trip_id"].max() + 1) if not df.empty else 1

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

        # carry-forward / clear widget state immediately
        st.session_state["w_acq_start_blood"] = end_blood
        st.session_state["w_acq_end_blood"] = None
        st.session_state["w_acq_end_play"] = ""
        if end_play:
            st.session_state["w_acq_start_play"] = end_play

        # system carry-forward
        if ee:
            st.session_state["acq_start_system"] = ee
        st.session_state["acq_end_system"] = None

        st.rerun()

    if st.button("Save Acquisition Trip", type="primary", use_container_width=True):
        try:
            save_acq()
            st.success("Saved.")
        except Exception as ex:
            st.error(str(ex))

    st.divider()

    # ----------------------------
    # Sidebar: Completion logger
    # ----------------------------
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

    st.number_input("Clues completed", min_value=1, step=1, key="w_comp_completed")

    st.caption("Duration uses playtime if both are entered; otherwise uses system Start/End.")

    def save_comp():
        df = load_df(COMP_CSV, COMP_COLS)

        log_date = st.session_state["w_comp_date"]
        start_play = str(st.session_state["w_comp_start_play"]).strip()
        end_play = str(st.session_state["w_comp_end_play"]).strip()
        completed = int(st.session_state["w_comp_completed"])

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

        next_id = int(df["session_id"].max() + 1) if not df.empty else 1

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
        }

        append_row(COMP_CSV, COMP_COLS, row)

        pending = {
            "w_comp_end_play": "",
        }
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


# Refresh data after possible saves
acq_df = load_df(ACQ_CSV, ACQ_COLS)
comp_df = load_df(COMP_CSV, COMP_COLS)
acq_sum = summarize_acq(acq_df)
comp_sum = summarize_comp(comp_df)

# ----------------------------
# Tabs
# ----------------------------
tab_acq, tab_comp, tab_combo = st.tabs(["Acquisition", "Completion", "End-to-end"])

# ----------------------------
# Acquisition tab
# ----------------------------
with tab_acq:
    if acq_df.empty:
        st.info("No acquisition trips logged yet.")
    else:
        total = acq_sum["total_clues"]
        remaining = acq_sum["remaining"]

        # KPI row
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Trips", int(acq_sum["total_trips"]))
        k2.metric("Clues logged", int(total))
        k3.metric("Avg time / trip", seconds_to_hhmm(acq_sum["avg_time_trip_s"]))
        k4.metric("Avg cost / casket", human_gp(acq_sum["avg_gp_per_clue"]))
        k5.metric("Clues / hour", f"{acq_sum['clues_per_hour']:.2f}")

        st.divider()

        # Money row (formatted)
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Expected alch / casket", human_gp(EXPECTED_ALCH_GP_PER_CASKET))
        net_per = EXPECTED_ALCH_GP_PER_CASKET - acq_sum["avg_gp_per_clue"]
        m2.metric("Net gp / casket", human_gp(net_per))
        m3.metric("GP cost remaining", human_gp(acq_sum["proj_gp_remaining"]))
        m4.metric("Expected alch remaining", human_gp(EXPECTED_ALCH_GP_PER_CASKET * remaining))
        m5.metric("Expected net remaining", human_gp(net_per * remaining))

        st.divider()

        # Time remaining with clearer label
        t1, t2, t3 = st.columns(3)
        t1.metric("Time remaining (acquire)", fmt_hours_minutes(acq_sum["proj_time_remaining_s"]))
        t2.metric("Remaining caskets", int(remaining))
        t3.metric("Trips remaining (rough)", math.ceil(remaining / DEFAULT_CLUES_PER_TRIP) if DEFAULT_CLUES_PER_TRIP else 0)

        st.divider()

        # Table
        disp = acq_df.copy()
        disp["duration"] = disp["duration_seconds"].apply(seconds_to_hhmm)
        disp["gp_cost"] = disp["gp_cost"].round(0).astype(int)
        disp["gp_per_clue"] = disp["gp_per_clue"].round(1)
        disp["clues_per_hour"] = disp["clues_per_hour"].round(2)

        st.subheader("Trip Log")
        st.dataframe(
            disp[
                ["trip_id", "log_date", "duration", "clues", "bloods_used", "deaths_used", "gp_cost", "gp_per_clue", "clues_per_hour"]
            ].sort_values("trip_id", ascending=False),
            use_container_width=True,
            height=350,
        )

        st.divider()
        st.subheader("Charts")

        # Build chart data
        d = acq_df.sort_values("trip_id").copy()
        d["duration_min"] = d["duration_seconds"] / 60.0

        cA, cB = st.columns(2)

        with cA:
            st.caption("Duration per trip (minutes)")
            st.line_chart(d.set_index("trip_id")[["duration_min"]])

            st.caption("Bloods used per trip")
            st.line_chart(d.set_index("trip_id")[["bloods_used"]])

        with cB:
            st.caption("Duration vs Bloods (scatter)")
            scatter = d[["duration_min", "bloods_used"]].copy()
            st.scatter_chart(scatter, x="duration_min", y="bloods_used")

            st.caption("Trip duration distribution (minutes)")
            # simple histogram using pandas cut + line_chart
            bins = pd.cut(d["duration_min"], bins=12)
            hist = bins.value_counts().sort_index()
            hist_df = pd.DataFrame({"bin": hist.index.astype(str), "count": hist.values}).set_index("bin")
            st.bar_chart(hist_df)

# ----------------------------
# Completion tab
# ----------------------------
with tab_comp:
    if comp_df.empty:
        st.info("No completion sessions logged yet.")
    else:
        total_completed = int(comp_sum["total_completed"])
        remaining = comp_sum["remaining"]

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Sessions", int(comp_sum["total_sessions"]))
        k2.metric("Clues completed logged", total_completed)
        k3.metric("Avg time / clue", fmt_hours_minutes(comp_sum["avg_time_clue_s"]))
        k4.metric("Clues / hour", f"{comp_sum['clues_per_hour']:.2f}")

        st.divider()

        t1, t2 = st.columns(2)
        t1.metric("Time remaining (complete)", fmt_hours_minutes(comp_sum["proj_time_remaining_s"]))
        t2.metric("Remaining to 650 (complete)", int(max(0, GOAL_CASKETS - total_completed)))

        st.divider()

        disp = comp_df.copy()
        disp["duration"] = disp["duration_seconds"].apply(seconds_to_hhmm)
        disp["clues_per_hour"] = disp["clues_per_hour"].round(2)

        st.subheader("Completion Log")
        st.dataframe(
            disp[["session_id", "log_date", "duration", "clues_completed", "clues_per_hour"]].sort_values("session_id", ascending=False),
            use_container_width=True,
            height=350,
        )

        st.divider()
        st.subheader("Charts")
        d = comp_df.sort_values("session_id").copy()
        d["duration_min"] = d["duration_seconds"] / 60.0

        c1, c2 = st.columns(2)
        with c1:
            st.caption("Duration per session (minutes)")
            st.line_chart(d.set_index("session_id")[["duration_min"]])
        with c2:
            st.caption("Clues completed per session")
            st.line_chart(d.set_index("session_id")[["clues_completed"]])

# ----------------------------
# End-to-end tab
# ----------------------------
with tab_combo:
    st.subheader("End-to-end estimates (Acquire + Complete)")

    if acq_df.empty or comp_df.empty:
        st.info("Log at least one acquisition trip and one completion session to get end-to-end averages.")
    else:
        acq_min_per = acq_sum["avg_time_clue_s"] / 60.0
        comp_min_per = comp_sum["avg_time_clue_s"] / 60.0
        total_min_per = acq_min_per + comp_min_per

        remaining = max(0, GOAL_CASKETS - int(acq_sum["total_clues"]))
        # Using acquisition logged as the “progress” source to goal.
        # (If you want completion to define progress instead, we can flip it.)
        remaining_seconds_total = remaining * (acq_sum["avg_time_clue_s"] + comp_sum["avg_time_clue_s"])

        a, b, c, d = st.columns(4)
        a.metric("Acquire min / casket", f"{acq_min_per:.2f}")
        b.metric("Complete min / casket", f"{comp_min_per:.2f}")
        c.metric("Total min / casket", f"{total_min_per:.2f}")
        d.metric("Time remaining (total)", fmt_hours_minutes(remaining_seconds_total))

        st.divider()
        st.caption(
            "This combines your observed average acquire time per clue with your observed average completion time per clue. "
            "Progress-to-goal uses acquisition logged clues."
        )