"""Overtime cost per employee by industry cohort.

Formula, per month and per cohort (USD)::

    overtime cost      = sum(overtime_hours x hourly_rate x 1.5)   over the cohort's timecards
    cost per employee  = overtime cost / employees active on the last day of the month

- Groups are the cohorts in ``industry_cohorts.csv`` (``cohort_name`` in the ``department``
  column). Every cohort appears, including cohorts whose departments have no employees.
- Timecards are bucketed into the month containing their ``week_start``. Overtime cost includes
  every timecard in the month, including employees who leave before month-end.
- Active employees are counted as in Headcount: hired on/before and not terminated on/before the
  last day of the month. Exempt and part-time employees count in the denominator.
- A cohort with no active employees at month-end reports 0.0.
- The ``All Departments`` rollup is total overtime cost / total active employees across the
  company, i.e. the headcount-weighted average of the cohort values (not their simple mean).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from metrics.snapshot import ALL_DEPARTMENTS, active_on, finalize, load_snapshot, period_label

OVERTIME_PREMIUM = 1.5


def _per_employee(cost: float, employees: int) -> float:
    return cost / employees if employees else 0.0


def compute_overtime_cost_per_employee(data_dir: str | Path) -> pd.DataFrame:
    snapshot = load_snapshot(data_dir)
    cohort_of = snapshot.industry_cohorts[["department_id", "cohort_name"]]
    cohorts = sorted(cohort_of["cohort_name"].unique().tolist())
    roster = snapshot.employee_roster().merge(cohort_of, on="department_id", how="left")

    costs = snapshot.timecards.merge(roster[["employee_id", "hourly_rate", "cohort_name"]], on="employee_id",
                                     how="inner")
    costs["period"] = costs["week_start"].dt.to_period("M")
    costs["cost"] = costs["overtime_hours"] * costs["hourly_rate"] * OVERTIME_PREMIUM
    cost_by_cohort = costs.groupby(["period", "cohort_name"])["cost"].sum()
    cost_by_period = costs.groupby("period")["cost"].sum()

    rows: list[dict[str, object]] = []
    for period in snapshot.periods:
        active = active_on(roster, period.end_time.normalize())
        headcount = active.groupby("cohort_name").size()
        for cohort in cohorts:
            cost = float(cost_by_cohort.get((period, cohort), 0.0))
            rows.append({"period": period_label(period), "department": cohort,
                         "value": _per_employee(cost, int(headcount.get(cohort, 0)))})
        rows.append({"period": period_label(period), "department": ALL_DEPARTMENTS,
                     "value": _per_employee(float(cost_by_period.get(period, 0.0)), len(active))})
    return finalize(rows, cohorts)
