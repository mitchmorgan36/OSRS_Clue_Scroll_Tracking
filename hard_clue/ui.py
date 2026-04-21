import inspect
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
import streamlit as st

from . import state
from .charts import (
    build_acq_clues_per_hour_chart,
    build_acq_profitability_chart,
    build_completion_caskets_completed_chart,
    build_completion_caskets_per_hour_chart,
    build_end_to_end_cph_chart,
    build_end_to_end_deviation_chart,
    build_end_to_end_income_source_pie,
    build_end_to_end_time_breakdown_pie,
    build_range_histogram,
)
from .config import (
    CHAOS_RUNE_GP_PER_CLUE,
    COMBINED_ACQUISITION_GP_INCOME_PER_CLUE,
    DEATH_RUNE_GP_PER_CLUE,
    DEATHS_PER_BLOOD,
    END_TO_END_RECENT_ACQ_EWMA_SPAN,
    END_TO_END_RECENT_COMP_EWMA_SPAN,
    EXPECTED_ALCH_GP_PER_CASKET,
    GOAL_CASKETS,
    GOAL_HEADER_CONTROLS_CONTAINER_WIDTH_PX,
    PRICE_BLOOD,
    PRICE_DEATH,
    RUNE_ARMOR_GP_PER_CLUE,
)
from .data import append_row, clear_loaded_data_cache, load_df
from .formatting import (
    fmt_hours_minutes,
    human_gp_or_na,
    minutes_to_metric_duration,
    now_local,
    parse_playtime_hhmm,
    resolve_session_log_date,
    seconds_to_metric_duration,
)
from .schemas import ACQ_COLS, ACQ_SHEET, COMP_COLS, COMP_SHEET
from .state import (
    persist_acq_logger_state,
    persist_acq_logger_state_values,
    persist_comp_logger_state,
    persist_comp_logger_state_values,
    queue_pending_updates,
)

ASSET_DIR = Path(__file__).resolve().parent


def inject_styles() -> None:
    css = (ASSET_DIR / "styles.css").read_text()
    st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)


def _render_inline_html(html: str, *, height: int = 0) -> None:
    html_fn = getattr(st, "html", None)
    if callable(html_fn):
        html_params = inspect.signature(html_fn).parameters
        if "unsafe_allow_javascript" in html_params:
            html_kwargs: dict[str, Any] = {"unsafe_allow_javascript": True}
            if "width" in html_params:
                html_kwargs["width"] = "stretch"
            html_fn(html, **html_kwargs)
            return

    iframe_fn = getattr(st, "iframe", None)
    if callable(iframe_fn):
        iframe_params = inspect.signature(iframe_fn).parameters
        iframe_kwargs: dict[str, Any] = {}
        normalized_height = max(1, int(height))
        if "height" in iframe_params:
            iframe_kwargs["height"] = normalized_height
        if "width" in iframe_params:
            iframe_kwargs["width"] = "stretch"
        if "scrolling" in iframe_params:
            iframe_kwargs["scrolling"] = False

        if "srcdoc" in iframe_params:
            iframe_fn(srcdoc=html, **iframe_kwargs)
            return
        if "html" in iframe_params:
            iframe_fn(html=html, **iframe_kwargs)
            return
        if "body" in iframe_params:
            iframe_fn(body=html, **iframe_kwargs)
            return
        if "src" in iframe_params:
            iframe_fn(src=f"data:text/html;charset=utf-8,{quote(html)}", **iframe_kwargs)
            return
        if iframe_params:
            iframe_fn(f"data:text/html;charset=utf-8,{quote(html)}", **iframe_kwargs)
            return

    if callable(html_fn):
        html_params = inspect.signature(html_fn).parameters
        html_kwargs: dict[str, Any] = {}
        if "width" in html_params:
            html_kwargs["width"] = "stretch"
        if "unsafe_allow_javascript" in html_params:
            html_kwargs["unsafe_allow_javascript"] = True
        html_fn(html, **html_kwargs)
        return

    # Legacy fallback for older Streamlit versions.
    from streamlit.components.v1 import html as legacy_html
    legacy_html(html, height=max(1, height))


