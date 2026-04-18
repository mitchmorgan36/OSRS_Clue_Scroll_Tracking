import inspect
import math
from datetime import date, datetime
from typing import Dict, Any
from urllib.parse import quote
from uuid import uuid4

from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from end_to_end_metrics import build_end_to_end_trend_df
import google_sheets_backend as gsb
from weighted_metrics import rolling_weighted_ratio, weighted_ratio

# ----------------------------
# Config
# ----------------------------
st.set_page_config(page_title="Hard Clue Dashboard", layout="wide")

GOAL_CASKETS = 650
DEFAULT_CLUES_PER_TRIP = 5
END_TO_END_RECENT_ACQ_EWMA_SPAN = 8
END_TO_END_RECENT_COMP_EWMA_SPAN = 4
PRIMARY_PACE_CHART_HEIGHT = 600
SECONDARY_DETAIL_CHART_HEIGHT = 500
CHART_TOP_MARGIN = 64
LINE_CHART_BOTTOM_MARGIN = 165
HISTOGRAM_BOTTOM_MARGIN = 80
PRIMARY_LEGEND_Y = -0.16
SECONDARY_LEGEND_Y = -0.22
END_TO_END_X_TITLE_STANDOFF = 38
SECONDARY_HISTOGRAM_HEIGHT = (
    SECONDARY_DETAIL_CHART_HEIGHT - LINE_CHART_BOTTOM_MARGIN + HISTOGRAM_BOTTOM_MARGIN
)
GOAL_HEADER_CONTROL_WIDTH_PX = 200
GOAL_HEADER_CONTROLS_CONTAINER_WIDTH_PX = (GOAL_HEADER_CONTROL_WIDTH_PX * 2) + 24

GOAL_PROGRESS_STATE_COLS = (
    "start_acq_total",
    "start_comp_total",
    "start_set_at",
)
GOAL_PROGRESS_STATE_SHEET = getattr(gsb, "GOAL_PROGRESS_STATE_SHEET", "goal_progress_state")
GOAL_SETTINGS_COLS = ("goal_caskets",)
GOAL_SETTINGS_SHEET = getattr(gsb, "GOAL_SETTINGS_SHEET", "goal_settings")
ACQ_SHEET = getattr(gsb, "ACQ_SHEET", "acquisition_trips")
COMP_SHEET = getattr(gsb, "COMP_SHEET", "completion_sessions")
ACQ_LOGGER_STATE_COLS = (
    "log_date",
    "start_playtime",
    "end_playtime",
    "start_bloods",
    "end_bloods",
    "clues",
    "notes",
    "start_system",
    "end_system",
    "updated_at",
)
ACQ_LOGGER_STATE_SHEET = getattr(gsb, "ACQ_LOGGER_STATE_SHEET", "acquisition_logger_state")
COMP_LOGGER_STATE_COLS = (
    "log_date",
    "start_playtime",
    "end_playtime",
    "clues_completed",
    "notes",
    "start_system",
    "end_system",
    "updated_at",
)
COMP_LOGGER_STATE_SHEET = getattr(gsb, "COMP_LOGGER_STATE_SHEET", "completion_logger_state")

PRICE_BLOOD = 400
PRICE_DEATH = 200
DEATHS_PER_BLOOD = 2

AVG_REWARD_ROLLS_PER_CASKET = 5
EXPECTED_ALCH_GP_PER_CASKET = 54244.076180305085
LOCAL_TIMEZONE = ZoneInfo("America/New_York")

# Fixed acquisition EV rules (project-level assumptions; not user-configurable)
JELLY_KILLS_PER_HARD_CLUE = 60
RUNE_ARMOR_GP_PER_QUALIFYING_DROP = 28573
RUNE_ARMOR_QUALIFYING_DROPS_PER_128_KILLS = 3
CHAOS_RUNES_PER_DROP = 45
CHAOS_DROP_KILLS_PER_DROP = 25.6
CHAOS_RUNE_GP = 45
DEATH_RUNES_PER_DROP = 15
DEATH_DROP_KILLS_PER_DROP = 42.67
DEATH_RUNE_GP = PRICE_DEATH

RUNE_ARMOR_GP_PER_KILL = (
    RUNE_ARMOR_GP_PER_QUALIFYING_DROP * RUNE_ARMOR_QUALIFYING_DROPS_PER_128_KILLS / 128
)
RUNE_ARMOR_GP_PER_CLUE = RUNE_ARMOR_GP_PER_KILL * JELLY_KILLS_PER_HARD_CLUE
CHAOS_RUNES_PER_KILL = CHAOS_RUNES_PER_DROP / CHAOS_DROP_KILLS_PER_DROP
CHAOS_RUNE_GP_PER_KILL = CHAOS_RUNES_PER_KILL * CHAOS_RUNE_GP
CHAOS_RUNE_GP_PER_CLUE = CHAOS_RUNE_GP_PER_KILL * JELLY_KILLS_PER_HARD_CLUE
DEATH_RUNES_PER_KILL = DEATH_RUNES_PER_DROP / DEATH_DROP_KILLS_PER_DROP
DEATH_RUNE_GP_PER_KILL = DEATH_RUNES_PER_KILL * DEATH_RUNE_GP
DEATH_RUNE_GP_PER_CLUE = DEATH_RUNE_GP_PER_KILL * JELLY_KILLS_PER_HARD_CLUE
COMBINED_ACQUISITION_GP_INCOME_PER_CLUE = (
    RUNE_ARMOR_GP_PER_CLUE + CHAOS_RUNE_GP_PER_CLUE + DEATH_RUNE_GP_PER_CLUE
)

# EV validation checks:
# - rune_armor_gp_per_kill = 28573 * 3 / 128 = 669.6796875
# - rune_armor_gp_per_clue = 669.6796875 * 60 = 40180.78125
# - chaos_runes_per_kill = 45 / 25.6 = 1.7578125
# - chaos_rune_gp_per_kill = 1.7578125 * 45 = 79.1015625
# - chaos_rune_gp_per_clue = 79.1015625 * 60 = 4746.09375
# - death_runes_per_kill = 15 / 42.67 = 0.3515350363252871
# - death_rune_gp_per_kill = 0.3515350363252871 * 200 = 70.30700726505742
# - death_rune_gp_per_clue = 70.30700726505742 * 60 = 4218.420435903446
# - combined_acquisition_gp_income_per_clue = 40180.78125 + 4746.09375 + 4218.420435903446 = 49145.29543590345
assert abs(RUNE_ARMOR_GP_PER_KILL - 669.6796875) < 1e-12
assert abs(RUNE_ARMOR_GP_PER_CLUE - 40180.78125) < 1e-12
assert abs(CHAOS_RUNES_PER_KILL - 1.7578125) < 1e-12
assert abs(CHAOS_RUNE_GP_PER_KILL - 79.1015625) < 1e-12
assert abs(CHAOS_RUNE_GP_PER_CLUE - 4746.09375) < 1e-12
assert abs(DEATH_RUNES_PER_KILL - 0.3515350363252871) < 1e-12
assert abs(DEATH_RUNE_GP_PER_KILL - 70.30700726505742) < 1e-12
assert abs(DEATH_RUNE_GP_PER_CLUE - 4218.420435903446) < 1e-12
assert abs(COMBINED_ACQUISITION_GP_INCOME_PER_CLUE - 49145.29543590345) < 1e-12

# ----------------------------
# UI tightening
# ----------------------------
st.markdown(
    """
<style>
:root {
  --acq-save-bg: #1d4ed8;
  --acq-save-border: #1e40af;
  --acq-save-hover: #1e40af;
  --comp-save-bg: #0f766e;
  --comp-save-border: #115e59;
  --comp-save-hover: #115e59;
  --start-hover-bg: #2f7d57;
  --start-hover-border: #256347;
  --end-hover-bg: #b4534d;
  --end-hover-border: #8f413b;
  --goal-header-control-width: 300px;
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
section[data-testid="stSidebar"] [data-testid="InputInstructions"] {
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
  white-space: normal !important;
  overflow-wrap: anywhere !important;
  text-overflow: clip !important;
  line-height: 1.2 !important;
}
div[data-testid="metric-container"] [data-testid="stMetricLabel"] {
  overflow: visible !important;
}
div[data-testid="metric-container"] label {
  overflow: visible !important;
}

/* Slightly reduce default spacing around column blocks holding metrics */
div[data-testid="column"] div[data-testid="metric-container"] {
  margin-top: 0 !important;
  margin-bottom: 0 !important;
}

div.st-key-metric_acq_cph div[data-testid="stMetricValue"] {
  color: #1d4ed8 !important;
}
div.st-key-metric_comp_cph div[data-testid="stMetricValue"] {
  color: #047857 !important;
}
div.st-key-metric_overall_cph div[data-testid="stMetricValue"] {
  color: #dc2626 !important;
}

.goal-caskets-label {
  white-space: nowrap !important;
  display: inline-block;
  margin: 0 0 0.24rem 0;
}
.goal-caskets-label--spacer {
  visibility: hidden;
  user-select: none;
}
.goal-caskets-label p {
  margin: 0 !important;
  overflow-wrap: normal !important;
  word-break: keep-all !important;
}
div.st-key-btn_goal_start_point button {
  white-space: normal !important;
  overflow-wrap: anywhere !important;
  word-break: normal !important;
  text-overflow: clip !important;
}
div.st-key-btn_save_acq_trip button {
  background: var(--acq-save-bg) !important;
  border-color: var(--acq-save-border) !important;
  color: #f8fafc !important;
}
div.st-key-btn_save_acq_trip button:hover {
  background: var(--acq-save-hover) !important;
  border-color: #1e3a8a !important;
  color: #f8fafc !important;
}
div.st-key-btn_save_comp_session button {
  background: var(--comp-save-bg) !important;
  border-color: var(--comp-save-border) !important;
  color: #f8fafc !important;
}
div.st-key-btn_save_comp_session button:hover {
  background: var(--comp-save-hover) !important;
  border-color: #134e4a !important;
  color: #f8fafc !important;
}
div.st-key-btn_acq_clear_start button,
div.st-key-btn_acq_clear_end button,
div.st-key-btn_comp_clear_start button,
div.st-key-btn_comp_clear_end button {
  background: #dc2626 !important;
  border-color: #b91c1c !important;
  color: #f8fafc !important;
  min-height: 2rem !important;
  padding: 0.1rem 0.45rem !important;
  font-size: 0.74rem !important;
  font-weight: 600 !important;
}
div.st-key-btn_acq_clear_start button:hover,
div.st-key-btn_acq_clear_end button:hover,
div.st-key-btn_comp_clear_start button:hover,
div.st-key-btn_comp_clear_end button:hover {
  background: #b91c1c !important;
  border-color: #991b1b !important;
  color: #fef2f2 !important;
}
div.st-key-btn_acq_clear_start button p,
div.st-key-btn_acq_clear_end button p,
div.st-key-btn_comp_clear_start button p,
div.st-key-btn_comp_clear_end button p {
  font-size: 0.74rem !important;
}

#ui-overflow-tooltip-float {
  position: fixed;
  z-index: 2147483647;
  max-width: min(80vw, 64ch);
  width: max-content;
  white-space: normal;
  padding: 0.24rem 0.44rem;
  border-radius: 0.34rem;
  background: rgba(15, 23, 42, 0.96);
  color: #f8fafc;
  box-shadow: 0 8px 20px rgba(2, 6, 23, 0.34);
  line-height: 1.22;
  font-size: 0.77rem;
  pointer-events: none;
  opacity: 0;
  visibility: hidden;
  transform: translateY(2px);
  transition: opacity 45ms linear, transform 45ms ease;
}
#ui-overflow-tooltip-float[data-visible="1"] {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}

</style>
""",
    unsafe_allow_html=True,
)


