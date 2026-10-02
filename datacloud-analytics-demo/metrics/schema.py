"""Contract every metric frame must satisfy before it is exported."""

from __future__ import annotations

import re

import pandas as pd

from metrics.snapshot import ALL_DEPARTMENTS, METRIC_COLUMNS

PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class MetricFrameError(ValueError):
    """Raised when a metric function returns a frame that breaks the contract."""


def validate_metric_frame(frame: pd.DataFrame, key: str) -> None:
    if list(frame.columns) != METRIC_COLUMNS:
        raise MetricFrameError(f"{key}: columns must be {METRIC_COLUMNS}, got {list(frame.columns)}")
    if frame.empty:
        raise MetricFrameError(f"{key}: metric frame is empty")
    if frame["value"].isna().any():
        raise MetricFrameError(f"{key}: value column contains nulls")
    if not pd.api.types.is_numeric_dtype(frame["value"]):
        raise MetricFrameError(f"{key}: value column must be numeric")
    bad_periods = sorted({p for p in frame["period"] if not PERIOD_PATTERN.match(str(p))})
    if bad_periods:
        raise MetricFrameError(f"{key}: periods must be YYYY-MM, got {bad_periods}")
    if frame.duplicated(["period", "department"]).any():
        raise MetricFrameError(f"{key}: duplicate (period, department) rows")
    periods = set(frame["period"])
    rollup_periods = set(frame.loc[frame["department"] == ALL_DEPARTMENTS, "period"])
    if periods != rollup_periods:
        missing = sorted(periods - rollup_periods)
        raise MetricFrameError(f"{key}: missing {ALL_DEPARTMENTS!r} rollup for periods {missing}")
