from typing import Any, Dict

import pandas as pd


def _valid_weighted_parts(numerator: pd.Series, denominator: pd.Series) -> tuple[pd.Series, pd.Series]:
    num = pd.to_numeric(pd.Series(numerator), errors="coerce")
    den = pd.to_numeric(pd.Series(denominator), errors="coerce")
    valid = num.notna() & den.notna() & (den > 0)
    return num.where(valid, 0.0).fillna(0.0), den.where(valid, 0.0).fillna(0.0)


def weighted_ratio(numerator: pd.Series, denominator: pd.Series) -> float:
    num, den = _valid_weighted_parts(numerator, denominator)
    denominator_total = float(den.sum())
    if denominator_total <= 0:
        return float("nan")
    return float(num.sum() / denominator_total)


def rolling_weighted_ratio(numerator: pd.Series, denominator: pd.Series, window: int) -> pd.Series:
    num, den = _valid_weighted_parts(numerator, denominator)
    window = max(1, int(window))
    numerator_total = num.rolling(window=window, min_periods=1).sum()
    denominator_total = den.rolling(window=window, min_periods=1).sum()
    return numerator_total.div(denominator_total.where(denominator_total > 0))


def ewma_weighted_ratio(numerator: pd.Series, denominator: pd.Series, span: int) -> pd.Series:
    num = pd.to_numeric(pd.Series(numerator), errors="coerce")
    den = pd.to_numeric(pd.Series(denominator), errors="coerce")
    valid = num.notna() & den.notna() & (den > 0)
    if not valid.any():
        return pd.Series(float("nan"), index=num.index)

    span = max(1, int(span))
    active_num = num[valid].astype(float)
    active_den = den[valid].astype(float)
    ewma_num = active_num.ewm(span=span, adjust=False).mean()
    ewma_den = active_den.ewm(span=span, adjust=False).mean()
    ratio = ewma_num.div(ewma_den.where(ewma_den > 0))
    return ratio.reindex(num.index).ffill()


def ewma_mean(series: pd.Series, span: int) -> pd.Series:
    values = pd.to_numeric(pd.Series(series), errors="coerce")
    valid = values.notna()
    if not valid.any():
        return pd.Series(float("nan"), index=values.index)

    span = max(1, int(span))
    active_values = values[valid].astype(float)
    smoothed = active_values.ewm(span=span, adjust=False).mean()
    return smoothed.reindex(values.index).ffill()



def _coerce_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _prepare_daily_stream(
    df: pd.DataFrame,
    seconds_col: str,
    count_col: str,
    prefix: str,
) -> pd.DataFrame:
    d = _coerce_numeric(df, [seconds_col, count_col]).copy()
    if "log_date" not in d.columns:
        return pd.DataFrame(columns=["date", f"{prefix}_seconds", f"{prefix}_caskets"])

    d["log_date"] = pd.to_datetime(d["log_date"], errors="coerce")
    d = d.dropna(subset=["log_date", seconds_col, count_col])
    d = d[d[count_col] > 0].copy()
    if d.empty:
        return pd.DataFrame(columns=["date", f"{prefix}_seconds", f"{prefix}_caskets"])

    d["date"] = d["log_date"].dt.date
    return (
        d.groupby("date", as_index=False)
        .agg(
            **{
                f"{prefix}_seconds": (seconds_col, "sum"),
                f"{prefix}_caskets": (count_col, "sum"),
            }
        )
        .sort_values("date")
    )


def exp_weighted_minutes_per_casket(
    seconds: pd.Series,
    caskets: pd.Series,
    span: int,
) -> pd.Series:
    sec = pd.to_numeric(seconds, errors="coerce")
    qty = pd.to_numeric(caskets, errors="coerce")
    valid = sec.notna() & qty.notna() & (qty > 0)
    if not valid.any():
        return pd.Series(float("nan"), index=seconds.index)

    span = max(1, int(span))
    active_seconds = sec[valid].astype(float)
    active_caskets = qty[valid].astype(float)

    # Smooth totals separately so larger clue or casket batches still carry more weight.
    ewma_seconds = active_seconds.ewm(span=span, adjust=False).mean()
    ewma_caskets = active_caskets.ewm(span=span, adjust=False).mean()
    active_minutes = ewma_seconds.div(ewma_caskets.where(ewma_caskets > 0)) / 60.0
    return active_minutes.reindex(seconds.index).ffill()


def exp_weighted_count(
    caskets: pd.Series,
    span: int,
) -> pd.Series:
    qty = pd.to_numeric(caskets, errors="coerce")
    valid = qty.notna() & (qty > 0)
    if not valid.any():
        return pd.Series(float("nan"), index=caskets.index)

    span = max(1, int(span))
    active_caskets = qty[valid].astype(float)
    ewma_caskets = active_caskets.ewm(span=span, adjust=False).mean()
    return ewma_caskets.reindex(caskets.index).ffill()


