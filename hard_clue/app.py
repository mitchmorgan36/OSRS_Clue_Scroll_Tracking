from types import SimpleNamespace

import pandas as pd
import streamlit as st

from . import data, state, ui
from .config import (
    END_TO_END_RECENT_ACQ_EWMA_SPAN,
    END_TO_END_RECENT_COMP_EWMA_SPAN,
    EXPECTED_ALCH_GP_PER_CASKET,
    GOAL_CASKETS,
)
from .formatting import parse_iso_datetime
from .metrics import (
    ensure_adjusted_end_to_end_columns,
    normalized_progress_baseline,
    prepare_acq_metrics,
    prepare_comp_metrics,
    summarize_acq,
    summarize_comp,
    summarize_end_to_end,
    build_end_to_end_trend_df,
)
from .schemas import ACQ_COLS, ACQ_SHEET, COMP_COLS, COMP_SHEET


def run_app() -> None:
    st.set_page_config(page_title="Hard Clue Dashboard", layout="wide")
    ui.inject_styles()

    state.ss_init()
    state.apply_pending_before_widgets()
    goal_caskets = state.normalize_goal_caskets(st.session_state.get("goal_caskets", GOAL_CASKETS))
    st.session_state["goal_caskets"] = goal_caskets

    session_cache_key = data.get_session_cache_key()

    acq_df = data.load_df(ACQ_SHEET, ACQ_COLS, session_cache_key)
    comp_df = data.load_df(COMP_SHEET, COMP_COLS, session_cache_key)
    acq_sum = summarize_acq(acq_df, goal_caskets)
    comp_sum = summarize_comp(comp_df, goal_caskets)
    acq_metrics_df = prepare_acq_metrics(acq_df)
    comp_metrics_df = prepare_comp_metrics(comp_df)
    end_to_end_sum = summarize_end_to_end(acq_sum, comp_sum, goal_caskets)
    end_to_end_trend_df = build_end_to_end_trend_df(
        acq_df,
        comp_df,
        END_TO_END_RECENT_ACQ_EWMA_SPAN,
        END_TO_END_RECENT_COMP_EWMA_SPAN,
    )
    end_to_end_trend_df = ensure_adjusted_end_to_end_columns(end_to_end_trend_df)

    running_acq_total = int(acq_sum.get("total_clues", 0))
    running_comp_total = int(comp_sum.get("total_completed", 0))

    progress_start_acq_total = normalized_progress_baseline(
        st.session_state.get("goal_progress_start_acq_total"),
        running_acq_total,
    )
    progress_start_comp_total = normalized_progress_baseline(
        st.session_state.get("goal_progress_start_comp_total"),
        running_comp_total,
    )
    progress_start_set_at = parse_iso_datetime(st.session_state.get("goal_progress_start_set_at"))

    st.session_state["goal_progress_start_acq_total"] = progress_start_acq_total
    st.session_state["goal_progress_start_comp_total"] = progress_start_comp_total
    st.session_state["goal_progress_start_set_at"] = progress_start_set_at.isoformat() if progress_start_set_at else None

    acq_since_progress_start = max(0, running_acq_total - progress_start_acq_total)
    comp_since_progress_start = max(0, running_comp_total - progress_start_comp_total)

    goal_progress_completed = comp_since_progress_start
    goal_progress_remaining = max(0, goal_caskets - goal_progress_completed)
    goal_progress = min(1.0, goal_progress_completed / goal_caskets) if goal_caskets > 0 else 0.0
    clues_on_ground_since_progress_start = max(0, acq_since_progress_start - comp_since_progress_start)
    stacked_clues_completion_time_s = (
        clues_on_ground_since_progress_start * float(comp_sum.get("avg_time_casket_s", 0.0) or 0.0)
    )
    clues_still_to_acquire_for_goal = max(0, goal_progress_remaining - clues_on_ground_since_progress_start)

    acq_goal_remaining = max(0, goal_caskets - acq_since_progress_start)
    comp_goal_remaining = max(0, goal_caskets - comp_since_progress_start)
    acq_goal_time_remaining_s = acq_goal_remaining * float(acq_sum.get("avg_time_clue_s", 0.0) or 0.0)
    comp_goal_time_remaining_s = comp_goal_remaining * float(comp_sum.get("avg_time_casket_s", 0.0) or 0.0)
    combo_goal_remaining = comp_goal_remaining
    combo_goal_time_remaining_s = combo_goal_remaining * (
        float(acq_sum.get("avg_time_clue_s", 0.0) or 0.0)
        + float(comp_sum.get("avg_time_casket_s", 0.0) or 0.0)
    )
    combo_expected_alch_gp_remaining = combo_goal_remaining * EXPECTED_ALCH_GP_PER_CASKET
    combo_projected_net_acquisition_gp_remaining = float("nan")
    combo_expected_net_remaining = float("nan")
    if acq_sum:
        net_gp_per_clue_on_acquisition = acq_sum.get("net_gp_per_clue_acquired", float("nan"))
        if not pd.isna(net_gp_per_clue_on_acquisition):
            combo_projected_net_acquisition_gp_remaining = float(net_gp_per_clue_on_acquisition) * combo_goal_remaining
            combo_expected_net_remaining = (
                combo_projected_net_acquisition_gp_remaining
                + (combo_goal_remaining * EXPECTED_ALCH_GP_PER_CASKET)
            )

    ctx = SimpleNamespace(**locals())
    ui.render_header(ctx)
    ui.render_sidebar(ctx)
    ui.render_tabs(ctx)