# ----------------------------
# UI DOM polish
# ----------------------------


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
    _render_inline_html(
        """
        <script>
        const rootWin = (() => {
          try {
            if (window.parent && window.parent.document) return window.parent;
          } catch (_err) {}
          return window;
        })();
        const rootDoc = rootWin.document;
        const OVERFLOW_TOOLTIP_DELAY_MS = 50;
        let overflowTooltipEl = null;
        let overflowTooltipTimer = null;
        let overflowTooltipTarget = null;

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
            if (label === 'Start Now') {
              styleButton(button, { hoverBg: '#2f7d57', hoverBorder: '#256347', hoverTextColor: '#f8fafc' });
            }
            if (label === 'End Now') {
              styleButton(button, { hoverBg: '#b4534d', hoverBorder: '#8f413b', hoverTextColor: '#f8fafc' });
            }
          });
        }

        function isTextVisiblyTruncated(el) {
          if (!el) return false;
          const style = rootWin.getComputedStyle(el);
          const hasHorizontalTruncation = (el.scrollWidth - el.clientWidth) > 1;
          const lineClamp = Number.parseInt(style.webkitLineClamp || '', 10);
          const hasVerticalTruncation = Number.isFinite(lineClamp) && lineClamp > 0 && (el.scrollHeight - el.clientHeight) > 1;
          const isHidden = style.display === 'none' || style.visibility === 'hidden';
          if (isHidden) return false;
          return hasHorizontalTruncation || hasVerticalTruncation;
        }

        function ensureOverflowTooltipElement() {
          if (overflowTooltipEl && rootDoc.body.contains(overflowTooltipEl)) return overflowTooltipEl;
          overflowTooltipEl = rootDoc.getElementById('ui-overflow-tooltip-float');
          if (!overflowTooltipEl) {
            overflowTooltipEl = rootDoc.createElement('div');
            overflowTooltipEl.id = 'ui-overflow-tooltip-float';
            rootDoc.body.appendChild(overflowTooltipEl);
          }
          return overflowTooltipEl;
        }

        function clearOverflowTooltipTimer() {
          if (overflowTooltipTimer) {
            rootWin.clearTimeout(overflowTooltipTimer);
            overflowTooltipTimer = null;
          }
        }

        function hideOverflowTooltip() {
          clearOverflowTooltipTimer();
          const tooltip = ensureOverflowTooltipElement();
          tooltip.removeAttribute('data-visible');
          overflowTooltipTarget = null;
        }

        function positionOverflowTooltip(target) {
          if (!target) return;
          const tooltip = ensureOverflowTooltipElement();
          const margin = 8;
          const gap = 6;
          const rect = target.getBoundingClientRect();
          const tipRect = tooltip.getBoundingClientRect();

          let left = rect.left;
          if (left + tipRect.width + margin > rootWin.innerWidth) {
            left = rootWin.innerWidth - tipRect.width - margin;
          }
          left = Math.max(margin, left);

          let top = rect.bottom + gap;
          if (top + tipRect.height + margin > rootWin.innerHeight) {
            top = rect.top - tipRect.height - gap;
          }
          top = Math.max(margin, top);

          tooltip.style.left = `${Math.round(left)}px`;
          tooltip.style.top = `${Math.round(top)}px`;
        }

        function scheduleOverflowTooltip(target) {
          if (!target) return;
          const text = target.getAttribute('data-ui-overflow-tooltip');
          if (!text) return;
          clearOverflowTooltipTimer();
          overflowTooltipTimer = rootWin.setTimeout(() => {
            const tooltip = ensureOverflowTooltipElement();
            tooltip.textContent = text;
            tooltip.setAttribute('data-visible', '1');
            overflowTooltipTarget = target;
            positionOverflowTooltip(target);
            overflowTooltipTimer = null;
          }, OVERFLOW_TOOLTIP_DELAY_MS);
        }

        function bindOverflowTooltipHover() {
          if (rootDoc.body.dataset.uiOverflowTooltipHoverBound === '1') return;
          rootDoc.body.dataset.uiOverflowTooltipHoverBound = '1';

          rootDoc.addEventListener('mouseover', (event) => {
            const candidate = event.target instanceof Element
              ? event.target.closest('[data-ui-overflow-tooltip]')
              : null;
            if (!candidate) return;
            if (overflowTooltipTarget === candidate) {
              positionOverflowTooltip(candidate);
              return;
            }
            hideOverflowTooltip();
            scheduleOverflowTooltip(candidate);
          }, true);

          rootDoc.addEventListener('mouseout', (event) => {
            const source = event.target instanceof Element
              ? event.target.closest('[data-ui-overflow-tooltip]')
              : null;
            if (!source) return;
            const related = event.relatedTarget;
            if (related instanceof Element && source.contains(related)) return;
            clearOverflowTooltipTimer();
            if (overflowTooltipTarget === source) hideOverflowTooltip();
          }, true);

          rootDoc.addEventListener('scroll', () => {
            if (overflowTooltipTarget) positionOverflowTooltip(overflowTooltipTarget);
          }, true);
          rootDoc.addEventListener('mousedown', hideOverflowTooltip, true);
          rootDoc.addEventListener('keydown', hideOverflowTooltip, true);
        }

        function applyOverflowTooltips() {
          const selector = [
            '[data-testid="stMetricLabel"] p',
            '[data-testid="stMetricValue"]',
            '[data-testid="stCaptionContainer"] p',
            '[data-testid="stTabs"] button [data-testid="stMarkdownContainer"] p',
            '[data-testid="stTabs"] button p',
            '.stMarkdown p',
            '.stMarkdown span'
          ].join(', ');

          rootDoc.querySelectorAll(selector).forEach((el) => {
            const text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
            if (!text) {
              el.removeAttribute('data-ui-overflow-tooltip');
              if (overflowTooltipTarget === el) hideOverflowTooltip();
              return;
            }
            if (isTextVisiblyTruncated(el)) {
              el.setAttribute('data-ui-overflow-tooltip', text);
            } else {
              el.removeAttribute('data-ui-overflow-tooltip');
              if (overflowTooltipTarget === el) hideOverflowTooltip();
            }
          });
        }

        function run() {
          applyButtonStyles();
          applyOverflowTooltips();
          bindOverflowTooltipHover();
        }

        run();
        if (!rootDoc.body.dataset.uiOverflowTooltipResizeBound) {
          rootDoc.body.dataset.uiOverflowTooltipResizeBound = '1';
          rootWin.addEventListener('resize', () => {
            rootWin.requestAnimationFrame(run);
            if (overflowTooltipTarget) positionOverflowTooltip(overflowTooltipTarget);
          });
        }
        const observer = new MutationObserver(run);
        observer.observe(rootDoc.body, { childList: true, subtree: true });
        </script>
        """,
        height=0
    )


def clamp_nonnegative_int(value: Any, default: int = 0) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError):
        out = default
    return max(0, out)


def parse_iso_datetime(raw: Any) -> datetime | None:
    if raw in (None, ""):
        return None
    try:
        dt = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TIMEZONE)
    return dt.astimezone(LOCAL_TIMEZONE)


def parse_iso_date(raw: Any) -> date | None:
    if raw in (None, ""):
        return None
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None


def clamp_positive_int(value: Any, default: int) -> int:
    return max(1, clamp_nonnegative_int(value, default=default))


def parse_optional_nonnegative_int(raw: Any) -> int | None:
    if raw in (None, ""):
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def normalize_draft_text(value: Any) -> str:
    return "" if value in (None, "") else str(value)


def normalize_draft_date(value: Any, default: date | None = None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    parsed = parse_iso_date(value)
    if parsed is not None:
        return parsed
    return default


def normalize_draft_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=LOCAL_TIMEZONE)
        return dt.astimezone(LOCAL_TIMEZONE)
    return parse_iso_datetime(value)


def load_acq_logger_state() -> tuple[Dict[str, Any], str | None]:
    try:
        df = gsb.read_sheet_df(ACQ_LOGGER_STATE_SHEET, list(ACQ_LOGGER_STATE_COLS))
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
        df = gsb.read_sheet_df(COMP_LOGGER_STATE_SHEET, list(COMP_LOGGER_STATE_COLS))
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
    gsb.replace_sheet(ACQ_LOGGER_STATE_SHEET, list(ACQ_LOGGER_STATE_COLS), state_df)


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
    gsb.replace_sheet(COMP_LOGGER_STATE_SHEET, list(COMP_LOGGER_STATE_COLS), state_df)


def load_goal_progress_state() -> Dict[str, Any]:
    try:
        df = gsb.read_sheet_df(GOAL_PROGRESS_STATE_SHEET, list(GOAL_PROGRESS_STATE_COLS))
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
    gsb.replace_sheet(GOAL_PROGRESS_STATE_SHEET, list(GOAL_PROGRESS_STATE_COLS), state_df)


def normalize_goal_caskets(value: Any) -> int:
    return max(1, clamp_nonnegative_int(value, default=GOAL_CASKETS))


def load_goal_settings_state() -> Dict[str, Any]:
    try:
        df = gsb.read_sheet_df(GOAL_SETTINGS_SHEET, list(GOAL_SETTINGS_COLS))
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
    gsb.replace_sheet(GOAL_SETTINGS_SHEET, list(GOAL_SETTINGS_COLS), state_df)


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


