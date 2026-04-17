import pandas as pd


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
