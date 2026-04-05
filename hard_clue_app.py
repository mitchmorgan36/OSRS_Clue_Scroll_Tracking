import os
import inspect
from datetime import datetime
from typing import Dict, Any
from urllib.parse import quote
from uuid import uuid4

from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

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
GOAL_HEADER_CONTROL_WIDTH_PX = 200
GOAL_HEADER_CONTROLS_CONTAINER_WIDTH_PX = (GOAL_HEADER_CONTROL_WIDTH_PX * 2) + 24

GOAL_PROGRESS_STATE_COLS = (
    "start_acq_total",
    "start_comp_total",
    "start_set_at",
)
GOAL_PROGRESS_STATE_SHEET = getattr(gsb, "GOAL_PROGRESS_STATE_SHEET", "goal_progress_state")

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

RUNE_ARMOR_GP_PER_KILL = (
    RUNE_ARMOR_GP_PER_QUALIFYING_DROP * RUNE_ARMOR_QUALIFYING_DROPS_PER_128_KILLS / 128
)
RUNE_ARMOR_GP_PER_CLUE = RUNE_ARMOR_GP_PER_KILL * JELLY_KILLS_PER_HARD_CLUE
CHAOS_RUNES_PER_KILL = CHAOS_RUNES_PER_DROP / CHAOS_DROP_KILLS_PER_DROP
CHAOS_RUNE_GP_PER_KILL = CHAOS_RUNES_PER_KILL * CHAOS_RUNE_GP
CHAOS_RUNE_GP_PER_CLUE = CHAOS_RUNE_GP_PER_KILL * JELLY_KILLS_PER_HARD_CLUE
COMBINED_ACQUISITION_GP_INCOME_PER_CLUE = RUNE_ARMOR_GP_PER_CLUE + CHAOS_RUNE_GP_PER_CLUE

# EV validation checks:
# - rune_armor_gp_per_kill = 28573 * 3 / 128 = 669.6796875
# - rune_armor_gp_per_clue = 669.6796875 * 60 = 40180.78125
# - chaos_runes_per_kill = 45 / 25.6 = 1.7578125
# - chaos_rune_gp_per_kill = 1.7578125 * 45 = 79.1015625
# - chaos_rune_gp_per_clue = 79.1015625 * 60 = 4746.09375
# - combined_acquisition_gp_income_per_clue = 40180.78125 + 4746.09375 = 44926.875
assert abs(RUNE_ARMOR_GP_PER_KILL - 669.6796875) < 1e-12
assert abs(RUNE_ARMOR_GP_PER_CLUE - 40180.78125) < 1e-12
assert abs(CHAOS_RUNES_PER_KILL - 1.7578125) < 1e-12
assert abs(CHAOS_RUNE_GP_PER_KILL - 79.1015625) < 1e-12
assert abs(CHAOS_RUNE_GP_PER_CLUE - 4746.09375) < 1e-12
assert abs(COMBINED_ACQUISITION_GP_INCOME_PER_CLUE - 44926.875) < 1e-12

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
            if (label === 'Save Acquisition Trip') {
              styleButton(button, { bg: '#1d4ed8', border: '#1e40af', textColor: '#f8fafc', hoverBg: '#1e40af', hoverBorder: '#1e3a8a', hoverTextColor: '#f8fafc' });
            }
            if (label === 'Save Completion Session') {
              styleButton(button, { bg: '#0f766e', border: '#115e59', textColor: '#f8fafc', hoverBg: '#115e59', hoverBorder: '#134e4a', hoverTextColor: '#f8fafc' });
            }
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