def human_gp_or_na(x: Any) -> str:
    if x is None or pd.isna(x):
        return "N/A"
    return human_gp(float(x))



def fmt_hours_minutes(total_seconds: float) -> str:
    total_seconds = int(round(float(total_seconds or 0)))
    total_seconds = max(0, total_seconds)
    if total_seconds < 3600:
        mins = total_seconds // 60
        secs = total_seconds % 60
        return f"{mins}m {secs:02d}s"
    hours = total_seconds // 3600
    mins = (total_seconds % 3600) // 60
    return f"{hours}h {mins:02d}m"



def seconds_to_metric_duration(total_seconds: float) -> str:
    return fmt_hours_minutes(total_seconds)


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


def today_local():
    return now_local().date()


def resolve_session_log_date(
    selected_date: Any,
    *,
    start_system: datetime | None = None,
    end_system: datetime | None = None,
    used_system_duration: bool = False,
) -> date:
    normalized_date = normalize_draft_date(selected_date, default=today_local()) or today_local()
    if used_system_duration:
        if end_system is not None:
            return end_system.astimezone(LOCAL_TIMEZONE).date()
        if start_system is not None:
            return start_system.astimezone(LOCAL_TIMEZONE).date()
    return normalized_date



@st.cache_data(show_spinner=False)
def load_df(sheet_name: str, columns: tuple[str, ...], session_cache_key: str) -> pd.DataFrame:
    df = gsb.read_sheet_df(sheet_name, list(columns))
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



def append_row(sheet_name: str, columns: tuple[str, ...], row: Dict[str, Any]) -> None:
    gsb.append_row(sheet_name, list(columns), row)



def rolling_mean(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=1).mean()


def coerce_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


ADJUSTED_END_TO_END_COLUMNS = (
    "adjusted_acquire_minutes_per_casket",
    "adjusted_complete_minutes_per_casket",
    "adjusted_total_minutes_per_casket",
    "adjusted_end_to_end_caskets_per_hour",
    "adjusted_acquire_same_day_share",
    "adjusted_complete_same_day_share",
    "adjusted_acquire_baseline_caskets",
    "adjusted_complete_baseline_caskets",
)


def exp_weighted_activity_count(counts: pd.Series, span: int) -> pd.Series:
    qty = pd.to_numeric(counts, errors="coerce")
    valid = qty.notna() & (qty > 0)
    if not valid.any():
        return pd.Series(float("nan"), index=counts.index)

    active_counts = qty[valid].astype(float)
    active_ewma = active_counts.ewm(span=max(1, int(span)), adjust=False).mean()
    return active_ewma.reindex(counts.index).ffill()


def sample_adjusted_component(
    raw_minutes: pd.Series,
    recent_minutes: pd.Series,
    same_day_count: pd.Series,
    prior_recent_count: pd.Series,
    prior_recent_minutes: pd.Series,
) -> tuple[pd.Series, pd.Series]:
    raw = pd.to_numeric(raw_minutes, errors="coerce")
    recent = pd.to_numeric(recent_minutes, errors="coerce")
    qty = pd.to_numeric(same_day_count, errors="coerce").fillna(0.0)
    baseline_qty = pd.to_numeric(prior_recent_count, errors="coerce")
    baseline_minutes = pd.to_numeric(prior_recent_minutes, errors="coerce")

    adjusted = recent.copy()
    same_day_share = pd.Series(0.0, index=raw.index, dtype=float)
    has_activity = raw.notna() & (qty > 0)
    has_baseline = baseline_minutes.notna() & baseline_qty.notna() & (baseline_qty > 0)

    blend = has_activity & has_baseline
    adjusted.loc[blend] = (
        (raw.loc[blend] * qty.loc[blend])
        + (baseline_minutes.loc[blend] * baseline_qty.loc[blend])
    ).div(qty.loc[blend] + baseline_qty.loc[blend])
    same_day_share.loc[blend] = qty.loc[blend].div(qty.loc[blend] + baseline_qty.loc[blend])

    raw_only = has_activity & ~has_baseline
    adjusted.loc[raw_only] = raw.loc[raw_only]
    same_day_share.loc[raw_only] = 1.0

    return adjusted, same_day_share


def minutes_to_caskets_per_hour_series(minutes_per_casket: pd.Series) -> pd.Series:
    values = pd.to_numeric(minutes_per_casket, errors="coerce")
    return 60.0 / values.where(values > 0)


def ensure_adjusted_end_to_end_columns(trend_df: pd.DataFrame) -> pd.DataFrame:
    if trend_df.empty or all(col in trend_df.columns for col in ADJUSTED_END_TO_END_COLUMNS):
        return trend_df

    d = trend_df.copy()
    for col in ("acq_caskets", "comp_caskets"):
        if col not in d.columns:
            d[col] = 0.0
        d[col] = pd.to_numeric(d[col], errors="coerce").fillna(0.0)

    if "recent_acq_caskets_per_day" not in d.columns:
        d["recent_acq_caskets_per_day"] = exp_weighted_activity_count(
            d["acq_caskets"],
            END_TO_END_RECENT_ACQ_EWMA_SPAN,
        )
    if "recent_comp_caskets_per_day" not in d.columns:
        d["recent_comp_caskets_per_day"] = exp_weighted_activity_count(
            d["comp_caskets"],
            END_TO_END_RECENT_COMP_EWMA_SPAN,
        )

    d["adjusted_acquire_baseline_caskets"] = d["recent_acq_caskets_per_day"].shift(1)
    d["adjusted_complete_baseline_caskets"] = d["recent_comp_caskets_per_day"].shift(1)
    d["adjusted_acquire_minutes_per_casket"], d["adjusted_acquire_same_day_share"] = (
        sample_adjusted_component(
            d.get("raw_acquire_minutes_per_casket", pd.Series(float("nan"), index=d.index)),
            d.get("recent_acquire_minutes_per_casket", pd.Series(float("nan"), index=d.index)),
            d["acq_caskets"],
            d["adjusted_acquire_baseline_caskets"],
            d.get("recent_acquire_minutes_per_casket", pd.Series(float("nan"), index=d.index)).shift(1),
        )
    )
    d["adjusted_complete_minutes_per_casket"], d["adjusted_complete_same_day_share"] = (
        sample_adjusted_component(
            d.get("raw_complete_minutes_per_casket", pd.Series(float("nan"), index=d.index)),
            d.get("recent_complete_minutes_per_casket", pd.Series(float("nan"), index=d.index)),
            d["comp_caskets"],
            d["adjusted_complete_baseline_caskets"],
            d.get("recent_complete_minutes_per_casket", pd.Series(float("nan"), index=d.index)).shift(1),
        )
    )
    d["adjusted_total_minutes_per_casket"] = (
        d["adjusted_acquire_minutes_per_casket"] + d["adjusted_complete_minutes_per_casket"]
    )
    d["adjusted_end_to_end_caskets_per_hour"] = minutes_to_caskets_per_hour_series(
        d["adjusted_total_minutes_per_casket"]
    )
    return d


def make_chart_legend_below(y: float | None = None, chart_height: int | None = None) -> dict:
    if y is None:
        y = PRIMARY_LEGEND_Y
    return dict(orientation="h", yanchor="top", y=y, xanchor="center", x=0.5)


def make_line_layout(
    title: str,
    x_title: str,
    y_title: str,
    y2_title: str | None = None,
    height: int = 380,
    legend_y: float | None = None,
) -> dict:
    layout = dict(
        title=title,
        height=height,
        margin=dict(l=40, r=40, t=CHART_TOP_MARGIN, b=LINE_CHART_BOTTOM_MARGIN),
        legend=make_chart_legend_below(y=legend_y, chart_height=height),
        xaxis=dict(
            title=dict(text=x_title, standoff=24),
            automargin=True,
            showline=True,
            linecolor="rgba(148, 163, 184, 0.42)",
            ticks="outside",
            ticklen=5,
            tickcolor="rgba(148, 163, 184, 0.42)",
        ),
        yaxis=dict(
            title=y_title,
            showline=True,
            linecolor="rgba(148, 163, 184, 0.42)",
            ticks="outside",
            ticklen=5,
            tickcolor="rgba(148, 163, 184, 0.42)",
        ),
    )
    if y2_title is not None:
        layout["yaxis2"] = dict(title=y2_title, overlaying="y", side="right")
    return layout


def scale_marker_sizes(
    weights: pd.Series,
    min_size: float = 6.0,
    max_size: float = 28.0,
    max_weight: float | None = None,
) -> list[float]:
    vals = pd.to_numeric(weights, errors="coerce").fillna(0.0).clip(lower=0.0)
    positive = vals[vals > 0]
    if positive.empty:
        return [min_size] * len(vals)

    size_max = float(max_weight) if max_weight and max_weight > 0 else float(positive.max())
    size_max = max(size_max, float(positive.max()))
    scale = positive.div(size_max)

    sizes = pd.Series(min_size, index=vals.index, dtype=float)
    sizes.loc[positive.index] = min_size + scale * (max_size - min_size)
    return sizes.tolist()


def render_accent_metric(container: Any, label: str, value: Any, key: str) -> None:
    try:
        metric_container = container.container(key=key)
    except TypeError:
        metric_container = container.container()
    metric_container.metric(label, value)


def minutes_to_hhmm(total_minutes: float) -> str:
    return seconds_to_hhmm(float(total_minutes or 0) * 60.0)


