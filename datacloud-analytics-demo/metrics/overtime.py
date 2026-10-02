"""Overtime rate: overtime hours as a percent of total hours worked.

Timecards are bucketed into the period containing their ``week_start``.
A department with no hours in a period reports 0.0.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from metrics.snapshot import ALL_DEPARTMENTS, finalize, load_snapshot, period_label


def _rate(overtime: float, regular: float) -> float:
    total = overtime + regular
    return 100.0 * overtime / total if total else 0.0


def compute_overtime(data_dir: str | Path) -> pd.DataFrame:
    snapshot = load_snapshot(data_dir)
    departments = snapshot.staffed_departments
    hours = snapshot.timecards.merge(
        snapshot.employee_roster()[["employee_id", "department_name"]], on="employee_id", how="inner"
    )
    hours["period"] = hours["week_start"].dt.to_period("M")
    by_department = hours.groupby(["period", "department_name"])[["regular_hours", "overtime_hours"]].sum()
    by_period = hours.groupby("period")[["regular_hours", "overtime_hours"]].sum()

    rows: list[dict[str, object]] = []
    for period in snapshot.periods:
        for department in departments:
            key = (period, department)
            regular, overtime = (by_department.loc[key].tolist() if key in by_department.index else (0.0, 0.0))
            rows.append({"period": period_label(period), "department": department,
                         "value": _rate(overtime, regular)})
        regular, overtime = by_period.loc[period].tolist() if period in by_period.index else (0.0, 0.0)
        rows.append({"period": period_label(period), "department": ALL_DEPARTMENTS,
                     "value": _rate(overtime, regular)})
    return finalize(rows, departments)
