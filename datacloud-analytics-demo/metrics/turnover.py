"""Turnover rate: terminations in the period / average headcount, as a percent.

Average headcount is the mean of the opening (prior day) and closing headcount.
A department whose average headcount is zero reports 0.0.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from metrics.snapshot import ALL_DEPARTMENTS, active_on, finalize, load_snapshot, period_label


def _rate(terminations: int, opening: int, closing: int) -> float:
    average = (opening + closing) / 2
    return 100.0 * terminations / average if average else 0.0


def compute_turnover(data_dir: str | Path) -> pd.DataFrame:
    snapshot = load_snapshot(data_dir)
    roster = snapshot.employee_roster()
    departments = snapshot.staffed_departments
    rows: list[dict[str, object]] = []
    for period in snapshot.periods:
        start = period.start_time.normalize()
        end = period.end_time.normalize()
        opening = active_on(roster, start - pd.Timedelta(days=1)).groupby("department_name").size()
        closing = active_on(roster, end).groupby("department_name").size()
        leavers = roster[roster["termination_date"].between(start, end)].groupby("department_name").size()
        for department in departments:
            rows.append({
                "period": period_label(period),
                "department": department,
                "value": _rate(int(leavers.get(department, 0)), int(opening.get(department, 0)),
                               int(closing.get(department, 0))),
            })
        rows.append({
            "period": period_label(period),
            "department": ALL_DEPARTMENTS,
            "value": _rate(int(leavers.sum()), int(opening.sum()), int(closing.sum())),
        })
    return finalize(rows, departments)
