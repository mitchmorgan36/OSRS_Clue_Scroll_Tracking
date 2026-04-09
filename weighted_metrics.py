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
