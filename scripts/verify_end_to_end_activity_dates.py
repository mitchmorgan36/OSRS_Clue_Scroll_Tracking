from math import isclose
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from end_to_end_metrics import build_end_to_end_trend_df


def assert_close(actual: float, expected: float, label: str) -> None:
    if not isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-9):
        raise AssertionError(f"{label}: expected {expected}, got {actual}")


def assert_nan(actual: float, label: str) -> None:
    if not pd.isna(actual):
        raise AssertionError(f"{label}: expected NaN, got {actual}")


def main() -> None:
    acq_df = pd.DataFrame(
        {
            "log_date": ["2026-01-01", "2026-01-02", "2026-01-06"],
            "duration_seconds": [600, 300, 600],
            "clues": [2, 3, 1],
        }
    )
    comp_df = pd.DataFrame(
        {
            "log_date": ["2026-01-03", "2026-01-05", "2026-01-06"],
            "duration_seconds": [480, 900, 300],
            "clues_completed": [2, 3, 1],
        }
    )

    trend_df = build_end_to_end_trend_df(acq_df, comp_df, window_caskets=50)
    expected_dates = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-05", "2026-01-06"]
    actual_dates = trend_df["date_label"].tolist()
    if actual_dates != expected_dates:
        raise AssertionError(f"date labels: expected {expected_dates}, got {actual_dates}")

    if "2026-01-04" in actual_dates:
        raise AssertionError("no-activity dates should not be added to the trend")

    first = trend_df.iloc[0]
    assert_close(first["recent_acquire_minutes_per_casket"], 5.0, "first acquisition point")
    assert_nan(first["recent_complete_minutes_per_casket"], "first completion point should be blank")
    assert_nan(first["recent_total_minutes_per_casket"], "first total point should be blank")
    assert_nan(first["recent_end_to_end_caskets_per_hour"], "first cph point should be blank")
    if not bool(first["has_acq_activity"]) or bool(first["has_comp_activity"]):
        raise AssertionError("first row activity flags are incorrect")

    second = trend_df.iloc[1]
    assert_close(second["recent_acquire_minutes_per_casket"], 3.0, "second acquisition point")
    assert_nan(second["recent_complete_minutes_per_casket"], "second completion point should still be blank")
    assert_nan(second["recent_total_minutes_per_casket"], "second total point should still be blank")

    third = trend_df.iloc[2]
    assert_close(third["recent_acquire_minutes_per_casket"], 3.0, "acquisition should carry forward")
    assert_close(third["recent_complete_minutes_per_casket"], 4.0, "first completion point")
    assert_close(third["recent_total_minutes_per_casket"], 7.0, "first total point")
    assert_close(third["recent_end_to_end_caskets_per_hour"], 60.0 / 7.0, "first cph point")
    if bool(third["has_acq_activity"]) or not bool(third["has_comp_activity"]):
        raise AssertionError("third row activity flags are incorrect")

    fourth = trend_df.iloc[3]
    assert_close(
        fourth["recent_acquire_minutes_per_casket"],
        third["recent_acquire_minutes_per_casket"],
        "acquisition should stay flat on later completion-only dates",
    )
    assert_close(fourth["recent_complete_minutes_per_casket"], 4.6, "completion should update on its new point")
    assert_close(fourth["recent_total_minutes_per_casket"], 7.6, "total should use carried acquisition value")

    fifth = trend_df.iloc[4]
    assert_close(fifth["recent_acquire_minutes_per_casket"], 4.166666666666667, "both-sides date acquisition update")
    assert_close(fifth["recent_complete_minutes_per_casket"], 4.666666666666667, "both-sides date completion update")
    assert_close(
        fifth["recent_total_minutes_per_casket"],
        8.833333333333334,
        "both-sides date total update",
    )
    assert_close(
        fifth["recent_end_to_end_caskets_per_hour"],
        60.0 / 8.833333333333334,
        "both-sides date cph update",
    )
    if not bool(fifth["has_acq_activity"]) or not bool(fifth["has_comp_activity"]):
        raise AssertionError("fifth row activity flags are incorrect")


if __name__ == "__main__":
    main()
