from datetime import datetime
from typing import Any, Dict

import pandas as pd
import streamlit as st

from . import data
from .config import DEFAULT_CLUES_PER_TRIP, GOAL_CASKETS
from .formatting import (
    clamp_nonnegative_int,
    clamp_positive_int,
    normalize_draft_date,
    normalize_draft_datetime,
    normalize_draft_text,
    now_local,
    today_local,
    parse_optional_nonnegative_int,
)
from .schemas import (
    ACQ_LOGGER_STATE_COLS,
    ACQ_LOGGER_STATE_SHEET,
    COMP_LOGGER_STATE_COLS,
    COMP_LOGGER_STATE_SHEET,
    GOAL_PROGRESS_STATE_COLS,
    GOAL_PROGRESS_STATE_SHEET,
    GOAL_SETTINGS_COLS,
    GOAL_SETTINGS_SHEET,
)

def load_acq_logger_state() -> tuple[Dict[str, Any], str | None]:
    try:
        df = data.read_sheet_df(ACQ_LOGGER_STATE_SHEET, list(ACQ_LOGGER_STATE_COLS))
    except Exception as ex:
        return {}, f"Could not load acquisition draft from Google Sheets: {ex}"
    if df.empty:
        return {}, None
    row = df.iloc[-1]
    return {
        "log_date": normalize_draft_date(row.get("log_date")),
        "start_playtime": normalize_draft_text(row.get("start_playtime")),
        "end_playtime": normalize_draft_text(row.get("end_playtime")),
        "start_bloods": parse_optional_nonnegative_int(row.get("start_bloods")),
        "end_bloods": parse_optional_nonnegative_int(row.get("end_bloods")),
        "clues": clamp_positive_int(row.get("clues"), default=DEFAULT_CLUES_PER_TRIP),
        "notes": normalize_draft_text(row.get("notes")),
        "start_system": normalize_draft_datetime(row.get("start_system")),
        "end_system": normalize_draft_datetime(row.get("end_system")),
    }, None


def load_comp_logger_state() -> tuple[Dict[str, Any], str | None]:
    try:
        df = data.read_sheet_df(COMP_LOGGER_STATE_SHEET, list(COMP_LOGGER_STATE_COLS))
    except Exception as ex:
        return {}, f"Could not load completion draft from Google Sheets: {ex}"
    if df.empty:
        return {}, None
    row = df.iloc[-1]
    return {
        "log_date": normalize_draft_date(row.get("log_date")),
        "start_playtime": normalize_draft_text(row.get("start_playtime")),
        "end_playtime": normalize_draft_text(row.get("end_playtime")),
        "clues_completed": clamp_positive_int(row.get("clues_completed"), default=10),
        "notes": normalize_draft_text(row.get("notes")),
        "start_system": normalize_draft_datetime(row.get("start_system")),
        "end_system": normalize_draft_datetime(row.get("end_system")),
    }, None


def save_acq_logger_state(
    *,
    log_date: Any,
    start_playtime: Any,
    end_playtime: Any,
    start_bloods: Any,
    end_bloods: Any,
    clues: Any,
    notes: Any,
    start_system: Any,
    end_system: Any,
) -> None:
    normalized_log_date = normalize_draft_date(log_date, default=today_local()) or today_local()
    normalized_start_system = normalize_draft_datetime(start_system)
    normalized_end_system = normalize_draft_datetime(end_system)
    payload = {
        "log_date": normalized_log_date.isoformat(),
        "start_playtime": normalize_draft_text(start_playtime),
        "end_playtime": normalize_draft_text(end_playtime),
        "start_bloods": parse_optional_nonnegative_int(start_bloods),
        "end_bloods": parse_optional_nonnegative_int(end_bloods),
        "clues": clamp_positive_int(clues, default=DEFAULT_CLUES_PER_TRIP),
        "notes": normalize_draft_text(notes),
        "start_system": normalized_start_system.isoformat() if normalized_start_system else None,
        "end_system": normalized_end_system.isoformat() if normalized_end_system else None,
        "updated_at": now_local().isoformat(),
    }
    state_df = pd.DataFrame([payload], columns=list(ACQ_LOGGER_STATE_COLS))
    data.replace_sheet(ACQ_LOGGER_STATE_SHEET, list(ACQ_LOGGER_STATE_COLS), state_df)