def inject_ui_dom_script() -> None:
    script = (ASSET_DIR / "dom_polish.js").read_text()
    _render_inline_html(f"<script>\n{script}\n</script>", height=0)


def render_accent_metric(container: Any, label: str, value: Any, key: str) -> None:
    try:
        metric_container = container.container(key=key)
    except TypeError:
        metric_container = container.container()
    metric_container.metric(label, value)


def render_header(ctx: Any) -> None:
    def set_goal_progress_start_point() -> None:
        start_set_at = now_local()
        st.session_state["goal_progress_start_acq_total"] = ctx.running_acq_total
        st.session_state["goal_progress_start_comp_total"] = ctx.running_comp_total
        st.session_state["goal_progress_start_set_at"] = start_set_at.isoformat()
        state.save_goal_progress_state(
            start_acq_total=ctx.running_acq_total,
            start_comp_total=ctx.running_comp_total,
            start_set_at=start_set_at,
        )

    def persist_goal_caskets() -> None:
        normalized_goal = state.normalize_goal_caskets(st.session_state.get("goal_caskets", GOAL_CASKETS))
        st.session_state["goal_caskets"] = normalized_goal
        state.save_goal_settings_state(normalized_goal)

    st.title("Hard Clue Dashboard")
    goal_controls_kwargs: dict[str, Any] = {"key": "goal_header_controls"}
    if "width" in inspect.signature(st.container).parameters:
        goal_controls_kwargs["width"] = GOAL_HEADER_CONTROLS_CONTAINER_WIDTH_PX
    goal_controls = st.container(**goal_controls_kwargs)
    with goal_controls:
        goal_input_col, goal_start_col = st.columns(2, gap="small")
        with goal_input_col:
            st.markdown('<div class="goal-caskets-label">Goal caskets</div>', unsafe_allow_html=True)
            st.number_input(
                "Goal caskets",
                min_value=1,
                step=1,
                key="goal_caskets",
                on_change=persist_goal_caskets,
                label_visibility="collapsed",
                width="stretch",
            )
        with goal_start_col:
            st.markdown(
                '<div class="goal-caskets-label goal-caskets-label--spacer" aria-hidden="true">Goal caskets</div>',
                unsafe_allow_html=True,
            )
            st.button(
                "Set Progress Start Point",
                on_click=set_goal_progress_start_point,
                width="stretch",
                key="btn_goal_start_point",
            )

    totals_col1, totals_col2, _totals_spacer_col = st.columns([2.0, 2.0, 4.0])
    totals_col1.metric("Total clues acquired tracked", ctx.running_acq_total)
    totals_col2.metric("Total caskets completed tracked", ctx.running_comp_total)

    if ctx.progress_start_set_at is None:
        st.caption("Progress start point: not set yet (currently counting from all-time totals).")
    else:
        st.caption(
            "Progress start point: "
            f"{ctx.progress_start_set_at.strftime('%Y-%m-%d %H:%M:%S %Z')} "
            f"(baseline: {ctx.progress_start_acq_total} acquired, {ctx.progress_start_comp_total} completed)"
        )

    st.caption(
        f"Since start point: {ctx.acq_since_progress_start} clues acquired • {ctx.comp_since_progress_start} caskets completed"
        f" • {ctx.clues_on_ground_since_progress_start} clues stacked"
        f" ({fmt_hours_minutes(ctx.stacked_clues_completion_time_s)} to complete)"
    )
    st.caption(
        f"Goal window context: {ctx.acq_since_progress_start} / {ctx.goal_caskets} clues acquired • "
        f"{ctx.comp_since_progress_start} / {ctx.goal_caskets} caskets completed • "
        f"{ctx.goal_progress_remaining} caskets remaining"
    )
    st.progress(
        ctx.goal_progress,
        text=(
            f"Goal progress to {ctx.goal_caskets} caskets (completed since start): "
            f"{ctx.goal_progress_completed} / {ctx.goal_caskets} ({ctx.goal_progress * 100:.1f}%) • {ctx.goal_progress_remaining} remaining"
            f" • {ctx.clues_still_to_acquire_for_goal} still to acquire after stacked clues"
        ),
    )
    inject_ui_dom_script()