def minutes_to_metric_duration(total_minutes: float) -> str:
    return fmt_hours_minutes(float(total_minutes or 0) * 60.0)


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
    d["gp_cost_per_clue"] = d["gp_spent_per_clue"]
    d["clues_per_hour"] = d["clues_per_hour"].where(d["clues_per_hour"].notna(), d["clues"].div(hours))
    # A logged acquisition trip still qualifies for jelly-drop EV, even if drops
    # (for example, a Skotizo blood-rune hit) make the net blood delta negative.
    d["eligible_for_acquisition_income"] = d["bloods_used"].notna()
    eligible_flag = d["eligible_for_acquisition_income"].astype(float)

    d["rune_armor_gp_per_kill"] = RUNE_ARMOR_GP_PER_KILL * eligible_flag
    d["rune_armor_gp_per_clue"] = RUNE_ARMOR_GP_PER_CLUE * eligible_flag
    d["chaos_runes_per_kill"] = CHAOS_RUNES_PER_KILL * eligible_flag
    d["chaos_rune_gp_per_kill"] = CHAOS_RUNE_GP_PER_KILL * eligible_flag
    d["chaos_rune_gp_per_clue"] = CHAOS_RUNE_GP_PER_CLUE * eligible_flag
    d["death_runes_per_kill"] = DEATH_RUNES_PER_KILL * eligible_flag
    d["death_rune_gp_per_kill"] = DEATH_RUNE_GP_PER_KILL * eligible_flag
    d["death_rune_gp_per_clue"] = DEATH_RUNE_GP_PER_CLUE * eligible_flag
    d["combined_acquisition_gp_income_per_clue"] = (
        d["rune_armor_gp_per_clue"] + d["chaos_rune_gp_per_clue"] + d["death_rune_gp_per_clue"]
    )
    d["net_gp_per_clue_acquired"] = d["combined_acquisition_gp_income_per_clue"] - d["gp_cost_per_clue"]

    clue_counts = d["clues"].where(d["clues"] > 0, 0).fillna(0)
    d["expected_kills"] = clue_counts * JELLY_KILLS_PER_HARD_CLUE
    d["expected_rune_armor_gp"] = clue_counts * d["rune_armor_gp_per_clue"]
    d["expected_chaos_rune_gp"] = clue_counts * d["chaos_rune_gp_per_clue"]
    d["expected_death_rune_gp"] = clue_counts * d["death_rune_gp_per_clue"]
    d["expected_combined_acquisition_gp_income"] = (
        d["expected_rune_armor_gp"] + d["expected_chaos_rune_gp"] + d["expected_death_rune_gp"]
    )
    d["expected_net_gp_trip_acquisition"] = d["expected_combined_acquisition_gp_income"] - d["gp_cost"]

    d["rolling_10_trip_avg_minutes_per_clue"] = rolling_weighted_ratio(
        d["duration_seconds"] / 60.0,
        d["clues"],
        10,
    )
    d["rolling_10_trip_avg_clues_per_hour"] = rolling_weighted_ratio(
        d["clues"],
        d["duration_seconds"] / 3600.0,
        10,
    )
    d["rolling_10_trip_avg_gp_cost_per_clue"] = rolling_weighted_ratio(d["gp_cost"], d["clues"], 10)
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
    d["rolling_10_session_avg_minutes_per_casket"] = rolling_weighted_ratio(
        d["duration_seconds"] / 60.0,
        d["clues_completed"],
        10,
    )
    d["rolling_10_session_avg_caskets_per_hour"] = rolling_weighted_ratio(
        d["clues_completed"],
        d["duration_seconds"] / 3600.0,
        10,
    )
    d["duration"] = d["duration_seconds"].apply(seconds_to_hhmm)
    d["log_date"] = d["log_date"].dt.date
    return d


def build_range_histogram(
    series: pd.Series,
    title: str,
    x_title: str,
    y_title: str,
    height: int = SECONDARY_HISTOGRAM_HEIGHT,
) -> go.Figure:
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

    fig.add_trace(
        go.Bar(
            x=labels,
            y=counts,
            name="Count",
            marker_color="#4f46e5",
            text=counts,
            textposition="outside",
            texttemplate="%{text}",
            cliponaxis=False,
        )
    )
    fig.update_layout(
        title=title,
        height=height,
        margin=dict(l=40, r=20, t=CHART_TOP_MARGIN, b=HISTOGRAM_BOTTOM_MARGIN),
        xaxis=dict(
            title=x_title,
            showline=True,
            linecolor="rgba(148, 163, 184, 0.42)",
            ticks="outside",
            ticklen=5,
            tickcolor="rgba(148, 163, 184, 0.42)",
        ),
        yaxis=dict(
            title=y_title,
            showline=True,
            linecolor="rgba(148, 163, 184, 0.42)",
            ticks="outside",
            ticklen=5,
            tickcolor="rgba(148, 163, 184, 0.42)",
        ),
        showlegend=False,
    )
    return fig


