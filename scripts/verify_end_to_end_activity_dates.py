from math import isclose
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hard_clue.metrics import build_end_to_end_trend_df


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

    trend_df = build_end_to_end_trend_df(acq_df, comp_df, recent_acq_span=3, recent_comp_span=2)
    prefix_trend_df = build_end_to_end_trend_df(
        acq_df.iloc[:-1],
        comp_df.iloc[:-1],
        recent_acq_span=3,
        recent_comp_span=2,
    )
    expected_dates = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-05", "2026-01-06"]
    actual_dates = trend_df["date_label"].tolist()
    if actual_dates != expected_dates:
        raise AssertionError(f"date labels: expected {expected_dates}, got {actual_dates}")

    if "2026-01-04" in actual_dates:
        raise AssertionError("no-activity dates should not be added to the trend")

    first = trend_df.iloc[0]
    assert_close(first["recent_acquire_minutes_per_casket"], 5.0, "first acquisition point")
    assert_close(first["raw_acquire_minutes_per_casket"], 5.0, "first raw acquisition point")
    assert_nan(first["recent_complete_minutes_per_casket"], "first completion point should be blank")
    assert_nan(first["raw_complete_minutes_per_casket"], "first raw completion point should be blank")
    assert_nan(first["recent_total_minutes_per_casket"], "first total point should be blank")
    assert_nan(first["raw_total_minutes_per_casket"], "first raw total point should be blank")
    assert_close(first["adjusted_acquire_minutes_per_casket"], 5.0, "first adjusted acquisition point")
    assert_nan(first["adjusted_complete_minutes_per_casket"], "first adjusted completion point should be blank")
    assert_nan(first["adjusted_total_minutes_per_casket"], "first adjusted total point should be blank")
    assert_close(first["adjusted_acquire_same_day_share"], 1.0, "first adjusted acquisition same-day share")
    assert_nan(first["recent_end_to_end_caskets_per_hour"], "first cph point should be blank")
    assert_close(first["all_time_total_minutes_per_casket"], 8.833333333333334, "flat overall total benchmark")
    assert_close(
        first["all_time_end_to_end_caskets_per_hour"],
        60.0 / 8.833333333333334,
        "flat overall cph benchmark",
    )
    if not bool(first["has_acq_activity"]) or bool(first["has_comp_activity"]):
        raise AssertionError("first row activity flags are incorrect")

    second = trend_df.iloc[1]
    assert_close(second["recent_acquire_minutes_per_casket"], 3.0, "second acquisition point")
    assert_close(second["raw_acquire_minutes_per_casket"], 1.6666666666666667, "second raw acquisition point")
    assert_nan(second["recent_complete_minutes_per_casket"], "second completion point should still be blank")
    assert_nan(second["recent_total_minutes_per_casket"], "second total point should still be blank")
    assert_nan(second["raw_total_minutes_per_casket"], "second raw total point should still be blank")
    assert_close(second["adjusted_acquire_minutes_per_casket"], 3.0, "second adjusted acquisition point")
    assert_close(second["adjusted_acquire_same_day_share"], 0.6, "second adjusted acquisition same-day share")
    assert_nan(second["adjusted_total_minutes_per_casket"], "second adjusted total point should still be blank")

    third = trend_df.iloc[2]
    assert_close(third["recent_acquire_minutes_per_casket"], 3.0, "acquisition should carry forward")
    assert_nan(third["raw_acquire_minutes_per_casket"], "raw acquisition should be blank on completion-only dates")
    assert_close(third["recent_complete_minutes_per_casket"], 4.0, "first completion point")
    assert_close(third["raw_complete_minutes_per_casket"], 4.0, "first raw completion point")
    assert_close(third["recent_complete_caskets_per_hour"], 15.0, "first completion cph point")
    assert_close(third["raw_complete_caskets_per_hour"], 15.0, "first raw completion cph point")
    assert_close(third["recent_total_minutes_per_casket"], 7.0, "first total point")
    assert_close(third["raw_total_minutes_per_casket"], 5.666666666666667, "first raw total point")
    assert_close(third["raw_total_same_day_weight"], 2.0, "first raw total same-day weight")
    assert_close(third["adjusted_total_minutes_per_casket"], 7.0, "first adjusted total point")
    assert_close(third["adjusted_complete_same_day_share"], 1.0, "first adjusted completion same-day share")
    assert_close(
        third["adjusted_end_to_end_caskets_per_hour"],
        60.0 / 7.0,
        "first adjusted cph point",
    )
    assert_close(third["recent_end_to_end_caskets_per_hour"], 60.0 / 7.0, "first cph point")
    if bool(third["has_acq_activity"]) or not bool(third["has_comp_activity"]):
        raise AssertionError("third row activity flags are incorrect")

    fourth = trend_df.iloc[3]
    assert_close(
        fourth["recent_acquire_minutes_per_casket"],
        third["recent_acquire_minutes_per_casket"],
        "acquisition should stay flat on later completion-only dates",
    )
    assert_close(fourth["recent_complete_minutes_per_casket"], 4.75, "completion should update on its new point")
    assert_close(fourth["recent_total_minutes_per_casket"], 7.75, "total should use carried acquisition value")
    assert_nan(fourth["raw_acquire_minutes_per_casket"], "raw acquisition should stay blank on completion-only dates")
    assert_close(fourth["raw_complete_minutes_per_casket"], 5.0, "second raw completion point")
    assert_close(fourth["raw_total_minutes_per_casket"], 6.666666666666667, "second raw total point")
    assert_close(fourth["raw_total_same_day_weight"], 3.0, "second raw total same-day weight")
    assert_close(fourth["adjusted_complete_minutes_per_casket"], 4.6, "second adjusted completion point")
    assert_close(fourth["adjusted_complete_same_day_share"], 0.6, "second adjusted completion same-day share")
    assert_close(fourth["adjusted_total_minutes_per_casket"], 7.6, "second adjusted total point")

    fifth = trend_df.iloc[4]
    assert_close(fifth["recent_acquire_minutes_per_casket"], 5.0, "both-sides date acquisition update")
    assert_close(fifth["raw_acquire_minutes_per_casket"], 10.0, "both-sides raw acquisition update")
    assert_close(fifth["recent_acquire_caskets_per_hour"], 12.0, "both-sides recent acquisition cph update")
    assert_close(fifth["raw_acquire_caskets_per_hour"], 6.0, "both-sides raw acquisition cph update")
    assert_close(
        fifth["recent_complete_minutes_per_casket"],
        4.857142857142857,
        "both-sides date completion update",
    )
    assert_close(fifth["raw_complete_minutes_per_casket"], 5.0, "both-sides raw completion update")
    assert_close(
        fifth["recent_complete_caskets_per_hour"],
        60.0 / 4.857142857142857,
        "both-sides recent completion cph update",
    )
    assert_close(fifth["raw_complete_caskets_per_hour"], 12.0, "both-sides raw completion cph update")
    assert_close(
        fifth["recent_total_minutes_per_casket"],
        9.857142857142858,
        "both-sides date total update",
    )
    assert_close(fifth["raw_total_minutes_per_casket"], 15.0, "both-sides raw total update")
    assert_close(fifth["raw_total_same_day_weight"], 2.0, "both-sides raw total same-day weight")
    assert_close(fifth["adjusted_acquire_minutes_per_casket"], 5.0, "both-sides adjusted acquisition update")
    assert_close(
        fifth["adjusted_complete_minutes_per_casket"],
        4.818181818181818,
        "both-sides adjusted completion update",
    )
    assert_close(
        fifth["adjusted_total_minutes_per_casket"],
        9.818181818181818,
        "both-sides adjusted total update",
    )
    assert_close(fifth["adjusted_acquire_same_day_share"], 1.0 / 3.5, "both-sides acquisition same-day share")
    assert_close(fifth["adjusted_complete_same_day_share"], 1.0 / 3.6666666666666665, "both-sides completion same-day share")
    assert_close(
        fifth["recent_end_to_end_caskets_per_hour"],
        60.0 / 9.857142857142858,
        "both-sides date cph update",
    )
    assert_close(
        fifth["all_time_total_minutes_per_casket"],
        first["all_time_total_minutes_per_casket"],
        "flat overall total benchmark should stay fixed",
    )
    assert_close(
        fifth["all_time_end_to_end_caskets_per_hour"],
        first["all_time_end_to_end_caskets_per_hour"],
        "flat overall cph benchmark should stay fixed",
    )
    if not bool(fifth["has_acq_activity"]) or not bool(fifth["has_comp_activity"]):
        raise AssertionError("fifth row activity flags are incorrect")

    compare_cols = [
        "recent_acquire_minutes_per_casket",
        "recent_complete_minutes_per_casket",
        "recent_total_minutes_per_casket",
        "recent_end_to_end_caskets_per_hour",
        "adjusted_acquire_minutes_per_casket",
        "adjusted_complete_minutes_per_casket",
        "adjusted_total_minutes_per_casket",
        "adjusted_end_to_end_caskets_per_hour",
    ]
    for col in compare_cols:
        full_prefix = trend_df.loc[: len(prefix_trend_df) - 1, col].reset_index(drop=True)
        prior_only = prefix_trend_df[col].reset_index(drop=True)
        if not full_prefix.equals(prior_only):
            raise AssertionError(f"{col}: adding future rows should not change earlier EWMA points")


if __name__ == "__main__":
    main()