def render_sidebar(ctx: Any) -> None:
    with st.sidebar:
        st.header("Acquisition Logger")

        def acq_start_now() -> None:
            start_at = now_local()
            st.session_state["acq_start_system"] = start_at
            st.session_state["acq_end_system"] = None
            st.session_state["w_acq_date"] = start_at.date()
            persist_acq_logger_state()

        def acq_end_now() -> None:
            st.session_state["acq_end_system"] = now_local()
            persist_acq_logger_state()

        def acq_clear_start_system() -> None:
            st.session_state["acq_start_system"] = None
            persist_acq_logger_state()

        def acq_clear_end_system() -> None:
            st.session_state["acq_end_system"] = None
            persist_acq_logger_state()

        acq_btn_col1, acq_btn_col2 = st.columns(2)
        with acq_btn_col1:
            st.button("Start Now", on_click=acq_start_now, width="stretch", key="btn_acq_start")
        with acq_btn_col2:
            st.button("End Now", on_click=acq_end_now, width="stretch", key="btn_acq_end")

        s0 = st.session_state.get("acq_start_system")
        e0 = st.session_state.get("acq_end_system")
        st.caption(
            f"System start: **{s0.strftime('%Y-%m-%d %H:%M:%S') if s0 else '—'}**  \n"
            f"System end: **{e0.strftime('%Y-%m-%d %H:%M:%S') if e0 else '—'}**"
        )
        acq_clear_col1, acq_clear_col2 = st.columns(2)
        with acq_clear_col1:
            st.button("Clear Start", on_click=acq_clear_start_system, width="stretch", key="btn_acq_clear_start")
        with acq_clear_col2:
            st.button("Clear End", on_click=acq_clear_end_system, width="stretch", key="btn_acq_clear_end")

        def save_acq() -> None:
            df = load_df(ACQ_SHEET, ACQ_COLS, ctx.session_cache_key)
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
            resolved_log_date = resolve_session_log_date(
                log_date,
                start_system=ss,
                end_system=ee,
                used_system_duration=dur_play is None and dur_sys is not None,
            )

            # This is stored as net blood-rune change for the trip, so rare profit
            # trips can be logged instead of being blocked by validation.
            bloods_used = start_blood - end_blood

            # Barraging always spends 2 deaths per blood used, but blood-rune profit
            # from drops should not imply matching death-rune profit too.
            deaths_used = int(bloods_used * DEATHS_PER_BLOOD) if bloods_used > 0 else 0
            gp_cost = float(bloods_used * PRICE_BLOOD + deaths_used * PRICE_DEATH)
            hours = dur / 3600.0
            clues_per_hour = float(clues / hours) if hours > 0 else 0.0
            gp_per_hour = float(gp_cost / hours) if hours > 0 else 0.0
            gp_per_clue = float(gp_cost / clues) if clues > 0 else 0.0

            numeric_ids = pd.to_numeric(df["trip_id"], errors="coerce") if not df.empty else pd.Series(dtype=float)
            next_id = int(numeric_ids.max() + 1) if numeric_ids.notna().any() else 1

            row = {
                "trip_id": next_id,
                "log_date": resolved_log_date.isoformat(),
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
            append_row(ACQ_SHEET, ACQ_COLS, row)
            clear_loaded_data_cache()

            next_start_system = ee if ee else st.session_state.get("acq_start_system")
            next_state = {
                "w_acq_date": resolve_session_log_date(
                    resolved_log_date,
                    start_system=next_start_system,
                    used_system_duration=next_start_system is not None,
                ),
                "w_acq_start_play": end_play if end_play else st.session_state.get("w_acq_start_play", ""),
                "w_acq_end_play": "",
                "w_acq_start_blood": end_blood,
                "w_acq_end_blood": None,
                "w_acq_clues": clues,
                "w_acq_notes": "",
                "acq_start_system": next_start_system,
                "acq_end_system": None,
            }
            queue_pending_updates(next_state)
            persist_acq_logger_state_values(
                log_date=next_state["w_acq_date"],
                start_playtime=next_state["w_acq_start_play"],
                end_playtime=next_state["w_acq_end_play"],
                start_bloods=next_state["w_acq_start_blood"],
                end_bloods=next_state["w_acq_end_blood"],
                clues=next_state["w_acq_clues"],
                notes=next_state["w_acq_notes"],
                start_system=next_state["acq_start_system"],
                end_system=next_state["acq_end_system"],
            )

        st.date_input("Date", key="w_acq_date", on_change=persist_acq_logger_state)
        st.text_input("Start playtime (HH.mm)", key="w_acq_start_play", placeholder="", on_change=persist_acq_logger_state)
        st.text_input("End playtime (HH.mm)", key="w_acq_end_play", placeholder="", on_change=persist_acq_logger_state)
        st.number_input(
            "Start bloods",
            min_value=0,
            step=1,
            value=None,
            key="w_acq_start_blood",
            on_change=persist_acq_logger_state,
        )
        st.number_input(
            "End bloods",
            min_value=0,
            step=1,
            value=None,
            key="w_acq_end_blood",
            on_change=persist_acq_logger_state,
        )
        st.number_input("Clues obtained", min_value=1, step=1, key="w_acq_clues", on_change=persist_acq_logger_state)
        st.text_area("Notes", key="w_acq_notes", height=72, placeholder="", on_change=persist_acq_logger_state)
        st.caption("Duration uses playtime if both are entered; otherwise uses system Start/End.")
        if st.session_state.get("acq_draft_error"):
            st.error(st.session_state["acq_draft_error"])

        if st.button("Save Acquisition Trip", type="primary", width="stretch", key="btn_save_acq_trip"):
            try:
                save_acq()
                st.success("Saved acquisition trip.")
                st.rerun()
            except Exception as ex:
                st.error(str(ex))

        st.divider()
        st.header("Completion Logger")

        def comp_start_now() -> None:
            start_at = now_local()
            st.session_state["comp_start_system"] = start_at
            st.session_state["comp_end_system"] = None
            st.session_state["w_comp_date"] = start_at.date()
            persist_comp_logger_state()

        def comp_end_now() -> None:
            st.session_state["comp_end_system"] = now_local()
            persist_comp_logger_state()

        def comp_clear_start_system() -> None:
            st.session_state["comp_start_system"] = None
            persist_comp_logger_state()

        def comp_clear_end_system() -> None:
            st.session_state["comp_end_system"] = None
            persist_comp_logger_state()

        comp_btn_col1, comp_btn_col2 = st.columns(2)
        with comp_btn_col1:
            st.button("Start Now", on_click=comp_start_now, width="stretch", key="btn_comp_start")
        with comp_btn_col2:
            st.button("End Now", on_click=comp_end_now, width="stretch", key="btn_comp_end")

        s1 = st.session_state.get("comp_start_system")
        e1 = st.session_state.get("comp_end_system")
        st.caption(
            f"System start: **{s1.strftime('%Y-%m-%d %H:%M:%S') if s1 else '—'}**  \n"
            f"System end: **{e1.strftime('%Y-%m-%d %H:%M:%S') if e1 else '—'}**"
        )
        comp_clear_col1, comp_clear_col2 = st.columns(2)
        with comp_clear_col1:
            st.button("Clear Start", on_click=comp_clear_start_system, width="stretch", key="btn_comp_clear_start")
        with comp_clear_col2:
            st.button("Clear End", on_click=comp_clear_end_system, width="stretch", key="btn_comp_clear_end")

        def save_comp() -> None:
            df = load_df(COMP_SHEET, COMP_COLS, ctx.session_cache_key)
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
            resolved_log_date = resolve_session_log_date(
                log_date,
                start_system=ss,
                end_system=ee,
                used_system_duration=dur_play is None and dur_sys is not None,
            )

            hours = dur / 3600.0
            clues_per_hour = float(completed / hours) if hours > 0 else 0.0
            numeric_ids = pd.to_numeric(df["session_id"], errors="coerce") if not df.empty else pd.Series(dtype=float)
            next_id = int(numeric_ids.max() + 1) if numeric_ids.notna().any() else 1

            row = {
                "session_id": next_id,
                "log_date": resolved_log_date.isoformat(),
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
            append_row(COMP_SHEET, COMP_COLS, row)
            clear_loaded_data_cache()

            next_start_system = ee if ee else st.session_state.get("comp_start_system")
            next_state = {
                "w_comp_date": resolve_session_log_date(
                    resolved_log_date,
                    start_system=next_start_system,
                    used_system_duration=next_start_system is not None,
                ),
                "w_comp_end_play": "",
                "w_comp_completed": completed,
                "w_comp_notes": "",
                "comp_start_system": next_start_system,
                "comp_end_system": None,
            }
            if end_play:
                next_state["w_comp_start_play"] = end_play
            else:
                next_state["w_comp_start_play"] = st.session_state.get("w_comp_start_play", "")
            queue_pending_updates(next_state)
            persist_comp_logger_state_values(
                log_date=next_state["w_comp_date"],
                start_playtime=next_state["w_comp_start_play"],
                end_playtime=next_state["w_comp_end_play"],
                clues_completed=next_state["w_comp_completed"],
                notes=next_state["w_comp_notes"],
                start_system=next_state["comp_start_system"],
                end_system=next_state["comp_end_system"],
            )

        st.date_input("Date", key="w_comp_date", on_change=persist_comp_logger_state)
        st.text_input(
            "Start playtime (HH.mm)",
            key="w_comp_start_play",
            placeholder="",
            on_change=persist_comp_logger_state,
        )
        st.text_input(
            "End playtime (HH.mm)",
            key="w_comp_end_play",
            placeholder="",
            on_change=persist_comp_logger_state,
        )
        st.number_input(
            "Caskets completed",
            min_value=1,
            step=1,
            key="w_comp_completed",
            on_change=persist_comp_logger_state,
        )
        st.text_area("Notes", key="w_comp_notes", height=72, placeholder="", on_change=persist_comp_logger_state)
        st.caption("Duration uses playtime if both are entered; otherwise uses system Start/End.")
        if st.session_state.get("comp_draft_error"):
            st.error(st.session_state["comp_draft_error"])

        if st.button("Save Completion Session", type="primary", width="stretch", key="btn_save_comp_session"):
            try:
                save_comp()
                st.success("Saved completion session.")
                st.rerun()
            except Exception as ex:
                st.error(str(ex))


def render_tabs(ctx: Any) -> None:
    acq_df = ctx.acq_df
    comp_df = ctx.comp_df
    acq_sum = ctx.acq_sum
    comp_sum = ctx.comp_sum
    acq_metrics_df = ctx.acq_metrics_df
    comp_metrics_df = ctx.comp_metrics_df
    end_to_end_sum = ctx.end_to_end_sum
    end_to_end_trend_df = ctx.end_to_end_trend_df
    goal_caskets = ctx.goal_caskets
    acq_goal_remaining = ctx.acq_goal_remaining
    comp_goal_remaining = ctx.comp_goal_remaining
    acq_goal_time_remaining_s = ctx.acq_goal_time_remaining_s
    comp_goal_time_remaining_s = ctx.comp_goal_time_remaining_s
    combo_goal_remaining = ctx.combo_goal_remaining
    combo_goal_time_remaining_s = ctx.combo_goal_time_remaining_s
    combo_expected_alch_gp_remaining = ctx.combo_expected_alch_gp_remaining
    combo_projected_net_acquisition_gp_remaining = ctx.combo_projected_net_acquisition_gp_remaining
    combo_expected_net_remaining = ctx.combo_expected_net_remaining
    tab_acq, tab_comp, tab_combo = st.tabs(["Acquisition", "Completion", "End-to-end"])


    with tab_acq:
        if acq_df.empty:
            st.info("No acquisition trips logged yet.")
        else:
            acq_rune_gp_per_clue = acq_sum.get("rune_armor_gp_per_clue", RUNE_ARMOR_GP_PER_CLUE) if acq_sum else RUNE_ARMOR_GP_PER_CLUE
            acq_chaos_gp_per_clue = acq_sum.get("chaos_rune_gp_per_clue", CHAOS_RUNE_GP_PER_CLUE) if acq_sum else CHAOS_RUNE_GP_PER_CLUE
            acq_death_gp_per_clue = acq_sum.get("death_rune_gp_per_clue", DEATH_RUNE_GP_PER_CLUE) if acq_sum else DEATH_RUNE_GP_PER_CLUE
            acq_combined_gp_income_per_clue = (
                acq_sum.get("combined_acquisition_gp_income_per_clue", COMBINED_ACQUISITION_GP_INCOME_PER_CLUE)
                if acq_sum
                else COMBINED_ACQUISITION_GP_INCOME_PER_CLUE
            )
            acq_gp_cost_per_clue = acq_sum.get("gp_cost_per_clue") if acq_sum else float("nan")
            acq_net_gp_per_clue = acq_sum.get("net_gp_per_clue_acquired") if acq_sum else float("nan")
            total = int(acq_sum["total_clues"])
            remaining = int(acq_goal_remaining)
            recent = acq_metrics_df["recent_ewma_minutes_per_clue"].dropna()
            recent_latest = float(recent.iloc[-1]) if not recent.empty else 0.0
            recent_best = float(recent.min()) if not recent.empty else 0.0
            median_minutes_per_clue = float(acq_metrics_df["minutes_per_clue"].dropna().median()) if acq_metrics_df["minutes_per_clue"].notna().any() else 0.0

            k1, k2, k3, k4, k5, k6 = st.columns(6)
            k1.metric("Trips", int(acq_sum["total_trips"]))
            k2.metric("Clues logged", total)
            k3.metric("Avg time / clue", seconds_to_metric_duration(acq_sum["avg_time_clue_s"]))
            render_accent_metric(k4, "Clues / hour", f"{acq_sum['clues_per_hour']:.2f}", "metric_acq_cph")
            k5.metric("Bloods / clue", f"{acq_sum['avg_bloods_per_clue']:.2f}")
            k6.metric("GP spent / clue", human_gp_or_na(acq_sum["avg_gp_per_clue"]))

            st.divider()

            t1, t2, t3, t4, t5, t6 = st.columns(6)
            t1.metric("Avg trip length", seconds_to_metric_duration(acq_sum["avg_time_trip_s"]))
            t2.metric("Recent EWMA time / clue", minutes_to_metric_duration(recent_latest))
            t3.metric("Median time / clue", minutes_to_metric_duration(median_minutes_per_clue))
            t4.metric("Best recent EWMA time / clue", minutes_to_metric_duration(recent_best))
            t5.metric("Time remaining (acquisition)", fmt_hours_minutes(acq_goal_time_remaining_s))
            t6.metric("Remaining caskets", remaining)

            st.divider()

            p1, p2, p3, p4, p5, p6 = st.columns(6)
            p1.metric("Rune armor GP / clue", human_gp_or_na(acq_rune_gp_per_clue))
            p2.metric("Chaos rune GP / clue", human_gp_or_na(acq_chaos_gp_per_clue))
            p3.metric("Death rune GP / clue", human_gp_or_na(acq_death_gp_per_clue))
            p4.metric("Combined acquisition GP / clue", human_gp_or_na(acq_combined_gp_income_per_clue))
            p5.metric("GP cost per clue", human_gp_or_na(acq_gp_cost_per_clue))
            p6.metric("Net acquisition GP / clue", human_gp_or_na(acq_net_gp_per_clue))

            st.divider()
            st.subheader("Charts")
            st.plotly_chart(build_acq_clues_per_hour_chart(acq_metrics_df), width="stretch")

            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(build_acq_profitability_chart(acq_metrics_df), width="stretch")
            with c2:
                st.plotly_chart(
                    build_range_histogram(
                        acq_metrics_df["minutes_per_clue"],
                        "Minutes per clue distribution",
                        "Minutes per clue range",
                        "Trips",
                    ),
                    width="stretch",
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
            disp["expected_rune_armor_gp"] = disp["expected_rune_armor_gp"].round(0)
            disp["expected_chaos_rune_gp"] = disp["expected_chaos_rune_gp"].round(0)
            disp["expected_death_rune_gp"] = disp["expected_death_rune_gp"].round(0)
            disp["expected_combined_acquisition_gp_income"] = disp["expected_combined_acquisition_gp_income"].round(0)
            disp["expected_net_gp_trip_acquisition"] = disp["expected_net_gp_trip_acquisition"].round(0)
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
                        "notes",
                        "bloods_per_clue",
                        "gp_spent_per_clue",
                        "expected_rune_armor_gp",
                        "expected_chaos_rune_gp",
                        "expected_death_rune_gp",
                        "expected_combined_acquisition_gp_income",
                        "expected_net_gp_trip_acquisition",
                        "bloods_used",
                        "deaths_used",
                        "gp_cost",
                    ]
                ].sort_values("trip_id", ascending=False),
                width="stretch",
                height=350,
                hide_index=True,
                column_config={"notes": st.column_config.TextColumn("notes", width="large")},
            )


    with tab_comp:
        if comp_df.empty:
            st.info("No completion sessions logged yet.")
        else:
            total_completed = int(comp_sum["total_completed"])
            remaining = int(comp_goal_remaining)
            recent = comp_metrics_df["recent_ewma_minutes_per_casket"].dropna()
            recent_latest = float(recent.iloc[-1]) if not recent.empty else 0.0
            recent_best = float(recent.min()) if not recent.empty else 0.0
            median_minutes_per_casket = float(comp_metrics_df["minutes_per_casket"].dropna().median()) if comp_metrics_df["minutes_per_casket"].notna().any() else 0.0
            fastest_minutes_per_casket = float(comp_metrics_df["minutes_per_casket"].dropna().min()) if comp_metrics_df["minutes_per_casket"].notna().any() else 0.0
            slowest_minutes_per_casket = float(comp_metrics_df["minutes_per_casket"].dropna().max()) if comp_metrics_df["minutes_per_casket"].notna().any() else 0.0

            k1, k2, k3, k4, k5, k6 = st.columns(6)
            k1.metric("Sessions", int(comp_sum["total_sessions"]))
            k2.metric("Caskets completed logged", total_completed)
            k3.metric("Avg time / casket", seconds_to_metric_duration(comp_sum["avg_time_casket_s"]))
            render_accent_metric(k4, "Caskets / hour", f"{comp_sum['caskets_per_hour']:.2f}", "metric_comp_cph")
            k5.metric("Median time / casket", minutes_to_metric_duration(median_minutes_per_casket))
            k6.metric("Recent EWMA time / casket", minutes_to_metric_duration(recent_latest))

            st.divider()

            t1, t2, t3, t4, t5, t6 = st.columns(6)
            t1.metric("Avg session length", seconds_to_metric_duration(comp_sum["avg_time_session_s"]))
            t2.metric("Best recent EWMA time / casket", minutes_to_metric_duration(recent_best))
            t3.metric("Fastest session time / casket", minutes_to_metric_duration(fastest_minutes_per_casket))
            t4.metric("Slowest session time / casket", minutes_to_metric_duration(slowest_minutes_per_casket))
            t5.metric("Time remaining (completion)", fmt_hours_minutes(comp_goal_time_remaining_s))
            t6.metric(f"Remaining to {goal_caskets} (completion)", remaining)

            st.divider()
            st.subheader("Charts")
            st.plotly_chart(build_completion_caskets_per_hour_chart(comp_metrics_df), width="stretch")
            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(build_completion_caskets_completed_chart(comp_metrics_df), width="stretch")
            with c2:
                st.plotly_chart(
                    build_range_histogram(
                        comp_metrics_df["minutes_per_casket"],
                        "Minutes per casket distribution",
                        "Minutes per casket range",
                        "Sessions",
                    ),
                    width="stretch",
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
                width="stretch",
                height=350,
                hide_index=True,
                column_config={"notes": st.column_config.TextColumn("notes", width="large")},
            )


    with tab_combo:
        st.subheader("End-to-end")
        if acq_df.empty or comp_df.empty or not end_to_end_sum:
            st.info("Log at least one acquisition trip and one completion session to get end-to-end averages.")
        else:
            a1, a2, a3, a4, _a5 = st.columns(5)
            a1.metric("Acquire time / clue", minutes_to_metric_duration(end_to_end_sum["acquire_minutes_per_clue"]))
            a2.metric("Complete time / casket", minutes_to_metric_duration(end_to_end_sum["complete_minutes_per_casket"]))
            a3.metric("Overall time / casket", minutes_to_metric_duration(end_to_end_sum["total_minutes_per_casket"]))
            render_accent_metric(
                a4,
                "Overall caskets / hour",
                f"{end_to_end_sum['end_to_end_caskets_per_hour']:.2f}",
                "metric_overall_cph",
            )

            st.divider()

            p1, p2, p3, p4, p5 = st.columns(5)
            p1.metric("Expected acquisition income / clue", human_gp_or_na(end_to_end_sum["combined_acquisition_gp_income_per_clue"]))
            p2.metric("Expected acquisition cost / clue", human_gp_or_na(end_to_end_sum["expected_cost_per_clue_acquisition"]))
            p3.metric("Net expected acquisition GP / clue", human_gp_or_na(end_to_end_sum["net_gp_per_clue_on_acquisition"]))
            p4.metric("Expected alch income / casket", human_gp_or_na(end_to_end_sum["expected_income_per_casket_alch"]))
            p5.metric("Net GP / casket (full process)", human_gp_or_na(end_to_end_sum["net_gp_per_casket"]))

            st.divider()

            b1, b2, b3, b4, _b5 = st.columns(5)
            b1.metric("Acquisition share of total time", f"{end_to_end_sum['acquisition_share_of_total_time'] * 100:.1f}%")
            b2.metric("Completion share of total time", f"{end_to_end_sum['completion_share_of_total_time'] * 100:.1f}%")
            b3.metric("Current bottleneck", end_to_end_sum["bottleneck"])
            b4.metric("Time remaining (total)", fmt_hours_minutes(combo_goal_time_remaining_s))

            st.divider()

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Net acquisition GP remaining", human_gp_or_na(combo_projected_net_acquisition_gp_remaining))
            c2.metric("Expected alch GP remaining", human_gp_or_na(combo_expected_alch_gp_remaining))
            c3.metric("Net GP remaining (full process)", human_gp_or_na(combo_expected_net_remaining))
            c4.metric("Remaining caskets", int(combo_goal_remaining))

        if not end_to_end_trend_df.empty:
            st.divider()
            st.subheader("Charts")
            st.plotly_chart(build_end_to_end_cph_chart(end_to_end_trend_df), width="stretch")
            st.plotly_chart(build_end_to_end_deviation_chart(end_to_end_trend_df), width="stretch")
            if end_to_end_sum:
                pie_col1, pie_col2 = st.columns(2)
                with pie_col1:
                    st.plotly_chart(build_end_to_end_income_source_pie(end_to_end_sum), width="stretch")
                with pie_col2:
                    st.plotly_chart(build_end_to_end_time_breakdown_pie(end_to_end_sum), width="stretch")
            else:
                st.caption("Full end-to-end summary cards and pie charts appear after at least one acquisition and one completion entry.")
            st.caption(
                f"**End-to-end caskets/hr chart.** Hollow circles are same-day points: blue shows raw acquisition, green "
                f"shows raw completion, and red shows a sample-adjusted daily total. Red blends each same-day component "
                f"with its own recent EWMA baseline based on that component's same-day count. EWMA means exponentially "
                f"weighted moving average: a recent-pace line that weights newer logged dates more heavily than older "
                f"logged dates. These lines use spans of {END_TO_END_RECENT_ACQ_EWMA_SPAN} acquisition dates and "
                f"{END_TO_END_RECENT_COMP_EWMA_SPAN} completion dates, and they are causal, so older points do not change "
                "when newer data is added. If only one side is logged on a date, the other side uses its recent EWMA value "
                "once it exists. The dotted gray line is the flat overall weighted average across all logged data."
            )
            st.caption(
                "**End-to-end daily deviation chart.** Bars compare each adjusted daily total with the recent EWMA. The "
                "percent label shows how much that day was faster or slower than recent pace. Darker bars have higher "
                "daily confidence, based on how much of the estimate came from same-day acquisition and completion data "
                "weighted by each side's share of recent end-to-end time."
            )
