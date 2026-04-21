from datetime import date, datetime
from typing import Any

import pandas as pd

from .config import LOCAL_TIMEZONE

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


def minutes_to_hhmm(total_minutes: float) -> str:
    return seconds_to_hhmm(float(total_minutes or 0) * 60.0)


def minutes_to_metric_duration(total_minutes: float) -> str:
    return fmt_hours_minutes(float(total_minutes or 0) * 60.0)
