from math import isclose
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from weighted_metrics import rolling_weighted_ratio, weighted_ratio


def assert_close(actual: float, expected: float, label: str) -> None:
    if not isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-9):
        raise AssertionError(f"{label}: expected {expected}, got {actual}")


def main() -> None:
    fast_seconds = 5 * 10 * 60
    slow_seconds = 1 * 30 * 60
    df = pd.DataFrame(
        {
            "duration_seconds": [fast_seconds, slow_seconds],
            "clues": [5, 1],
            "gp_cost": [500, 500],
            "clues_completed": [5, 1],
        }
    )

    expected_minutes = ((fast_seconds + slow_seconds) / 60.0) / 6
    unweighted_minutes = ((df["duration_seconds"] / 60.0) / df["clues"]).mean()
    if isclose(float(unweighted_minutes), expected_minutes, rel_tol=1e-9, abs_tol=1e-9):
        raise AssertionError("fixture does not distinguish weighted and unweighted averages")

    assert_close(
        weighted_ratio(df["duration_seconds"] / 60.0, df["clues"]),
        expected_minutes,
        "overall acquisition minutes per clue",
    )

    rolling_minutes = rolling_weighted_ratio(df["duration_seconds"] / 60.0, df["clues"], 10)
    assert_close(rolling_minutes.iloc[0], 10.0, "first rolling minutes per clue")
    assert_close(rolling_minutes.iloc[1], expected_minutes, "second rolling minutes per clue")

    assert_close(
        rolling_weighted_ratio(df["gp_cost"], df["clues"], 10).iloc[1],
        1000 / 6,
        "rolling GP cost per clue",
    )
    assert_close(
        rolling_weighted_ratio(df["clues_completed"], df["duration_seconds"] / 3600.0, 10).iloc[1],
        6 / ((fast_seconds + slow_seconds) / 3600.0),
        "rolling caskets per hour",
    )


if __name__ == "__main__":
    main()
