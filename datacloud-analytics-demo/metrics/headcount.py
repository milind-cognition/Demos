"""Headcount: active employees on the last day of each period."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from metrics.snapshot import ALL_DEPARTMENTS, active_on, finalize, load_snapshot, period_label


def compute_headcount(data_dir: str | Path) -> pd.DataFrame:
    snapshot = load_snapshot(data_dir)
    roster = snapshot.employee_roster()
    departments = snapshot.staffed_departments
    rows: list[dict[str, object]] = []
    for period in snapshot.periods:
        active = active_on(roster, period.end_time.normalize())
        counts = active.groupby("department_name").size()
        for department in departments:
            rows.append({"period": period_label(period), "department": department,
                         "value": int(counts.get(department, 0))})
        rows.append({"period": period_label(period), "department": ALL_DEPARTMENTS, "value": len(active)})
    return finalize(rows, departments)