def save_comp_logger_state(
    *,
    log_date: Any,
    start_playtime: Any,
    end_playtime: Any,
    clues_completed: Any,
    notes: Any,
    start_system: Any,
    end_system: Any,
) -> None:
    normalized_log_date = normalize_draft_date(log_date, default=today_local()) or today_local()
    normalized_start_system = normalize_draft_datetime(start_system)
    normalized_end_system = normalize_draft_datetime(end_system)
    payload = {
        "log_date": normalized_log_date.isoformat(),
        "start_playtime": normalize_draft_text(start_playtime),
        "end_playtime": normalize_draft_text(end_playtime),
        "clues_completed": clamp_positive_int(clues_completed, default=10),
        "notes": normalize_draft_text(notes),
        "start_system": normalized_start_system.isoformat() if normalized_start_system else None,
        "end_system": normalized_end_system.isoformat() if normalized_end_system else None,
        "updated_at": now_local().isoformat(),
    }
    state_df = pd.DataFrame([payload], columns=list(COMP_LOGGER_STATE_COLS))
    data.replace_sheet(COMP_LOGGER_STATE_SHEET, list(COMP_LOGGER_STATE_COLS), state_df)


def load_goal_progress_state() -> Dict[str, Any]:
    try:
        df = data.read_sheet_df(GOAL_PROGRESS_STATE_SHEET, list(GOAL_PROGRESS_STATE_COLS))
    except Exception:
        return {}
    if df.empty:
        return {}
    row = df.iloc[-1]
    return {
        "start_acq_total": clamp_nonnegative_int(row.get("start_acq_total"), default=0),
        "start_comp_total": clamp_nonnegative_int(row.get("start_comp_total"), default=0),
        "start_set_at": str(row.get("start_set_at") or "").strip() or None,
    }


def save_goal_progress_state(start_acq_total: int, start_comp_total: int, start_set_at: datetime | None) -> None:
    payload = {
        "start_acq_total": clamp_nonnegative_int(start_acq_total, default=0),
        "start_comp_total": clamp_nonnegative_int(start_comp_total, default=0),
        "start_set_at": start_set_at.isoformat() if start_set_at else None,
    }
    state_df = pd.DataFrame([payload], columns=list(GOAL_PROGRESS_STATE_COLS))
    data.replace_sheet(GOAL_PROGRESS_STATE_SHEET, list(GOAL_PROGRESS_STATE_COLS), state_df)


def normalize_goal_caskets(value: Any) -> int:
    return max(1, clamp_nonnegative_int(value, default=GOAL_CASKETS))


def load_goal_settings_state() -> Dict[str, Any]:
    try:
        df = data.read_sheet_df(GOAL_SETTINGS_SHEET, list(GOAL_SETTINGS_COLS))
    except Exception:
        return {}
    if df.empty:
        return {}
    row = df.iloc[-1]
    return {
        "goal_caskets": normalize_goal_caskets(row.get("goal_caskets")),
    }


def save_goal_settings_state(goal_caskets: int) -> None:
    payload = {
        "goal_caskets": normalize_goal_caskets(goal_caskets),
    }
    state_df = pd.DataFrame([payload], columns=list(GOAL_SETTINGS_COLS))
    data.replace_sheet(GOAL_SETTINGS_SHEET, list(GOAL_SETTINGS_COLS), state_df)