# ----------------------------
# Helpers
# ----------------------------
def ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)



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
    d["eligible_for_acquisition_income"] = d["bloods_used"].fillna(0) > 0
    eligible_flag = d["eligible_for_acquisition_income"].astype(float)

    d["rune_armor_gp_per_kill"] = RUNE_ARMOR_GP_PER_KILL * eligible_flag
    d["rune_armor_gp_per_clue"] = RUNE_ARMOR_GP_PER_CLUE * eligible_flag
    d["chaos_runes_per_kill"] = CHAOS_RUNES_PER_KILL * eligible_flag
    d["chaos_rune_gp_per_kill"] = CHAOS_RUNE_GP_PER_KILL * eligible_flag
    d["chaos_rune_gp_per_clue"] = CHAOS_RUNE_GP_PER_CLUE * eligible_flag
    d["combined_acquisition_gp_income_per_clue"] = d["rune_armor_gp_per_clue"] + d["chaos_rune_gp_per_clue"]
    d["net_gp_per_clue_acquired"] = d["combined_acquisition_gp_income_per_clue"] - d["gp_cost_per_clue"]

    clue_counts = d["clues"].where(d["clues"] > 0, 0).fillna(0)
    d["expected_kills"] = clue_counts * JELLY_KILLS_PER_HARD_CLUE
    d["expected_rune_armor_gp"] = clue_counts * d["rune_armor_gp_per_clue"]
    d["expected_chaos_rune_gp"] = clue_counts * d["chaos_rune_gp_per_clue"]
    d["expected_combined_acquisition_gp_income"] = (
        d["expected_rune_armor_gp"] + d["expected_chaos_rune_gp"]
    )
    d["expected_net_gp_trip_acquisition"] = d["expected_combined_acquisition_gp_income"] - d["gp_cost"]

    d["rolling_10_trip_avg_minutes_per_clue"] = d["minutes_per_clue"].rolling(window=10, min_periods=1).mean()
    d["rolling_10_trip_avg_gp_cost_per_clue"] = (
        d["gp_cost_per_clue"].rolling(window=10, min_periods=1).mean()
    )
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


def build_acq_profitability_chart(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["trip_id"]).sort_values("trip_id").copy()
    fig = go.Figure()
    fig.update_layout(
        **make_line_layout("Acquisition GP per clue profitability by trip", "Trip #", "GP per clue", height=360)
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
            x=d["trip_id"],
            y=d["gp_cost_per_clue"],
            mode="lines+markers",
            name="GP cost per clue",
            line=dict(color="#b45309", width=3),
            marker=dict(color="#b45309", size=7),
            hovertemplate="Trip %{x}<br>GP cost/clue: %{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=d["trip_id"],
            y=d["rolling_10_trip_avg_gp_cost_per_clue"],
            mode="lines",
            name="Rolling 10-trip avg GP cost per clue",
            line=dict(color="#7c2d12", width=3, dash="dash"),
            hovertemplate="Trip %{x}<br>Rolling GP cost/clue: %{y:,.0f}<extra></extra>",
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
    d["rolling_5_day_end_to_end_caskets_per_hour"] = (
        d["end_to_end_caskets_per_hour"].rolling(window=5, min_periods=1).mean()
    )
    d["rolling_5_day_total_minutes_per_casket"] = (
        d["total_minutes_per_casket"].rolling(window=5, min_periods=1).mean()
    )
    d["date_label"] = d["date"].dt.strftime("%Y-%m-%d")
    return d


def build_end_to_end_time_breakdown_pie(end_to_end_sum: Dict[str, Any]) -> go.Figure:
    fig = go.Figure()
    acquire_minutes = float(end_to_end_sum.get("acquire_minutes_per_casket") or 0.0)
    complete_minutes = float(end_to_end_sum.get("complete_minutes_per_casket") or 0.0)

    labels = ["Acquisition time", "Completion time"]
    values = [max(0.0, acquire_minutes), max(0.0, complete_minutes)]
    if sum(values) <= 0:
        fig.update_layout(title="Time breakdown per casket", height=360)
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
        title="Time breakdown per casket",
        height=430,
        margin=dict(l=20, r=20, t=90, b=95),
        legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="center", x=0.5),
    )
    return fig