def _sample_adjusted_component(
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


def _minutes_to_caskets_per_hour(minutes_per_casket: pd.Series) -> pd.Series:
    values = pd.to_numeric(minutes_per_casket, errors="coerce")
    return 60.0 / values.where(values > 0)


def build_end_to_end_trend_df(
    acq_df: pd.DataFrame,
    comp_df: pd.DataFrame,
    recent_acq_span: int,
    recent_comp_span: int,
) -> pd.DataFrame:
    acq_daily = _prepare_daily_stream(acq_df, "duration_seconds", "clues", "acq")
    comp_daily = _prepare_daily_stream(comp_df, "duration_seconds", "clues_completed", "comp")
    if acq_daily.empty and comp_daily.empty:
        return pd.DataFrame()

    d = pd.merge(acq_daily, comp_daily, on="date", how="outer").sort_values("date")
    for col in ("acq_seconds", "acq_caskets", "comp_seconds", "comp_caskets"):
        if col not in d.columns:
            d[col] = 0.0
    d[["acq_seconds", "acq_caskets", "comp_seconds", "comp_caskets"]] = d[
        ["acq_seconds", "acq_caskets", "comp_seconds", "comp_caskets"]
    ].fillna(0.0)

    d["date"] = pd.to_datetime(d["date"])
    d["has_acq_activity"] = d["acq_caskets"] > 0
    d["has_comp_activity"] = d["comp_caskets"] > 0
    d["has_both_activity"] = d["has_acq_activity"] & d["has_comp_activity"]

    d["recent_acquire_minutes_per_casket"] = exp_weighted_minutes_per_casket(
        d["acq_seconds"],
        d["acq_caskets"],
        recent_acq_span,
    )
    d["recent_complete_minutes_per_casket"] = exp_weighted_minutes_per_casket(
        d["comp_seconds"],
        d["comp_caskets"],
        recent_comp_span,
    )
    d["recent_acq_caskets_per_day"] = exp_weighted_count(d["acq_caskets"], recent_acq_span)
    d["recent_comp_caskets_per_day"] = exp_weighted_count(d["comp_caskets"], recent_comp_span)

    d["raw_acquire_minutes_per_casket"] = (
        d["acq_seconds"].div(d["acq_caskets"].where(d["acq_caskets"] > 0)) / 60.0
    )
    d["raw_complete_minutes_per_casket"] = (
        d["comp_seconds"].div(d["comp_caskets"].where(d["comp_caskets"] > 0)) / 60.0
    )
    d["raw_total_acquire_component"] = d["raw_acquire_minutes_per_casket"].ffill()
    d["raw_total_complete_component"] = d["raw_complete_minutes_per_casket"].ffill()
    d["raw_total_minutes_per_casket"] = (
        d["raw_total_acquire_component"] + d["raw_total_complete_component"]
    )
    d["adjusted_acquire_baseline_caskets"] = d["recent_acq_caskets_per_day"].shift(1)
    d["adjusted_complete_baseline_caskets"] = d["recent_comp_caskets_per_day"].shift(1)
    d["adjusted_acquire_minutes_per_casket"], d["adjusted_acquire_same_day_share"] = (
        _sample_adjusted_component(
            d["raw_acquire_minutes_per_casket"],
            d["recent_acquire_minutes_per_casket"],
            d["acq_caskets"],
            d["adjusted_acquire_baseline_caskets"],
            d["recent_acquire_minutes_per_casket"].shift(1),
        )
    )
    d["adjusted_complete_minutes_per_casket"], d["adjusted_complete_same_day_share"] = (
        _sample_adjusted_component(
            d["raw_complete_minutes_per_casket"],
            d["recent_complete_minutes_per_casket"],
            d["comp_caskets"],
            d["adjusted_complete_baseline_caskets"],
            d["recent_complete_minutes_per_casket"].shift(1),
        )
    )
    d["adjusted_total_minutes_per_casket"] = (
        d["adjusted_acquire_minutes_per_casket"] + d["adjusted_complete_minutes_per_casket"]
    )
    d["recent_total_minutes_per_casket"] = (
        d["recent_acquire_minutes_per_casket"] + d["recent_complete_minutes_per_casket"]
    )
    d["adjusted_end_to_end_caskets_per_hour"] = _minutes_to_caskets_per_hour(
        d["adjusted_total_minutes_per_casket"]
    )
    d["raw_end_to_end_caskets_per_hour"] = _minutes_to_caskets_per_hour(
        d["raw_total_minutes_per_casket"]
    )
    d["raw_acquire_caskets_per_hour"] = _minutes_to_caskets_per_hour(
        d["raw_acquire_minutes_per_casket"]
    )
    d["raw_complete_caskets_per_hour"] = _minutes_to_caskets_per_hour(
        d["raw_complete_minutes_per_casket"]
    )

    acq_total_caskets = float(d["acq_caskets"].sum())
    comp_total_caskets = float(d["comp_caskets"].sum())
    all_time_acq = (
        float(d["acq_seconds"].sum()) / acq_total_caskets / 60.0
        if acq_total_caskets > 0
        else float("nan")
    )
    all_time_comp = (
        float(d["comp_seconds"].sum()) / comp_total_caskets / 60.0
        if comp_total_caskets > 0
        else float("nan")
    )
    d["all_time_acquire_minutes_per_casket"] = all_time_acq
    d["all_time_complete_minutes_per_casket"] = all_time_comp
    d["all_time_total_minutes_per_casket"] = (
        d["all_time_acquire_minutes_per_casket"] + d["all_time_complete_minutes_per_casket"]
    )
    d["all_time_end_to_end_caskets_per_hour"] = _minutes_to_caskets_per_hour(
        d["all_time_total_minutes_per_casket"]
    )
    d["all_time_acquire_caskets_per_hour"] = _minutes_to_caskets_per_hour(
        d["all_time_acquire_minutes_per_casket"]
    )
    d["all_time_complete_caskets_per_hour"] = _minutes_to_caskets_per_hour(
        d["all_time_complete_minutes_per_casket"]
    )
    d["recent_acquire_caskets_per_hour"] = _minutes_to_caskets_per_hour(
        d["recent_acquire_minutes_per_casket"]
    )
    d["recent_complete_caskets_per_hour"] = _minutes_to_caskets_per_hour(
        d["recent_complete_minutes_per_casket"]
    )
    d["recent_end_to_end_caskets_per_hour"] = _minutes_to_caskets_per_hour(
        d["recent_total_minutes_per_casket"]
    )

    d["raw_total_same_day_weight"] = d["acq_caskets"] + d["comp_caskets"]
    d["recent_acq_ewma_span"] = int(max(1, int(recent_acq_span)))
    d["recent_comp_ewma_span"] = int(max(1, int(recent_comp_span)))
    d["date_label"] = d["date"].dt.strftime("%Y-%m-%d")
    return d


from .config import (
    CHAOS_RUNE_GP_PER_CLUE,
    CHAOS_RUNE_GP_PER_KILL,
    CHAOS_RUNES_PER_KILL,
    COMBINED_ACQUISITION_GP_INCOME_PER_CLUE,
    DEATH_RUNE_GP_PER_CLUE,
    DEATH_RUNE_GP_PER_KILL,
    DEATH_RUNES_PER_KILL,
    END_TO_END_RECENT_ACQ_EWMA_SPAN,
    END_TO_END_RECENT_COMP_EWMA_SPAN,
    EXPECTED_ALCH_GP_PER_CASKET,
    JELLY_KILLS_PER_HARD_CLUE,
    RUNE_ARMOR_GP_PER_CLUE,
    RUNE_ARMOR_GP_PER_KILL,
)
from .formatting import seconds_to_hhmm

def coerce_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out

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

    d["recent_ewma_minutes_per_clue"] = ewma_weighted_ratio(
        d["duration_seconds"] / 60.0,
        d["clues"],
        END_TO_END_RECENT_ACQ_EWMA_SPAN,
    )
    d["recent_ewma_clues_per_hour"] = ewma_weighted_ratio(
        d["clues"],
        d["duration_seconds"] / 3600.0,
        END_TO_END_RECENT_ACQ_EWMA_SPAN,
    )
    d["recent_ewma_gp_cost_per_clue"] = ewma_weighted_ratio(
        d["gp_cost"],
        d["clues"],
        END_TO_END_RECENT_ACQ_EWMA_SPAN,
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
    d["recent_ewma_minutes_per_casket"] = ewma_weighted_ratio(
        d["duration_seconds"] / 60.0,
        d["clues_completed"],
        END_TO_END_RECENT_COMP_EWMA_SPAN,
    )
    d["recent_ewma_caskets_per_hour"] = ewma_weighted_ratio(
        d["clues_completed"],
        d["duration_seconds"] / 3600.0,
        END_TO_END_RECENT_COMP_EWMA_SPAN,
    )
    d["duration"] = d["duration_seconds"].apply(seconds_to_hhmm)
    d["log_date"] = d["log_date"].dt.date
    return d

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

def normalized_progress_baseline(raw_value: Any, running_total: int) -> int:
    baseline = clamp_nonnegative_int(raw_value, default=0)
    return min(running_total, baseline)
