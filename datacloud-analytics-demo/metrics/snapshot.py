"""Loading and shared helpers for a ``data/`` snapshot directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ALL_DEPARTMENTS = "All Departments"
METRIC_COLUMNS = ["period", "department", "value"]

_SCHEMAS: dict[str, dict[str, list[str]]] = {
    "departments": {"columns": ["department_id", "department_name", "cost_center"], "dates": []},
    "employees": {
        "columns": [
            "employee_id", "department_id", "job_title", "flsa_status",
            "employment_type", "hourly_rate", "hire_date",
        ],
        "dates": ["hire_date"],
    },
    "timecards": {
        "columns": ["employee_id", "week_start", "regular_hours", "overtime_hours"],
        "dates": ["week_start"],
    },
    "terminations": {
        "columns": ["employee_id", "termination_date", "termination_type", "reason"],
        "dates": ["termination_date"],
    },
    "industry_cohorts": {
        "columns": ["department_id", "cohort_id", "cohort_name", "naics_sector"],
        "dates": [],
    },
}


class SnapshotError(ValueError):
    """Raised when a snapshot directory is missing files or columns."""


@dataclass(frozen=True)
class Snapshot:
    departments: pd.DataFrame
    employees: pd.DataFrame
    timecards: pd.DataFrame
    terminations: pd.DataFrame
    industry_cohorts: pd.DataFrame

    @property
    def periods(self) -> list[pd.Period]:
        """Monthly reporting periods spanned by the timecards, oldest first."""
        if self.timecards.empty:
            return []
        start = self.timecards["week_start"].min().to_period("M")
        end = self.timecards["week_start"].max().to_period("M")
        return list(pd.period_range(start, end, freq="M"))

    @property
    def staffed_departments(self) -> list[str]:
        """Names of departments with at least one employee record, sorted."""
        staffed = self.departments[self.departments["department_id"].isin(self.employees["department_id"])]
        return sorted(staffed["department_name"].tolist())

    def employee_roster(self) -> pd.DataFrame:
        """Employees joined to department name and (optional) termination date."""
        roster = self.employees.merge(
            self.departments[["department_id", "department_name"]], on="department_id", how="left"
        )
        return roster.merge(
            self.terminations[["employee_id", "termination_date", "termination_type"]],
            on="employee_id",
            how="left",
        )


def _read(data_dir: Path, name: str) -> pd.DataFrame:
    path = data_dir / f"{name}.csv"
    if not path.is_file():
        raise SnapshotError(f"Snapshot is missing {path.name} (looked in {data_dir})")
    schema = _SCHEMAS[name]
    frame = pd.read_csv(path, dtype=str)
    missing = [c for c in schema["columns"] if c not in frame.columns]
    if missing:
        raise SnapshotError(f"{path.name} is missing columns: {', '.join(missing)}")
    for column in schema["dates"]:
        frame[column] = pd.to_datetime(frame[column], format="%Y-%m-%d")
    return frame


def load_snapshot(data_dir: str | Path) -> Snapshot:
    """Load and type every CSV in a snapshot directory."""
    root = Path(data_dir)
    frames = {name: _read(root, name) for name in _SCHEMAS}
    frames["employees"]["hourly_rate"] = frames["employees"]["hourly_rate"].astype(float)
    for column in ("regular_hours", "overtime_hours"):
        frames["timecards"][column] = frames["timecards"][column].astype(float)
    return Snapshot(**frames)


def active_on(roster: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Employees hired on/before ``as_of`` and not terminated on/before it."""
    hired = roster["hire_date"] <= as_of
    still_employed = roster["termination_date"].isna() | (roster["termination_date"] > as_of)
    return roster[hired & still_employed]


def period_label(period: pd.Period) -> str:
    return period.strftime("%Y-%m")


def finalize(rows: list[dict[str, object]], departments: list[str]) -> pd.DataFrame:
    """Build the canonical metric frame: sorted by period, departments A-Z, rollup last."""
    frame = pd.DataFrame(rows, columns=METRIC_COLUMNS)
    order = {name: i for i, name in enumerate([*departments, ALL_DEPARTMENTS])}
    frame["value"] = frame["value"].astype(float).round(2)
    frame = frame.sort_values(["period", "department"], key=lambda s: s.map(order) if s.name == "department" else s)
    return frame.reset_index(drop=True)