def build_end_to_end_cph_chart(trend_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(**make_line_layout("Total caskets per hour", "Date", "Caskets per hour", height=380))
    if trend_df.empty:
        return fig

    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["end_to_end_caskets_per_hour"],
            mode="lines+markers",
            name="End-to-end caskets/hr",
            line=dict(color="#dc2626", width=3),
            marker=dict(color="#dc2626", size=7),
            hovertemplate="%{x}<br>End-to-end caskets/hr: %{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["rolling_5_day_end_to_end_caskets_per_hour"],
            mode="lines",
            name="Rolling 5-day avg",
            line=dict(color="#f87171", width=3, dash="dash"),
            hovertemplate="%{x}<br>Rolling 5-day caskets/hr: %{y:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=40, r=40, t=48, b=88),
        legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="center", x=0.5),
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
        **make_line_layout("Total minutes per casket", "Date", "Minutes per casket", height=340)
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
    fig.add_trace(
        go.Scatter(
            x=trend_df["date_label"],
            y=trend_df["rolling_5_day_total_minutes_per_casket"],
            mode="lines",
            name="Rolling 5-day avg",
            line=dict(color="#a78bfa", width=3, dash="dash"),
            hovertemplate="%{x}<br>Rolling 5-day min/casket: %{y:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=40, r=40, t=48, b=88),
        legend=dict(orientation="h", yanchor="top", y=-0.28, xanchor="center", x=0.5),
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
    alch_gp = float(end_to_end_sum.get("expected_income_per_casket_alch") or 0.0)

    labels = [
        "GP from rune armor drops",
        "GP from chaos runes",
        "GP from alching casket rewards",
    ]
    values = [max(0.0, rune_gp), max(0.0, chaos_gp), max(0.0, alch_gp)]
    if sum(values) <= 0:
        fig.update_layout(title="Income source share toward net GP per casket", height=360)
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
        title="Income source share toward net GP per casket",
        height=430,
        margin=dict(l=20, r=20, t=90, b=95),
        legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="center", x=0.5),
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

    st.session_state.setdefault("acq_start_system", None)
    st.session_state.setdefault("acq_end_system", None)
    st.session_state.setdefault("comp_start_system", None)
    st.session_state.setdefault("comp_end_system", None)

    st.session_state.setdefault("w_acq_date", today_local())
    st.session_state.setdefault("w_acq_start_play", "")
    st.session_state.setdefault("w_acq_end_play", "")
    st.session_state.setdefault("w_acq_start_blood", None)
    st.session_state.setdefault("w_acq_end_blood", None)
    st.session_state.setdefault("w_acq_clues", DEFAULT_CLUES_PER_TRIP)
    st.session_state.setdefault("w_acq_notes", "")

    st.session_state.setdefault("w_comp_date", today_local())
    st.session_state.setdefault("w_comp_start_play", "")
    st.session_state.setdefault("w_comp_end_play", "")
    st.session_state.setdefault("w_comp_completed", 10)
    st.session_state.setdefault("w_comp_notes", "")

    st.session_state.setdefault("pending_apply", False)
    st.session_state.setdefault("pending", {})
    st.session_state.setdefault("goal_caskets", GOAL_CASKETS)
    st.session_state.setdefault("goal_progress_start_acq_total", goal_progress_state.get("start_acq_total"))
    st.session_state.setdefault("goal_progress_start_comp_total", goal_progress_state.get("start_comp_total"))
    st.session_state.setdefault("goal_progress_start_set_at", goal_progress_state.get("start_set_at"))



def apply_pending_before_widgets() -> None:
    if st.session_state.get("pending_apply") and isinstance(st.session_state.get("pending"), dict):
        for k, v in st.session_state["pending"].items():
            st.session_state[k] = v
        st.session_state["pending"] = {}
        st.session_state["pending_apply"] = False


ss_init()
apply_pending_before_widgets()
goal_caskets = int(st.session_state.get("goal_caskets", GOAL_CASKETS))


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
    eligible_income_clues = float(d.loc[d["bloods_used"].fillna(0) > 0, "clues"].fillna(0).sum())

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
    total_expected_combined_acquisition_gp_income = total_expected_rune_armor_gp + total_expected_chaos_rune_gp
    rune_armor_gp_per_clue = total_expected_rune_armor_gp / total_clues if total_clues > 0 else float("nan")
    chaos_rune_gp_per_clue = total_expected_chaos_rune_gp / total_clues if total_clues > 0 else float("nan")
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
    projected_combined_acquisition_income_remaining = (
        projected_rune_armor_gp_remaining + projected_chaos_rune_gp_remaining
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
        "combined_acquisition_gp_income_per_clue": combined_acquisition_gp_income_per_clue,
        "gp_cost_per_clue": gp_cost_per_clue,
        "net_gp_per_clue_acquired": net_gp_per_clue_acquired,
        "total_expected_rune_armor_gp": total_expected_rune_armor_gp,
        "total_expected_chaos_rune_gp": total_expected_chaos_rune_gp,
        "total_expected_combined_acquisition_gp_income": total_expected_combined_acquisition_gp_income,
        "total_expected_net_acquisition_gp": total_expected_net_acquisition_gp,
        "remaining": remaining,
        "proj_time_remaining_s": proj_seconds_remaining,
        "proj_gp_remaining": proj_gp_remaining,
        "projected_rune_armor_gp_remaining": projected_rune_armor_gp_remaining,
        "projected_chaos_rune_gp_remaining": projected_chaos_rune_gp_remaining,
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

acq_df = load_df(ACQ_CSV, ACQ_COLS, SESSION_CACHE_KEY)
comp_df = load_df(COMP_CSV, COMP_COLS, SESSION_CACHE_KEY)
acq_sum = summarize_acq(acq_df, goal_caskets)
comp_sum = summarize_comp(comp_df, goal_caskets)
acq_metrics_df = prepare_acq_metrics(acq_df)
comp_metrics_df = prepare_comp_metrics(comp_df)
end_to_end_sum = summarize_end_to_end(acq_sum, comp_sum, goal_caskets)
end_to_end_trend_df = build_end_to_end_trend_df(acq_df, comp_df)

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

acq_goal_remaining = max(0, goal_caskets - acq_since_progress_start)
comp_goal_remaining = max(0, goal_caskets - comp_since_progress_start)
acq_goal_time_remaining_s = acq_goal_remaining * float(acq_sum.get("avg_time_clue_s", 0.0) or 0.0)
comp_goal_time_remaining_s = comp_goal_remaining * float(comp_sum.get("avg_time_casket_s", 0.0) or 0.0)
combo_goal_remaining = comp_goal_remaining
combo_goal_time_remaining_s = combo_goal_remaining * (
    float(acq_sum.get("avg_time_clue_s", 0.0) or 0.0)
    + float(comp_sum.get("avg_time_casket_s", 0.0) or 0.0)
)
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
)
st.progress(
    goal_progress,
    text=(
        f"Goal progress to {goal_caskets} caskets (completed since start): "
        f"{goal_progress_completed} / {goal_caskets} ({goal_progress * 100:.1f}%) • {goal_progress_remaining} remaining"
    ),
)
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
        st.button("Start Now", on_click=acq_start_now, width="stretch", key="btn_acq_start")
    with acq_btn_col2:
        st.button("End Now", on_click=acq_end_now, width="stretch", key="btn_acq_end")

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
        acq_submit = st.form_submit_button("Save Acquisition Trip", type="primary", width="stretch")

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
        st.button("Start Now", on_click=comp_start_now, width="stretch", key="btn_comp_start")
    with comp_btn_col2:
        st.button("End Now", on_click=comp_end_now, width="stretch", key="btn_comp_end")

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
        comp_submit = st.form_submit_button("Save Completion Session", type="primary", width="stretch")

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
    acq_rune_gp_per_clue = acq_sum.get("rune_armor_gp_per_clue", RUNE_ARMOR_GP_PER_CLUE) if acq_sum else RUNE_ARMOR_GP_PER_CLUE
    acq_chaos_gp_per_clue = acq_sum.get("chaos_rune_gp_per_clue", CHAOS_RUNE_GP_PER_CLUE) if acq_sum else CHAOS_RUNE_GP_PER_CLUE
    acq_combined_gp_income_per_clue = (
        acq_sum.get("combined_acquisition_gp_income_per_clue", COMBINED_ACQUISITION_GP_INCOME_PER_CLUE)
        if acq_sum
        else COMBINED_ACQUISITION_GP_INCOME_PER_CLUE
    )
    acq_gp_cost_per_clue = acq_sum.get("gp_cost_per_clue") if acq_sum else float("nan")
    acq_net_gp_per_clue = acq_sum.get("net_gp_per_clue_acquired") if acq_sum else float("nan")

    p1, p2, p3, p4, p5 = st.columns(5)
    p1.metric("GP per clue from rune armor drops", human_gp_or_na(acq_rune_gp_per_clue))
    p2.metric("GP per clue from Chaos rune drops", human_gp_or_na(acq_chaos_gp_per_clue))
    p3.metric("Combined acquisition GP income per clue", human_gp_or_na(acq_combined_gp_income_per_clue))
    p4.metric("GP cost per clue", human_gp_or_na(acq_gp_cost_per_clue))
    p5.metric("Net GP per clue acquired", human_gp_or_na(acq_net_gp_per_clue))

    st.divider()

    if acq_df.empty:
        st.info("No acquisition trips logged yet.")
    else:
        total = int(acq_sum["total_clues"])
        remaining = int(acq_goal_remaining)
        rolling = acq_metrics_df["rolling_10_trip_avg_minutes_per_clue"].dropna()
        rolling_latest = float(rolling.iloc[-1]) if not rolling.empty else 0.0
        rolling_best = float(rolling.min()) if not rolling.empty else 0.0
        median_minutes_per_clue = float(acq_metrics_df["minutes_per_clue"].dropna().median()) if acq_metrics_df["minutes_per_clue"].notna().any() else 0.0

        st.caption(
            f"Goal window: {acq_since_progress_start} / {goal_caskets} clues acquired since start point • "
            f"{remaining} remaining (lifetime total: {total})"
        )

        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("Trips", int(acq_sum["total_trips"]))
        k2.metric("Clues logged", total)
        k3.metric("Avg time / clue", seconds_to_metric_duration(acq_sum["avg_time_clue_s"]))
        k4.metric("Clues / hour", f"{acq_sum['clues_per_hour']:.2f}")
        k5.metric("Bloods / clue", f"{acq_sum['avg_bloods_per_clue']:.2f}")
        k6.metric("GP spent / clue", human_gp_or_na(acq_sum["avg_gp_per_clue"]))

        st.divider()

        t1, t2, t3, t4, t5, t6 = st.columns(6)
        t1.metric("Avg trip length", seconds_to_metric_duration(acq_sum["avg_time_trip_s"]))
        t2.metric("Rolling 10-trip avg time / clue", minutes_to_metric_duration(rolling_latest))
        t3.metric("Median time / clue", minutes_to_metric_duration(median_minutes_per_clue))
        t4.metric("Best rolling 10-trip time / clue", minutes_to_metric_duration(rolling_best))
        t5.metric("Time remaining (acquire)", fmt_hours_minutes(acq_goal_time_remaining_s))
        t6.metric("Remaining caskets", remaining)

        st.divider()
        st.subheader("Charts")
        st.plotly_chart(build_acq_minutes_per_clue_chart(acq_metrics_df), width="stretch")

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

        st.caption(
            f"Goal window: {comp_since_progress_start} / {goal_caskets} caskets completed since start point • "
            f"{remaining} remaining (lifetime total: {total_completed})"
        )

        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("Sessions", int(comp_sum["total_sessions"]))
        k2.metric("Caskets completed logged", total_completed)
        k3.metric("Avg time / casket", seconds_to_metric_duration(comp_sum["avg_time_casket_s"]))
        k4.metric("Caskets / hour", f"{comp_sum['caskets_per_hour']:.2f}")
        k5.metric("Median time / casket", minutes_to_metric_duration(median_minutes_per_casket))
        k6.metric("Rolling 10-session avg time / casket", minutes_to_metric_duration(rolling_latest))

        st.divider()

        t1, t2, t3, t4, t5, t6 = st.columns(6)
        t1.metric("Avg session length", seconds_to_metric_duration(comp_sum["avg_time_session_s"]))
        t2.metric("Best rolling 10-session time / casket", minutes_to_metric_duration(rolling_best))
        t3.metric("Fastest session time / casket", minutes_to_metric_duration(fastest_minutes_per_casket))
        t4.metric("Slowest session time / casket", minutes_to_metric_duration(slowest_minutes_per_casket))
        t5.metric("Time remaining (complete)", fmt_hours_minutes(comp_goal_time_remaining_s))
        t6.metric(f"Remaining to {goal_caskets} (complete)", remaining)

        st.divider()
        st.subheader("Charts")
        st.plotly_chart(build_completion_minutes_per_casket_chart(comp_metrics_df), width="stretch")
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(build_completion_caskets_per_hour_chart(comp_metrics_df), width="stretch")
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
        st.caption(
            f"Goal window: {acq_since_progress_start} acquired • "
            f"{comp_since_progress_start} completed since start point • "
            f"{int(combo_goal_remaining)} remaining to {goal_caskets}"
        )

        a1, a2, a3, a4, _a5 = st.columns(5)
        a1.metric("Acquire min / clue", f"{end_to_end_sum['acquire_minutes_per_clue']:.2f}")
        a2.metric("Complete min / casket", f"{end_to_end_sum['complete_minutes_per_casket']:.2f}")
        a3.metric("Total min / casket", f"{end_to_end_sum['total_minutes_per_casket']:.2f}")
        a4.metric("Caskets / hour", f"{end_to_end_sum['end_to_end_caskets_per_hour']:.2f}")

        st.divider()

        p1, p2, p3, p4, p5 = st.columns(5)
        p1.metric("Expected income / clue (acquisition)", human_gp_or_na(end_to_end_sum["combined_acquisition_gp_income_per_clue"]))
        p2.metric("Expected cost / clue (acquisition)", human_gp_or_na(end_to_end_sum["expected_cost_per_clue_acquisition"]))
        p3.metric("Net expected GP / clue (acquisition)", human_gp_or_na(end_to_end_sum["net_gp_per_clue_on_acquisition"]))
        p4.metric("Expected alch income / casket", human_gp_or_na(end_to_end_sum["expected_income_per_casket_alch"]))
        p5.metric("Net GP / casket (full process)", human_gp_or_na(end_to_end_sum["net_gp_per_casket"]))

        st.divider()

        b1, b2, b3, b4, _b5 = st.columns(5)
        b1.metric("Acquisition share of total time", f"{end_to_end_sum['acquisition_share_of_total_time'] * 100:.1f}%")
        b2.metric("Completion share of total time", f"{end_to_end_sum['completion_share_of_total_time'] * 100:.1f}%")
        b3.metric("Current bottleneck", end_to_end_sum["bottleneck"])
        b4.metric("Time remaining (total)", fmt_hours_minutes(combo_goal_time_remaining_s))

        st.divider()

        c1, c2, c3, _c4, _c5 = st.columns(5)
        c1.metric("Net acquisition GP remaining", human_gp_or_na(combo_projected_net_acquisition_gp_remaining))
        c2.metric("Net GP remaining (full process)", human_gp_or_na(combo_expected_net_remaining))
        c3.metric("Remaining caskets", int(combo_goal_remaining))

        st.divider()
        st.subheader("Charts")
        pie_col1, pie_col2 = st.columns(2)
        with pie_col1:
            st.plotly_chart(build_end_to_end_income_source_pie(end_to_end_sum), width="stretch")
        with pie_col2:
            st.plotly_chart(build_end_to_end_time_breakdown_pie(end_to_end_sum), width="stretch")
        st.plotly_chart(build_end_to_end_cph_chart(end_to_end_trend_df), width="stretch")
        st.plotly_chart(build_end_to_end_minutes_chart(end_to_end_trend_df), width="stretch")