def build_acq_clues_per_hour_chart(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["trip_id", "clues_per_hour"]).sort_values("trip_id").copy()
    fig = go.Figure()
    fig.update_layout(
        **make_line_layout("Clues per hour by trip", "Trip #", "Clues per hour", height=PRIMARY_PACE_CHART_HEIGHT)
    )
    if d.empty:
        return fig

    fig.add_trace(
        go.Scatter(
            x=d["trip_id"],
            y=d["clues_per_hour"],
            mode="lines+markers",
            name="Clues per hour",
            line=dict(color="#1d4ed8", width=3),
            marker=dict(color="#1d4ed8", size=7),
            customdata=pd.DataFrame({"clues": d["clues"], "log_date": d["log_date"].astype(str)}),
            hovertemplate=(
                "Trip %{x}<br>Date: %{customdata[1]}"
                "<br>Clues/hr: %{y:.2f}"
                "<br>Clues obtained: %{customdata[0]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=d["trip_id"],
            y=d["rolling_10_trip_avg_clues_per_hour"],
            mode="lines",
            name="Rolling 10-trip avg",
            line=dict(color="#60a5fa", width=2.5, dash="dash"),
            hovertemplate="Rolling avg: %{y:.2f} clues/hr<extra></extra>",
        )
    )

    overall_avg = weighted_ratio(d["clues"], d["duration_seconds"] / 3600.0)
    fig.add_trace(
        go.Scatter(
            x=d["trip_id"],
            y=[overall_avg] * len(d),
            mode="lines",
            name="Overall avg",
            line=dict(color="#93c5fd", width=2, dash="dot"),
            hovertemplate="Overall avg: %{y:.2f} clues/hr<extra></extra>",
        )
    )
    return fig


def build_acq_profitability_chart(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["trip_id"]).sort_values("trip_id").copy()
    fig = go.Figure()
    fig.update_layout(
        **make_line_layout(
            "GP cost per clue by trip",
            "Trip #",
            "GP per clue",
            height=SECONDARY_DETAIL_CHART_HEIGHT,
            legend_y=SECONDARY_LEGEND_Y,
        )
    )
    if d.empty:
        return fig

    fig.add_trace(
        go.Scatter(
            x=d["trip_id"],
            y=d["gp_cost_per_clue"],
            mode="lines+markers",
            name="GP cost per clue",
            line=dict(color="#b45309", width=2.5),
            marker=dict(color="#b45309", size=6),
            customdata=pd.DataFrame({"clues": d["clues"], "log_date": d["log_date"].astype(str)}),
            hovertemplate=(
                "Trip %{x}<br>Date: %{customdata[1]}"
                "<br>GP cost/clue: %{y:,.0f}"
                "<br>Clues obtained: %{customdata[0]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=d["trip_id"],
            y=d["rolling_10_trip_avg_gp_cost_per_clue"],
            mode="lines",
            name="Rolling 10-trip avg",
            line=dict(color="#f59e0b", width=2.5, dash="dash"),
            hovertemplate="Trip %{x}<br>Rolling GP cost/clue: %{y:,.0f}<extra></extra>",
        )
    )

    overall_avg = weighted_ratio(d["gp_cost"], d["clues"])
    fig.add_trace(
        go.Scatter(
            x=d["trip_id"],
            y=[overall_avg] * len(d),
            mode="lines",
            name="Overall avg",
            line=dict(color="#fde68a", width=2, dash="dot"),
            hovertemplate="Trip %{x}<br>Overall GP cost/clue: %{y:,.0f}<extra></extra>",
        )
    )
    return fig


def build_completion_minutes_per_casket_chart(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["session_id", "minutes_per_casket"]).sort_values("session_id").copy()
    fig = go.Figure()
    fig.update_layout(
        **make_line_layout(
            "Minutes per casket by session",
            "Session #",
            "Minutes per casket",
            height=SECONDARY_DETAIL_CHART_HEIGHT,
            legend_y=SECONDARY_LEGEND_Y,
        )
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

    overall_avg = weighted_ratio(d["duration_seconds"] / 60.0, d["clues_completed"])
    fig.add_trace(
        go.Scatter(
            x=d["session_id"],
            y=[overall_avg] * len(d),
            mode="lines",
            name="Overall avg",
            line=dict(color="#99f6e4", width=2, dash="dot"),
            hovertemplate="Overall avg: %{y:.2f} min/casket<extra></extra>",
        )
    )
    return fig


def build_completion_caskets_per_hour_chart(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["session_id", "caskets_per_hour"]).sort_values("session_id").copy()
    fig = go.Figure()
    fig.update_layout(
        **make_line_layout(
            "Caskets per hour by session",
            "Session #",
            "Caskets per hour",
            height=PRIMARY_PACE_CHART_HEIGHT,
        )
    )
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
            customdata=pd.DataFrame(
                {
                    "clues_completed": d["clues_completed"],
                    "log_date": d["log_date"].astype(str),
                }
            ),
            hovertemplate=(
                "Session %{x}<br>Date: %{customdata[1]}"
                "<br>Caskets/hr: %{y:.2f}"
                "<br>Caskets completed: %{customdata[0]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=d["session_id"],
            y=d["rolling_10_session_avg_caskets_per_hour"],
            mode="lines",
            name="Rolling 10-session avg",
            line=dict(color="#6ee7b7", width=2.5, dash="dash"),
            hovertemplate="Rolling avg: %{y:.2f} caskets/hr<extra></extra>",
        )
    )

    overall_avg = weighted_ratio(d["clues_completed"], d["duration_seconds"] / 3600.0)
    fig.add_trace(
        go.Scatter(
            x=d["session_id"],
            y=[overall_avg] * len(d),
            mode="lines",
            name="Overall avg",
            line=dict(color="#a7f3d0", width=2, dash="dot"),
            hovertemplate="Overall avg: %{y:.2f} caskets/hr<extra></extra>",
        )
    )
    return fig


def build_completion_caskets_completed_chart(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["session_id", "clues_completed"]).sort_values("session_id").copy()
    fig = go.Figure()
    fig.update_layout(
        **make_line_layout(
            "Caskets completed by session",
            "Session #",
            "Caskets completed",
            height=SECONDARY_DETAIL_CHART_HEIGHT,
            legend_y=SECONDARY_LEGEND_Y,
        )
    )
    if d.empty:
        return fig

    d["rolling_10_session_avg_caskets_completed"] = rolling_mean(
        pd.to_numeric(d["clues_completed"], errors="coerce"),
        10,
    )

    fig.add_trace(
        go.Scatter(
            x=d["session_id"],
            y=d["clues_completed"],
            mode="lines+markers",
            name="Caskets completed",
            line=dict(color="#059669", width=3),
            marker=dict(color="#059669", size=7),
            customdata=pd.DataFrame({"log_date": d["log_date"].astype(str)}),
            hovertemplate=(
                "Session %{x}<br>Date: %{customdata[0]}"
                "<br>Caskets completed: %{y:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=d["session_id"],
            y=d["rolling_10_session_avg_caskets_completed"],
            mode="lines",
            name="Rolling 10-session avg",
            line=dict(color="#6ee7b7", width=2.5, dash="dash"),
            hovertemplate="Rolling avg: %{y:.2f} caskets/session<extra></extra>",
        )
    )

    overall_avg = float(pd.to_numeric(d["clues_completed"], errors="coerce").dropna().mean())
    fig.add_trace(
        go.Scatter(
            x=d["session_id"],
            y=[overall_avg] * len(d),
            mode="lines",
            name="Overall avg",
            line=dict(color="#a7f3d0", width=2, dash="dot"),
            hovertemplate="Overall avg: %{y:.2f} caskets/session<extra></extra>",
        )
    )
    return fig


def build_end_to_end_time_breakdown_pie(end_to_end_sum: Dict[str, Any]) -> go.Figure:
    fig = go.Figure()
    acquire_minutes = float(end_to_end_sum.get("acquire_minutes_per_casket") or 0.0)
    complete_minutes = float(end_to_end_sum.get("complete_minutes_per_casket") or 0.0)

    labels = ["Acquisition time", "Completion time"]
    values = [max(0.0, acquire_minutes), max(0.0, complete_minutes)]
    if sum(values) <= 0:
        fig.update_layout(title="Time per casket split", height=360)
        return fig

    fig.add_trace(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.35,
            sort=False,
            marker=dict(colors=["#1d4ed8", "#0f766e"]),
            textinfo="percent",
            texttemplate="%{percent:.1%}",
            hovertemplate="%{label}<br>%{value:.2f} min (%{percent:.1%})<extra></extra>",
        )
    )
    fig.update_layout(
        title="Time per casket split",
        height=430,
        margin=dict(l=20, r=20, t=90, b=95),
        legend=make_chart_legend_below(y=-0.08),
    )
    return fig


def build_end_to_end_cph_chart(trend_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        **make_line_layout(
            "End-to-end caskets per hour",
            "Date",
            "Caskets per hour",
            height=PRIMARY_PACE_CHART_HEIGHT,
        )
    )
    if trend_df.empty:
        return fig

    max_raw_weight = float(
        max(
            pd.to_numeric(trend_df["raw_total_same_day_weight"], errors="coerce").fillna(0.0).max(),
            pd.to_numeric(trend_df["acq_caskets"], errors="coerce").fillna(0.0).max(),
            pd.to_numeric(trend_df["comp_caskets"], errors="coerce").fillna(0.0).max(),
        )
    )
    raw_total_sizes = scale_marker_sizes(
        trend_df["raw_total_same_day_weight"],
        min_size=9.0,
        max_size=32.0,
        max_weight=max_raw_weight,
    )
    raw_acq_sizes = scale_marker_sizes(
        trend_df["acq_caskets"],
        min_size=7.0,
        max_size=28.0,
        max_weight=max_raw_weight,
    )
    raw_comp_sizes = scale_marker_sizes(
        trend_df["comp_caskets"],
        min_size=7.0,
        max_size=28.0,
        max_weight=max_raw_weight,
    )
    hover_raw_total_data = trend_df[
        [
            "adjusted_acquire_minutes_per_casket",
            "adjusted_complete_minutes_per_casket",
            "adjusted_acquire_same_day_share",
            "adjusted_complete_same_day_share",
            "acq_caskets",
            "comp_caskets",
            "raw_total_same_day_weight",
        ]
    ]
    hover_span_data = trend_df[["recent_acq_ewma_span", "recent_comp_ewma_span"]]
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            name="Adjusted daily total",
            hoverinfo="skip",
            marker=dict(
                size=11,
                color="rgba(220, 38, 38, 0)",
                line=dict(color="rgba(220, 38, 38, 0.40)", width=1.5),
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["adjusted_end_to_end_caskets_per_hour"],
            mode="markers",
            name="Adjusted daily total",
            showlegend=False,
            marker=dict(
                size=raw_total_sizes,
                color="rgba(220, 38, 38, 0)",
                line=dict(color="rgba(220, 38, 38, 0.40)", width=1.5),
            ),
            customdata=hover_raw_total_data,
            hovertemplate=(
                "%{x}<br>Adjusted daily pace: %{y:.4f} caskets/hr"
                "<br>Adjusted acquisition: %{customdata[0]:.4f} min/clue"
                "<br>Adjusted completion: %{customdata[1]:.4f} min/casket"
                "<br>Acquisition same-day weight: %{customdata[2]:.0%} from %{customdata[4]:.0f} clues"
                "<br>Completion same-day weight: %{customdata[3]:.0%} from %{customdata[5]:.0f} caskets"
                "<br>Date's total marker weight: %{customdata[6]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["recent_end_to_end_caskets_per_hour"],
            mode="lines+markers",
            name="Recent overall",
            line=dict(color="#dc2626", width=3),
            marker=dict(color="#dc2626", size=7),
            customdata=hover_span_data,
            hovertemplate=(
                "%{x}<br>Recent overall: %{y:.2f} caskets/hr"
                "<br>Acquisition EWMA span: %{customdata[0]:.0f}"
                "<br>Completion EWMA span: %{customdata[1]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["raw_acquire_caskets_per_hour"],
            mode="markers",
            name="Raw acquisition point",
            showlegend=False,
            marker=dict(
                size=raw_acq_sizes,
                color="rgba(29, 78, 216, 0)",
                line=dict(color="rgba(29, 78, 216, 0.38)", width=1.5),
            ),
            customdata=trend_df[["acq_caskets"]],
            hovertemplate=(
                "%{x}<br>Raw acquisition pace: %{y:.4f} clues/hr"
                "<br>Clues logged on this date: %{customdata[0]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["recent_acquire_caskets_per_hour"],
            mode="lines+markers",
            name="Recent acquisition",
            line=dict(color="#1d4ed8", width=2.5),
            marker=dict(color="#1d4ed8", size=6),
            hovertemplate="%{x}<br>Recent acquisition pace: %{y:.2f} clues/hr<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["raw_complete_caskets_per_hour"],
            mode="markers",
            name="Raw completion point",
            showlegend=False,
            marker=dict(
                size=raw_comp_sizes,
                color="rgba(15, 118, 110, 0)",
                line=dict(color="rgba(15, 118, 110, 0.38)", width=1.5),
            ),
            customdata=trend_df[["comp_caskets"]],
            hovertemplate=(
                "%{x}<br>Raw completion pace: %{y:.4f} caskets/hr"
                "<br>Caskets logged on this date: %{customdata[0]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["recent_complete_caskets_per_hour"],
            mode="lines+markers",
            name="Recent completion",
            line=dict(color="#0f766e", width=2.5),
            marker=dict(color="#0f766e", size=6),
            hovertemplate="%{x}<br>Recent completion pace: %{y:.2f} caskets/hr<extra></extra>",
        )
    )
    y_values = pd.concat(
        [
            trend_df["adjusted_end_to_end_caskets_per_hour"],
            trend_df["recent_end_to_end_caskets_per_hour"],
            trend_df["raw_acquire_caskets_per_hour"],
            trend_df["recent_acquire_caskets_per_hour"],
            trend_df["raw_complete_caskets_per_hour"],
            trend_df["recent_complete_caskets_per_hour"],
            trend_df["all_time_end_to_end_caskets_per_hour"],
        ],
        axis=0,
    ).dropna()
    yaxis_config = dict(
        title="Caskets per hour",
        automargin=True,
        showline=True,
        linecolor="rgba(148, 163, 184, 0.42)",
        ticks="outside",
        ticklen=5,
        tickcolor="rgba(148, 163, 184, 0.42)",
    )
    if not y_values.empty:
        y_min = float(y_values.min())
        y_max = float(y_values.max())
        span = max(y_max - y_min, 0.01)
        pad = max(span * 0.06, 0.08)
        if span <= 1.5:
            dtick = 0.25
        elif span <= 3.0:
            dtick = 0.5
        else:
            dtick = 1.0
        y_lower = max(0.0, math.floor((y_min - pad) / dtick) * dtick)
        y_upper = math.ceil((y_max + pad) / dtick) * dtick
        if y_upper <= y_lower:
            y_upper = y_lower + dtick
        yaxis_config.update(range=[y_lower, y_upper], tickmode="linear", dtick=dtick)
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["all_time_end_to_end_caskets_per_hour"],
            mode="lines",
            name="Overall average",
            line=dict(color="#64748b", width=2.5, dash="dot"),
            hovertemplate="%{x}<br>Overall average: %{y:.4f} caskets/hr<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=40, r=40, t=64, b=165),
        legend=make_chart_legend_below(chart_height=PRIMARY_PACE_CHART_HEIGHT),
        xaxis=dict(
            title=dict(text="Date", standoff=END_TO_END_X_TITLE_STANDOFF),
            type="category",
            tickangle=-35,
            automargin=True,
            categoryorder="array",
            categoryarray=trend_df["date_label"].tolist(),
            showline=True,
            linecolor="rgba(148, 163, 184, 0.42)",
            ticks="outside",
            ticklen=5,
            tickcolor="rgba(148, 163, 184, 0.42)",
        ),
        yaxis=yaxis_config,
    )
    return fig


def build_end_to_end_deviation_chart(trend_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    chart_height = SECONDARY_DETAIL_CHART_HEIGHT
    fig.update_layout(
        title="End-to-end daily deviation",
        height=chart_height,
        margin=dict(l=40, r=40, t=CHART_TOP_MARGIN, b=LINE_CHART_BOTTOM_MARGIN),
        legend=make_chart_legend_below(y=SECONDARY_LEGEND_Y, chart_height=chart_height),
        barmode="overlay",
        bargap=0.28,
        xaxis=dict(
            title=dict(text="Date", standoff=44),
            type="category",
            tickangle=-35,
            automargin=True,
            categoryorder="array",
            categoryarray=trend_df["date_label"].tolist() if "date_label" in trend_df else [],
            showline=False,
            ticks="",
        ),
        yaxis=dict(
            title="Deviation from benchmark",
            ticksuffix="%",
            zeroline=False,
            showline=True,
            linecolor="rgba(148, 163, 184, 0.42)",
            ticks="outside",
            ticklen=5,
            tickcolor="rgba(148, 163, 184, 0.42)",
        ),
    )
    if trend_df.empty:
        return fig

    d = trend_df.copy()
    adjusted_cph = pd.to_numeric(d["adjusted_end_to_end_caskets_per_hour"], errors="coerce")
    recent_cph = pd.to_numeric(d["recent_end_to_end_caskets_per_hour"], errors="coerce")
    overall_cph = pd.to_numeric(d["all_time_end_to_end_caskets_per_hour"], errors="coerce")
    d["recent_deviation_pct"] = (adjusted_cph.div(recent_cph.where(recent_cph > 0)) - 1.0) * 100.0
    d["overall_deviation_pct"] = (adjusted_cph.div(overall_cph.where(overall_cph > 0)) - 1.0) * 100.0
    d["adjusted_cph"] = adjusted_cph
    d["recent_cph"] = recent_cph
    d["overall_cph"] = overall_cph
    d["adjusted_minutes"] = pd.to_numeric(d["adjusted_total_minutes_per_casket"], errors="coerce")
    d["recent_minutes"] = pd.to_numeric(d["recent_total_minutes_per_casket"], errors="coerce")
    d["overall_minutes"] = pd.to_numeric(d["all_time_total_minutes_per_casket"], errors="coerce")
    d["same_day_weight"] = pd.to_numeric(d["raw_total_same_day_weight"], errors="coerce").fillna(0.0)
    d["acq_caskets"] = pd.to_numeric(d["acq_caskets"], errors="coerce").fillna(0.0)
    d["comp_caskets"] = pd.to_numeric(d["comp_caskets"], errors="coerce").fillna(0.0)
    d["acq_same_day_share"] = (
        pd.to_numeric(d["adjusted_acquire_same_day_share"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    )
    d["comp_same_day_share"] = (
        pd.to_numeric(d["adjusted_complete_same_day_share"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    )

    recent_acq_minutes = pd.to_numeric(d["recent_acquire_minutes_per_casket"], errors="coerce")
    recent_comp_minutes = pd.to_numeric(d["recent_complete_minutes_per_casket"], errors="coerce")
    recent_component_total = recent_acq_minutes + recent_comp_minutes
    d["acq_time_share"] = recent_acq_minutes.div(recent_component_total.where(recent_component_total > 0))
    d["comp_time_share"] = recent_comp_minutes.div(recent_component_total.where(recent_component_total > 0))

    adjusted_acq_minutes = pd.to_numeric(d["adjusted_acquire_minutes_per_casket"], errors="coerce")
    adjusted_comp_minutes = pd.to_numeric(d["adjusted_complete_minutes_per_casket"], errors="coerce")
    adjusted_component_total = adjusted_acq_minutes + adjusted_comp_minutes
    d["acq_time_share"] = d["acq_time_share"].where(
        d["acq_time_share"].notna(),
        adjusted_acq_minutes.div(adjusted_component_total.where(adjusted_component_total > 0)),
    )
    d["comp_time_share"] = d["comp_time_share"].where(
        d["comp_time_share"].notna(),
        adjusted_comp_minutes.div(adjusted_component_total.where(adjusted_component_total > 0)),
    )
    d["acq_time_share"] = d["acq_time_share"].fillna(0.0).clip(0.0, 1.0)
    d["comp_time_share"] = d["comp_time_share"].fillna(0.0).clip(0.0, 1.0)
    d["same_day_confidence"] = (
        (d["acq_same_day_share"] * d["acq_time_share"])
        + (d["comp_same_day_share"] * d["comp_time_share"])
    ).fillna(0.0).clip(0.0, 1.0)
    visible_confidence = d["same_day_confidence"].where(d["recent_deviation_pct"].notna()).dropna()
    min_alpha = 0.18
    if visible_confidence.empty:
        weight_alpha = pd.Series(min_alpha, index=d.index, dtype=float)
    else:
        min_confidence = float(visible_confidence.min())
        max_confidence = float(visible_confidence.max())
        if max_confidence > min_confidence:
            confidence_ratio = d["same_day_confidence"].sub(min_confidence).div(max_confidence - min_confidence)
            confidence_ratio = confidence_ratio.clip(0.0, 1.0).fillna(0.0)
            weight_alpha = (min_alpha + (1.0 - min_alpha) * confidence_ratio.pow(0.85)).clip(min_alpha, 1.0)
        else:
            weight_alpha = pd.Series(1.0, index=d.index, dtype=float)
    positive_colors = [f"rgba(22, 163, 74, {alpha:.3f})" for alpha in weight_alpha]
    negative_colors = [f"rgba(225, 29, 72, {alpha:.3f})" for alpha in weight_alpha]

    positive = d["recent_deviation_pct"].where(d["recent_deviation_pct"] >= 0)
    negative = d["recent_deviation_pct"].where(d["recent_deviation_pct"] < 0)
    hover_data = d[
        [
            "adjusted_cph",
            "recent_cph",
            "overall_cph",
            "overall_deviation_pct",
            "adjusted_minutes",
            "recent_minutes",
            "overall_minutes",
            "recent_deviation_pct",
            "same_day_confidence",
            "acq_caskets",
            "comp_caskets",
            "acq_same_day_share",
            "comp_same_day_share",
            "acq_time_share",
            "comp_time_share",
            "same_day_weight",
        ]
    ]
    hover_template = (
        "%{x}"
        "<br>Vs recent EWMA: %{y:.2f}% (positive means faster than recent)"
        "<br>Adjusted daily pace: %{customdata[0]:.4f} caskets/hr (sample-adjusted day estimate)"
        "<br>Recent EWMA pace: %{customdata[1]:.4f} caskets/hr (recent trend benchmark)"
        "<br>Vs overall average: %{customdata[3]:.2f}% (day estimate vs all-time pace)"
        "<br>Overall average: %{customdata[2]:.4f} caskets/hr (all logged data)"
        "<br>Adjusted total: %{customdata[4]:.2f} min/casket (day estimate in minutes)"
        "<br>Recent total: %{customdata[5]:.2f} min/casket (recent benchmark in minutes)"
        "<br>Overall total: %{customdata[6]:.2f} min/casket (all-time benchmark in minutes)"
        "<br>Daily confidence: %{customdata[8]:.0%} (controls bar opacity)"
        "<br>Acquired clues: %{customdata[9]:.0f} (same-day acquisition count)"
        "<br>Completed caskets: %{customdata[10]:.0f} (same-day completion count)"
        "<br>Acq same-day share: %{customdata[11]:.0%} (how much today's acquisition sample counts)"
        "<br>Acq time share: %{customdata[13]:.0%} (acquisition share of recent total time)"
        "<br>Comp same-day share: %{customdata[12]:.0%} (how much today's completion sample counts)"
        "<br>Comp time share: %{customdata[14]:.0%} (completion share of recent total time)"
        "<br>Logged activity count: %{customdata[15]:.0f} (raw clues+caskets context)<extra></extra>"
    )

    fig.add_trace(
        go.Bar(
            x=d["date_label"],
            y=positive,
            name="Better than recent",
            marker=dict(color=positive_colors),
            customdata=hover_data,
            hovertemplate=hover_template,
        )
    )
    fig.add_trace(
        go.Bar(
            x=d["date_label"],
            y=negative,
            name="Slower than recent",
            marker=dict(color=negative_colors),
            customdata=hover_data,
            hovertemplate=hover_template,
        )
    )
    fig.add_shape(
        type="line",
        xref="paper",
        x0=0,
        x1=1,
        yref="y",
        y0=0,
        y1=0,
        layer="above",
        line=dict(color="#ffffff", width=0.75),
    )

    y_values = d["recent_deviation_pct"].dropna()
    if not y_values.empty:
        max_abs = max(abs(float(y_values.min())), abs(float(y_values.max())))
        padded = max(max_abs * 1.18, 2.0)
        if padded <= 6:
            dtick = 1.0
        elif padded <= 15:
            dtick = 2.5
        elif padded <= 30:
            dtick = 5.0
        else:
            dtick = 10.0
        axis_bound = math.ceil(padded / dtick) * dtick
        fig.update_yaxes(range=[-axis_bound, axis_bound], tickmode="linear", dtick=dtick)

    return fig


def build_end_to_end_minutes_chart(trend_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        **make_line_layout("End-to-end minutes per casket", "Date", "Minutes per casket", height=420)
    )
    if trend_df.empty:
        return fig

    max_raw_weight = float(
        max(
            pd.to_numeric(trend_df["raw_total_same_day_weight"], errors="coerce").fillna(0.0).max(),
            pd.to_numeric(trend_df["acq_caskets"], errors="coerce").fillna(0.0).max(),
            pd.to_numeric(trend_df["comp_caskets"], errors="coerce").fillna(0.0).max(),
        )
    )
    raw_total_sizes = scale_marker_sizes(
        trend_df["raw_total_same_day_weight"],
        min_size=8.0,
        max_size=20.0,
        max_weight=max_raw_weight,
    )
    raw_acq_sizes = scale_marker_sizes(
        trend_df["acq_caskets"],
        min_size=7.0,
        max_size=18.0,
        max_weight=max_raw_weight,
    )
    raw_comp_sizes = scale_marker_sizes(
        trend_df["comp_caskets"],
        min_size=7.0,
        max_size=18.0,
        max_weight=max_raw_weight,
    )
    hover_span_data = trend_df[["recent_acq_ewma_span", "recent_comp_ewma_span"]]
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["adjusted_total_minutes_per_casket"],
            mode="markers",
            name="Adjusted daily total",
            marker=dict(
                size=raw_total_sizes,
                color="rgba(220, 38, 38, 0)",
                line=dict(color="rgba(220, 38, 38, 0.40)", width=1.5),
            ),
            customdata=trend_df[
                [
                    "adjusted_acquire_minutes_per_casket",
                    "adjusted_complete_minutes_per_casket",
                    "adjusted_acquire_same_day_share",
                    "adjusted_complete_same_day_share",
                    "acq_caskets",
                    "comp_caskets",
                    "raw_total_same_day_weight",
                ]
            ],
            hovertemplate=(
                "%{x}<br>Adjusted daily total: %{y:.4f} min/casket"
                "<br>Adjusted acquisition: %{customdata[0]:.4f} min/clue"
                "<br>Adjusted completion: %{customdata[1]:.4f} min/casket"
                "<br>Acquisition same-day weight: %{customdata[2]:.0%} from %{customdata[4]:.0f} clues"
                "<br>Completion same-day weight: %{customdata[3]:.0%} from %{customdata[5]:.0f} caskets"
                "<br>Total marker weight: %{customdata[6]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["recent_total_minutes_per_casket"],
            mode="lines+markers",
            name="Recent total (EWMA)",
            line=dict(color="#dc2626", width=3),
            marker=dict(color="#dc2626", size=7),
            customdata=hover_span_data,
            hovertemplate=(
                "%{x}<br>Recent total: %{y:.2f} min/casket"
                "<br>Acquisition EWMA span: %{customdata[0]:.0f}"
                "<br>Completion EWMA span: %{customdata[1]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["raw_acquire_minutes_per_casket"],
            mode="markers",
            name="Raw acquisition point",
            marker=dict(
                size=raw_acq_sizes,
                color="rgba(29, 78, 216, 0)",
                line=dict(color="rgba(29, 78, 216, 0.38)", width=1.5),
            ),
            customdata=trend_df[["acq_caskets"]],
            hovertemplate=(
                "%{x}<br>Raw acquisition: %{y:.4f} min/clue"
                "<br>Acquired clues: %{customdata[0]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["recent_acquire_minutes_per_casket"],
            mode="lines",
            name="Recent acquisition (EWMA)",
            line=dict(color="#1d4ed8", width=2.5),
            hovertemplate="%{x}<br>Recent acquisition: %{y:.2f} min/clue<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["raw_complete_minutes_per_casket"],
            mode="markers",
            name="Raw completion point",
            marker=dict(
                size=raw_comp_sizes,
                color="rgba(15, 118, 110, 0)",
                line=dict(color="rgba(15, 118, 110, 0.38)", width=1.5),
            ),
            customdata=trend_df[["comp_caskets"]],
            hovertemplate=(
                "%{x}<br>Raw completion: %{y:.4f} min/casket"
                "<br>Completed caskets: %{customdata[0]:.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["recent_complete_minutes_per_casket"],
            mode="lines",
            name="Recent completion (EWMA)",
            line=dict(color="#0f766e", width=2.5),
            hovertemplate="%{x}<br>Recent completion: %{y:.2f} min/casket<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["all_time_total_minutes_per_casket"],
            mode="lines",
            name="Overall average",
            line=dict(color="#64748b", width=2.5, dash="dot"),
            hovertemplate="%{x}<br>Overall average: %{y:.4f} min/casket<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=40, r=40, t=64, b=120),
        legend=make_chart_legend_below(),
        xaxis=dict(
            title="Date",
            type="category",
            categoryorder="array",
            categoryarray=trend_df["date_label"].tolist(),
        )
    )
    return fig


def build_end_to_end_income_source_pie(end_to_end_sum: Dict[str, Any]) -> go.Figure:
    fig = go.Figure()
    rune_gp = float(end_to_end_sum.get("rune_armor_gp_per_clue") or 0.0)
    chaos_gp = float(end_to_end_sum.get("chaos_rune_gp_per_clue") or 0.0)
    death_gp = float(end_to_end_sum.get("death_rune_gp_per_clue") or 0.0)
    alch_gp = float(end_to_end_sum.get("expected_income_per_casket_alch") or 0.0)

    labels = [
        "Rune armor drops",
        "Chaos runes",
        "Death runes",
        "Casket alch rewards",
    ]
    values = [max(0.0, rune_gp), max(0.0, chaos_gp), max(0.0, death_gp), max(0.0, alch_gp)]
    if sum(values) <= 0:
        fig.update_layout(title="Estimated GP sources per casket", height=360)
        return fig

    fig.add_trace(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.35,
            sort=False,
            textinfo="percent",
            texttemplate="%{percent:.1%}",
            hovertemplate="%{label}<br>%{percent:.1%}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Estimated GP sources per casket",
        height=430,
        margin=dict(l=20, r=20, t=90, b=95),
        legend=make_chart_legend_below(y=-0.08),
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


ss_init()
apply_pending_before_widgets()
goal_caskets = normalize_goal_caskets(st.session_state.get("goal_caskets", GOAL_CASKETS))
st.session_state["goal_caskets"] = goal_caskets


# ----------------------------
# Summaries
# ----------------------------
def summarize_acq(df: pd.DataFrame, goal_caskets: int) -> Dict[str, Any]:
    if df.empty:
        return {}
    d = coerce_numeric(df, ["clues", "duration_seconds", "gp_cost", "bloods_used"]).copy()
    total_trips = len(d)
    total_clues = int(d["clues"].fillna(0).sum())
    total_seconds = float(d["duration_seconds"].fillna(0).sum())
    total_gp = float(d["gp_cost"].fillna(0).sum())
    total_bloods = float(d["bloods_used"].fillna(0).sum())
    eligible_income_clues = float(d.loc[d["bloods_used"].notna(), "clues"].fillna(0).sum())

    avg_seconds_per_trip = float(d["duration_seconds"].dropna().mean()) if d["duration_seconds"].notna().any() else 0.0
    avg_seconds_per_clue = total_seconds / total_clues if total_clues > 0 else 0.0
    avg_gp_per_clue = total_gp / total_clues if total_clues > 0 else 0.0
    avg_bloods_per_clue = total_bloods / total_clues if total_clues > 0 else 0.0

    total_hours = total_seconds / 3600 if total_seconds > 0 else 0.0
    clues_per_hour = total_clues / total_hours if total_hours > 0 else 0.0
    gp_per_hour = total_gp / total_hours if total_hours > 0 else 0.0

    gp_cost_per_clue = total_gp / total_clues if total_clues > 0 else float("nan")
    total_expected_rune_armor_gp = eligible_income_clues * RUNE_ARMOR_GP_PER_CLUE
    total_expected_chaos_rune_gp = eligible_income_clues * CHAOS_RUNE_GP_PER_CLUE
    total_expected_death_rune_gp = eligible_income_clues * DEATH_RUNE_GP_PER_CLUE
    total_expected_combined_acquisition_gp_income = (
        total_expected_rune_armor_gp + total_expected_chaos_rune_gp + total_expected_death_rune_gp
    )
    rune_armor_gp_per_clue = total_expected_rune_armor_gp / total_clues if total_clues > 0 else float("nan")
    chaos_rune_gp_per_clue = total_expected_chaos_rune_gp / total_clues if total_clues > 0 else float("nan")
    death_rune_gp_per_clue = total_expected_death_rune_gp / total_clues if total_clues > 0 else float("nan")
    combined_acquisition_gp_income_per_clue = (
        total_expected_combined_acquisition_gp_income / total_clues if total_clues > 0 else float("nan")
    )
    net_gp_per_clue_acquired = (
        combined_acquisition_gp_income_per_clue - gp_cost_per_clue if total_clues > 0 else float("nan")
    )
    total_expected_net_acquisition_gp = total_expected_combined_acquisition_gp_income - total_gp

    remaining = max(0, goal_caskets - total_clues)
    proj_seconds_remaining = remaining * avg_seconds_per_clue
    projected_rune_armor_gp_remaining = remaining * rune_armor_gp_per_clue
    projected_chaos_rune_gp_remaining = remaining * chaos_rune_gp_per_clue
    projected_death_rune_gp_remaining = remaining * death_rune_gp_per_clue
    projected_combined_acquisition_income_remaining = (
        projected_rune_armor_gp_remaining + projected_chaos_rune_gp_remaining + projected_death_rune_gp_remaining
    )
    projected_acquisition_cost_remaining = remaining * gp_cost_per_clue
    projected_net_acquisition_gp_remaining = (
        projected_combined_acquisition_income_remaining - projected_acquisition_cost_remaining
    )
    proj_gp_remaining = projected_acquisition_cost_remaining

    return {
        "total_trips": total_trips,
        "total_clues": total_clues,
        "avg_time_trip_s": avg_seconds_per_trip,
        "avg_time_clue_s": avg_seconds_per_clue,
        "avg_gp_per_clue": avg_gp_per_clue,
        "avg_bloods_per_clue": avg_bloods_per_clue,
        "clues_per_hour": clues_per_hour,
        "gp_per_hour": gp_per_hour,
        "eligible_income_clues": eligible_income_clues,
        "rune_armor_gp_per_clue": rune_armor_gp_per_clue,
        "chaos_rune_gp_per_clue": chaos_rune_gp_per_clue,
        "death_rune_gp_per_clue": death_rune_gp_per_clue,
        "combined_acquisition_gp_income_per_clue": combined_acquisition_gp_income_per_clue,
        "gp_cost_per_clue": gp_cost_per_clue,
        "net_gp_per_clue_acquired": net_gp_per_clue_acquired,
        "total_expected_rune_armor_gp": total_expected_rune_armor_gp,
        "total_expected_chaos_rune_gp": total_expected_chaos_rune_gp,
        "total_expected_death_rune_gp": total_expected_death_rune_gp,
        "total_expected_combined_acquisition_gp_income": total_expected_combined_acquisition_gp_income,
        "total_expected_net_acquisition_gp": total_expected_net_acquisition_gp,
        "remaining": remaining,
        "proj_time_remaining_s": proj_seconds_remaining,
        "proj_gp_remaining": proj_gp_remaining,
        "projected_rune_armor_gp_remaining": projected_rune_armor_gp_remaining,
        "projected_chaos_rune_gp_remaining": projected_chaos_rune_gp_remaining,
        "projected_death_rune_gp_remaining": projected_death_rune_gp_remaining,
        "projected_combined_acquisition_income_remaining": projected_combined_acquisition_income_remaining,
        "projected_acquisition_cost_remaining": projected_acquisition_cost_remaining,
        "projected_net_acquisition_gp_remaining": projected_net_acquisition_gp_remaining,
        "projected_net_gp_remaining_full_process": (
            projected_net_acquisition_gp_remaining + (remaining * EXPECTED_ALCH_GP_PER_CASKET)
        ),
    }



def summarize_comp(df: pd.DataFrame, goal_caskets: int) -> Dict[str, Any]:
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

    remaining = max(0, goal_caskets - total_completed)
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


def summarize_end_to_end(acq_sum: Dict[str, Any], comp_sum: Dict[str, Any], goal_caskets: int) -> Dict[str, Any]:
    if not acq_sum or not comp_sum:
        return {}

    acquire_minutes_per_clue = acq_sum["avg_time_clue_s"] / 60.0
    complete_minutes_per_casket = comp_sum["avg_time_casket_s"] / 60.0
    total_minutes_per_casket = acquire_minutes_per_clue + complete_minutes_per_casket
    end_to_end_caskets_per_hour = 60.0 / total_minutes_per_casket if total_minutes_per_casket > 0 else 0.0

    acquisition_share_of_total_time = (
        acquire_minutes_per_clue / total_minutes_per_casket if total_minutes_per_casket > 0 else 0.0
    )
    completion_share_of_total_time = (
        complete_minutes_per_casket / total_minutes_per_casket if total_minutes_per_casket > 0 else 0.0
    )

    expected_income_per_clue_acquisition = acq_sum["combined_acquisition_gp_income_per_clue"]
    expected_cost_per_clue_acquisition = acq_sum["gp_cost_per_clue"]
    net_gp_per_clue_on_acquisition = acq_sum["net_gp_per_clue_acquired"]
    expected_income_per_casket_alch = EXPECTED_ALCH_GP_PER_CASKET
    net_gp_per_casket = (
        net_gp_per_clue_on_acquisition + expected_income_per_casket_alch
        if not pd.isna(net_gp_per_clue_on_acquisition)
        else float("nan")
    )
    end_to_end_gp_per_hour = (
        net_gp_per_casket * end_to_end_caskets_per_hour if not pd.isna(net_gp_per_casket) else float("nan")
    )

    remaining_caskets = max(0, goal_caskets - int(acq_sum["total_clues"]))
    time_remaining_total_s = remaining_caskets * (acq_sum["avg_time_clue_s"] + comp_sum["avg_time_casket_s"])
    gp_cost_remaining = acq_sum["projected_acquisition_cost_remaining"]
    expected_alch_remaining = expected_income_per_casket_alch * remaining_caskets
    projected_net_acquisition_gp_remaining = acq_sum["projected_net_acquisition_gp_remaining"]
    expected_net_remaining = acq_sum["projected_net_gp_remaining_full_process"]

    if abs(acquire_minutes_per_clue - complete_minutes_per_casket) < 0.05:
        bottleneck = "Balanced"
    elif acquire_minutes_per_clue > complete_minutes_per_casket:
        bottleneck = "Acquisition"
    else:
        bottleneck = "Completion"

    return {
        "acquire_minutes_per_clue": acquire_minutes_per_clue,
        "acquire_minutes_per_casket": acquire_minutes_per_clue,
        "complete_minutes_per_casket": complete_minutes_per_casket,
        "total_minutes_per_casket": total_minutes_per_casket,
        "end_to_end_caskets_per_hour": end_to_end_caskets_per_hour,
        "acquisition_share_of_total_time": acquisition_share_of_total_time,
        "completion_share_of_total_time": completion_share_of_total_time,
        "end_to_end_gp_per_hour": end_to_end_gp_per_hour,
        "rune_armor_gp_per_clue": acq_sum["rune_armor_gp_per_clue"],
        "chaos_rune_gp_per_clue": acq_sum["chaos_rune_gp_per_clue"],
        "death_rune_gp_per_clue": acq_sum["death_rune_gp_per_clue"],
        "combined_acquisition_gp_income_per_clue": expected_income_per_clue_acquisition,
        "expected_cost_per_clue_acquisition": expected_cost_per_clue_acquisition,
        "expected_income_per_casket_alch": expected_income_per_casket_alch,
        "net_gp_per_clue_on_acquisition": net_gp_per_clue_on_acquisition,
        "net_gp_per_casket": net_gp_per_casket,
        "expected_net_gp_per_casket": net_gp_per_casket,
        "bottleneck": bottleneck,
        "time_remaining_total_s": time_remaining_total_s,
        "gp_cost_remaining": gp_cost_remaining,
        "expected_alch_remaining": expected_alch_remaining,
        "expected_net_remaining": expected_net_remaining,
        "projected_net_acquisition_gp_remaining": projected_net_acquisition_gp_remaining,
        "remaining_caskets": remaining_caskets,
    }


# ----------------------------
# Load data
# ----------------------------
SESSION_CACHE_KEY = get_session_cache_key()

acq_df = load_df(ACQ_SHEET, ACQ_COLS, SESSION_CACHE_KEY)
comp_df = load_df(COMP_SHEET, COMP_COLS, SESSION_CACHE_KEY)
acq_sum = summarize_acq(acq_df, goal_caskets)
comp_sum = summarize_comp(comp_df, goal_caskets)
acq_metrics_df = prepare_acq_metrics(acq_df)
comp_metrics_df = prepare_comp_metrics(comp_df)
end_to_end_sum = summarize_end_to_end(acq_sum, comp_sum, goal_caskets)
build_end_to_end_trend_params = inspect.signature(build_end_to_end_trend_df).parameters
if len(build_end_to_end_trend_params) >= 4:
    end_to_end_trend_df = build_end_to_end_trend_df(
        acq_df,
        comp_df,
        END_TO_END_RECENT_ACQ_EWMA_SPAN,
        END_TO_END_RECENT_COMP_EWMA_SPAN,
    )
else:
    # Guard hot-reload sessions where Streamlit reran the app against an older
    # imported helper that still expects the previous single-window signature.
    fallback_window = max(END_TO_END_RECENT_ACQ_EWMA_SPAN, END_TO_END_RECENT_COMP_EWMA_SPAN)
    end_to_end_trend_df = build_end_to_end_trend_df(acq_df, comp_df, fallback_window)
end_to_end_trend_df = ensure_adjusted_end_to_end_columns(end_to_end_trend_df)

running_acq_total = int(acq_sum.get("total_clues", 0))
running_comp_total = int(comp_sum.get("total_completed", 0))


def normalized_progress_baseline(raw_value: Any, running_total: int) -> int:
    baseline = clamp_nonnegative_int(raw_value, default=0)
    return min(running_total, baseline)


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


def set_goal_progress_start_point() -> None:
    start_set_at = now_local()
    st.session_state["goal_progress_start_acq_total"] = running_acq_total
    st.session_state["goal_progress_start_comp_total"] = running_comp_total
    st.session_state["goal_progress_start_set_at"] = start_set_at.isoformat()
    save_goal_progress_state(
        start_acq_total=running_acq_total,
        start_comp_total=running_comp_total,
        start_set_at=start_set_at,
    )


def persist_goal_caskets() -> None:
    normalized_goal = normalize_goal_caskets(st.session_state.get("goal_caskets", GOAL_CASKETS))
    st.session_state["goal_caskets"] = normalized_goal
    save_goal_settings_state(normalized_goal)


# ----------------------------
# Header
# ----------------------------
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
totals_col1.metric("Total clues acquired tracked", running_acq_total)
totals_col2.metric("Total caskets completed tracked", running_comp_total)

if progress_start_set_at is None:
    st.caption("Progress start point: not set yet (currently counting from all-time totals).")
else:
    st.caption(
        "Progress start point: "
        f"{progress_start_set_at.strftime('%Y-%m-%d %H:%M:%S %Z')} "
        f"(baseline: {progress_start_acq_total} acquired, {progress_start_comp_total} completed)"
    )

st.caption(
    f"Since start point: {acq_since_progress_start} clues acquired • {comp_since_progress_start} caskets completed"
    f" • {clues_on_ground_since_progress_start} clues stacked"
    f" ({fmt_hours_minutes(stacked_clues_completion_time_s)} to complete)"
)
st.caption(
    f"Goal window context: {acq_since_progress_start} / {goal_caskets} clues acquired • "
    f"{comp_since_progress_start} / {goal_caskets} caskets completed • "
    f"{goal_progress_remaining} caskets remaining"
)
st.progress(
    goal_progress,
    text=(
        f"Goal progress to {goal_caskets} caskets (completed since start): "
        f"{goal_progress_completed} / {goal_caskets} ({goal_progress * 100:.1f}%) • {goal_progress_remaining} remaining"
        f" • {clues_still_to_acquire_for_goal} still to acquire after stacked clues"
    ),
)
inject_ui_dom_script()


# ----------------------------
# Sidebar
# ----------------------------
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
        df = load_df(ACQ_SHEET, ACQ_COLS, SESSION_CACHE_KEY)
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
        df = load_df(COMP_SHEET, COMP_COLS, SESSION_CACHE_KEY)
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


# ----------------------------
# Tabs
# ----------------------------
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
        rolling = acq_metrics_df["rolling_10_trip_avg_minutes_per_clue"].dropna()
        rolling_latest = float(rolling.iloc[-1]) if not rolling.empty else 0.0
        rolling_best = float(rolling.min()) if not rolling.empty else 0.0
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
        t2.metric("Rolling 10-trip avg time / clue", minutes_to_metric_duration(rolling_latest))
        t3.metric("Median time / clue", minutes_to_metric_duration(median_minutes_per_clue))
        t4.metric("Best rolling 10-trip time / clue", minutes_to_metric_duration(rolling_best))
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
        rolling = comp_metrics_df["rolling_10_session_avg_minutes_per_casket"].dropna()
        rolling_latest = float(rolling.iloc[-1]) if not rolling.empty else 0.0
        rolling_best = float(rolling.min()) if not rolling.empty else 0.0
        median_minutes_per_casket = float(comp_metrics_df["minutes_per_casket"].dropna().median()) if comp_metrics_df["minutes_per_casket"].notna().any() else 0.0
        fastest_minutes_per_casket = float(comp_metrics_df["minutes_per_casket"].dropna().min()) if comp_metrics_df["minutes_per_casket"].notna().any() else 0.0
        slowest_minutes_per_casket = float(comp_metrics_df["minutes_per_casket"].dropna().max()) if comp_metrics_df["minutes_per_casket"].notna().any() else 0.0

        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("Sessions", int(comp_sum["total_sessions"]))
        k2.metric("Caskets completed logged", total_completed)
        k3.metric("Avg time / casket", seconds_to_metric_duration(comp_sum["avg_time_casket_s"]))
        render_accent_metric(k4, "Caskets / hour", f"{comp_sum['caskets_per_hour']:.2f}", "metric_comp_cph")
        k5.metric("Median time / casket", minutes_to_metric_duration(median_minutes_per_casket))
        k6.metric("Rolling 10-session avg time / casket", minutes_to_metric_duration(rolling_latest))

        st.divider()

        t1, t2, t3, t4, t5, t6 = st.columns(6)
        t1.metric("Avg session length", seconds_to_metric_duration(comp_sum["avg_time_session_s"]))
        t2.metric("Best rolling 10-session time / casket", minutes_to_metric_duration(rolling_best))
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
            f"Hollow circles are same-day points: blue shows raw acquisition, green shows raw completion, and red shows "
            f"a sample-adjusted daily total. Red blends each same-day component with its own recent EWMA baseline based "
            f"on that component's same-day count. The EWMA lines use "
            f"spans of {END_TO_END_RECENT_ACQ_EWMA_SPAN} acquisition dates and {END_TO_END_RECENT_COMP_EWMA_SPAN} "
            "completion dates, and they are causal, so older points do not change when newer data is added. If "
            "only one side is logged on a date, the other side uses its recent EWMA value once it exists. "
            "The dotted gray line is the flat overall weighted average across all logged data."
        )