def ss_init() -> None:
    goal_progress_state = load_goal_progress_state()
    goal_settings_state = load_goal_settings_state()
    acq_logger_state, acq_logger_error = load_acq_logger_state()
    comp_logger_state, comp_logger_error = load_comp_logger_state()

    st.session_state.setdefault("acq_draft_error", acq_logger_error)
    st.session_state.setdefault("comp_draft_error", comp_logger_error)
    st.session_state.setdefault("acq_start_system", acq_logger_state.get("start_system"))
    st.session_state.setdefault("acq_end_system", acq_logger_state.get("end_system"))
    st.session_state.setdefault("comp_start_system", comp_logger_state.get("start_system"))
    st.session_state.setdefault("comp_end_system", comp_logger_state.get("end_system"))

    st.session_state.setdefault("w_acq_date", acq_logger_state.get("log_date") or today_local())
    st.session_state.setdefault("w_acq_start_play", acq_logger_state.get("start_playtime", ""))
    st.session_state.setdefault("w_acq_end_play", acq_logger_state.get("end_playtime", ""))
    st.session_state.setdefault("w_acq_start_blood", acq_logger_state.get("start_bloods"))
    st.session_state.setdefault("w_acq_end_blood", acq_logger_state.get("end_bloods"))
    st.session_state.setdefault("w_acq_clues", acq_logger_state.get("clues", DEFAULT_CLUES_PER_TRIP))
    st.session_state.setdefault("w_acq_notes", acq_logger_state.get("notes", ""))

    st.session_state.setdefault("w_comp_date", comp_logger_state.get("log_date") or today_local())
    st.session_state.setdefault("w_comp_start_play", comp_logger_state.get("start_playtime", ""))
    st.session_state.setdefault("w_comp_end_play", comp_logger_state.get("end_playtime", ""))
    st.session_state.setdefault("w_comp_completed", comp_logger_state.get("clues_completed", 10))
    st.session_state.setdefault("w_comp_notes", comp_logger_state.get("notes", ""))

    st.session_state.setdefault("pending_apply", False)
    st.session_state.setdefault("pending", {})
    st.session_state.setdefault("goal_caskets", goal_settings_state.get("goal_caskets", GOAL_CASKETS))
    st.session_state.setdefault("goal_progress_start_acq_total", goal_progress_state.get("start_acq_total"))
    st.session_state.setdefault("goal_progress_start_comp_total", goal_progress_state.get("start_comp_total"))
    st.session_state.setdefault("goal_progress_start_set_at", goal_progress_state.get("start_set_at"))


def apply_pending_before_widgets() -> None:
    if st.session_state.get("pending_apply") and isinstance(st.session_state.get("pending"), dict):
        for k, v in st.session_state["pending"].items():
            st.session_state[k] = v
        st.session_state["pending"] = {}
        st.session_state["pending_apply"] = False


def queue_pending_updates(updates: Dict[str, Any]) -> None:
    pending = st.session_state.get("pending")
    merged = dict(pending) if isinstance(pending, dict) else {}
    merged.update(updates)
    st.session_state["pending"] = merged
    st.session_state["pending_apply"] = True


def persist_acq_logger_state_values(
    *,
    log_date: Any,
    start_playtime: Any,
    end_playtime: Any,
    start_bloods: Any,
    end_bloods: Any,
    clues: Any,
    notes: Any,
    start_system: Any,
    end_system: Any,
) -> None:
    try:
        save_acq_logger_state(
            log_date=log_date,
            start_playtime=start_playtime,
            end_playtime=end_playtime,
            start_bloods=start_bloods,
            end_bloods=end_bloods,
            clues=clues,
            notes=notes,
            start_system=start_system,
            end_system=end_system,
        )
        st.session_state["acq_draft_error"] = None
    except Exception as ex:
        st.session_state["acq_draft_error"] = f"Could not sync acquisition draft to Google Sheets: {ex}"


def persist_comp_logger_state_values(
    *,
    log_date: Any,
    start_playtime: Any,
    end_playtime: Any,
    clues_completed: Any,
    notes: Any,
    start_system: Any,
    end_system: Any,
) -> None:
    try:
        save_comp_logger_state(
            log_date=log_date,
            start_playtime=start_playtime,
            end_playtime=end_playtime,
            clues_completed=clues_completed,
            notes=notes,
            start_system=start_system,
            end_system=end_system,
        )
        st.session_state["comp_draft_error"] = None
    except Exception as ex:
        st.session_state["comp_draft_error"] = f"Could not sync completion draft to Google Sheets: {ex}"


def persist_acq_logger_state() -> None:
    persist_acq_logger_state_values(
        log_date=st.session_state.get("w_acq_date"),
        start_playtime=st.session_state.get("w_acq_start_play"),
        end_playtime=st.session_state.get("w_acq_end_play"),
        start_bloods=st.session_state.get("w_acq_start_blood"),
        end_bloods=st.session_state.get("w_acq_end_blood"),
        clues=st.session_state.get("w_acq_clues"),
        notes=st.session_state.get("w_acq_notes"),
        start_system=st.session_state.get("acq_start_system"),
        end_system=st.session_state.get("acq_end_system"),
    )


def persist_comp_logger_state() -> None:
    persist_comp_logger_state_values(
        log_date=st.session_state.get("w_comp_date"),
        start_playtime=st.session_state.get("w_comp_start_play"),
        end_playtime=st.session_state.get("w_comp_end_play"),
        clues_completed=st.session_state.get("w_comp_completed"),
        notes=st.session_state.get("w_comp_notes"),
        start_system=st.session_state.get("comp_start_system"),
        end_system=st.session_state.get("comp_end_system"),
    )
