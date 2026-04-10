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


def trailing_weighted_minutes_per_casket(
    seconds: pd.Series,
    caskets: pd.Series,
    window_caskets: int,
) -> tuple[pd.Series, pd.Series]:
    seconds_values = pd.to_numeric(seconds, errors="coerce").fillna(0).tolist()
    casket_values = pd.to_numeric(caskets, errors="coerce").fillna(0).tolist()
    window_caskets = max(1, int(window_caskets))

    minutes_per_casket = []
    caskets_in_window = []
    for idx in range(len(casket_values)):
        included_caskets = 0.0
        included_seconds = 0.0

        for prev_idx in range(idx, -1, -1):
            batch_caskets = float(casket_values[prev_idx])
            batch_seconds = float(seconds_values[prev_idx])
            if batch_caskets <= 0:
                continue

            remaining_caskets = window_caskets - included_caskets
            take_caskets = min(batch_caskets, remaining_caskets)
            included_caskets += take_caskets
            included_seconds += (batch_seconds / batch_caskets) * take_caskets

            if included_caskets >= window_caskets:
                break

        if included_caskets > 0:
            minutes_per_casket.append((included_seconds / included_caskets) / 60.0)
            caskets_in_window.append(included_caskets)
        else:
            minutes_per_casket.append(float("nan"))
            caskets_in_window.append(0.0)

    return (
        pd.Series(minutes_per_casket, index=seconds.index),
        pd.Series(caskets_in_window, index=seconds.index),
    )


def _minutes_to_caskets_per_hour(minutes_per_casket: pd.Series) -> pd.Series:
    values = pd.to_numeric(minutes_per_casket, errors="coerce")
    return 60.0 / values.where(values > 0)


def build_end_to_end_trend_df(
    acq_df: pd.DataFrame,
    comp_df: pd.DataFrame,
    window_caskets: int,
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

    d["cum_acq_seconds"] = d["acq_seconds"].cumsum()
    d["cum_acq_caskets"] = d["acq_caskets"].cumsum()
    d["cum_comp_seconds"] = d["comp_seconds"].cumsum()
    d["cum_comp_caskets"] = d["comp_caskets"].cumsum()

    (
        d["recent_acquire_minutes_per_casket"],
        d["recent_acq_caskets_in_window"],
    ) = trailing_weighted_minutes_per_casket(d["acq_seconds"], d["acq_caskets"], window_caskets)
    (
        d["recent_complete_minutes_per_casket"],
        d["recent_comp_caskets_in_window"],
    ) = trailing_weighted_minutes_per_casket(d["comp_seconds"], d["comp_caskets"], window_caskets)

    d["overall_acquire_minutes_per_casket"] = (
        d["cum_acq_seconds"].div(d["cum_acq_caskets"].where(d["cum_acq_caskets"] > 0)) / 60.0
    )
    d["overall_complete_minutes_per_casket"] = (
        d["cum_comp_seconds"].div(d["cum_comp_caskets"].where(d["cum_comp_caskets"] > 0)) / 60.0
    )
    d["overall_total_minutes_per_casket"] = (
        d["overall_acquire_minutes_per_casket"] + d["overall_complete_minutes_per_casket"]
    )
    d["recent_total_minutes_per_casket"] = (
        d["recent_acquire_minutes_per_casket"] + d["recent_complete_minutes_per_casket"]
    )
    d["overall_end_to_end_caskets_per_hour"] = _minutes_to_caskets_per_hour(
        d["overall_total_minutes_per_casket"]
    )
    d["recent_end_to_end_caskets_per_hour"] = _minutes_to_caskets_per_hour(
        d["recent_total_minutes_per_casket"]
    )

    d["window_caskets"] = int(window_caskets)
    d["date_label"] = d["date"].dt.strftime("%Y-%m-%d")
    return d
