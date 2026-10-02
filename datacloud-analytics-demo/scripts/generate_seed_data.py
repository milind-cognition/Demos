"""Generate the deterministic seed snapshot in ``data/``.

The CSVs are checked in; re-running this script must reproduce them byte for
byte (stdlib ``random`` with a fixed seed, no third-party dependencies).

    python scripts/generate_seed_data.py
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SEED = 1042

WINDOW_START = date(2025, 10, 1)
WINDOW_END = date(2026, 9, 30)


@dataclass(frozen=True)
class DepartmentSpec:
    department_id: str
    name: str
    cost_center: str
    cohort_id: str
    cohort_name: str
    naics_sector: str
    opening_headcount: int
    non_exempt_share: float
    weekly_ot_mean: float
    rate_range: tuple[float, float]
    monthly_attrition: float
    monthly_growth_hires: float
    titles: tuple[str, ...]
    ot_seasonality: dict[int, float] = field(default_factory=dict)


DEPARTMENTS: tuple[DepartmentSpec, ...] = (
    DepartmentSpec("D01", "Platform Engineering", "CC-1100", "TECH", "Technology", "51",
                   34, 0.15, 3.0, (52.0, 88.0), 0.009, 0.3,
                   ("Site Reliability Engineer", "Platform Engineer", "Infrastructure Technician")),
    DepartmentSpec("D02", "Product Engineering", "CC-1150", "TECH", "Technology", "51",
                   42, 0.10, 2.0, (48.0, 85.0), 0.011, 0.7,
                   ("Software Engineer", "QA Analyst", "Engineering Manager")),
    DepartmentSpec("D03", "Sales", "CC-1200", "PROSVC", "Professional Services", "54",
                   30, 0.20, 1.5, (32.0, 70.0), 0.022, 0.4,
                   ("Account Executive", "Sales Development Rep", "Sales Operations Analyst")),
    DepartmentSpec("D04", "Customer Success", "CC-1300", "PROSVC", "Professional Services", "54",
                   28, 0.85, 4.0, (24.0, 40.0), 0.020, 0.3,
                   ("Support Specialist", "Customer Success Manager", "Implementation Consultant"),
                   {1: 1.3, 2: 1.2}),
    DepartmentSpec("D05", "Finance", "CC-1400", "FINSVC", "Financial Services", "52",
                   16, 0.30, 3.0, (34.0, 72.0), 0.008, 0.1,
                   ("Financial Analyst", "Accountant", "Controller"),
                   {12: 1.6, 3: 1.4, 6: 1.4, 9: 1.4}),
    DepartmentSpec("D06", "Payroll Operations", "CC-1450", "FINSVC", "Financial Services", "52",
                   14, 0.80, 5.0, (26.0, 44.0), 0.010, 0.1,
                   ("Payroll Specialist", "Payroll Tax Analyst", "Payroll Supervisor"),
                   {12: 1.8, 1: 2.0}),
    DepartmentSpec("D07", "Warehouse Operations", "CC-1500", "LOGIS", "Transportation & Logistics", "49",
                   48, 0.95, 7.0, (19.0, 30.0), 0.030, 0.2,
                   ("Warehouse Associate", "Forklift Operator", "Shift Lead"),
                   {11: 1.7, 12: 1.9, 1: 0.8, 7: 1.1}),
    DepartmentSpec("D08", "Fleet Services", "CC-1550", "LOGIS", "Transportation & Logistics", "48",
                   22, 0.95, 6.0, (22.0, 34.0), 0.025, 0.1,
                   ("Delivery Driver", "Fleet Mechanic", "Dispatcher"),
                   {11: 1.4, 12: 1.6}),
    # Newly created department: mapped to a cohort, but no hires yet.
    DepartmentSpec("D09", "Field Services", "CC-1600", "FIELD", "Field Operations", "81",
                   0, 0.0, 0.0, (0.0, 0.0), 0.0, 0.0, ()),
)

SEASONAL_WAREHOUSE_HIRES = {date(2025, 10, 13): 6, date(2025, 11, 3): 8}
SEASONAL_END = date(2026, 1, 9)

VOLUNTARY_REASONS = ("Career opportunity", "Compensation", "Relocation", "Personal reasons", "Return to school")
INVOLUNTARY_REASONS = ("Performance", "Attendance", "Position eliminated")


@dataclass
class Employee:
    employee_id: str
    spec: DepartmentSpec
    job_title: str
    flsa_status: str
    employment_type: str
    hourly_rate: float
    hire_date: date
    termination_date: date | None = None
    termination_type: str = ""
    termination_reason: str = ""


def month_starts(start: date, end: date) -> list[date]:
    months, current = [], start.replace(day=1)
    while current <= end:
        months.append(current)
        current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
    return months


def month_end(month_start: date) -> date:
    return (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def random_day(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


class Generator:
    def __init__(self) -> None:
        self.rng = random.Random(SEED)
        self.employees: list[Employee] = []

    def hire(self, spec: DepartmentSpec, hire_date: date, *, seasonal: bool = False) -> Employee:
        rng = self.rng
        non_exempt = seasonal or rng.random() < spec.non_exempt_share
        low, high = spec.rate_range
        rate = rng.uniform(low, low + (high - low) * (0.6 if non_exempt else 1.0))
        employee = Employee(
            employee_id=f"E{len(self.employees) + 1:04d}",
            spec=spec,
            job_title="Seasonal Warehouse Associate" if seasonal else rng.choice(spec.titles),
            flsa_status="non_exempt" if non_exempt else "exempt",
            employment_type="part_time" if (non_exempt and rng.random() < 0.08) else "full_time",
            hourly_rate=round(rate, 2),
            hire_date=hire_date,
        )
        self.employees.append(employee)
        return employee

    def active(self, spec: DepartmentSpec, as_of: date) -> list[Employee]:
        return [
            e for e in self.employees
            if e.spec is spec and e.hire_date <= as_of
            and (e.termination_date is None or e.termination_date > as_of)
        ]

    def run(self) -> None:
        rng = self.rng
        for spec in DEPARTMENTS:
            for _ in range(spec.opening_headcount):
                self.hire(spec, random_day(rng, date(2017, 1, 9), date(2025, 9, 15)))

        warehouse = next(s for s in DEPARTMENTS if s.department_id == "D07")
        for hire_date, count in SEASONAL_WAREHOUSE_HIRES.items():
            for _ in range(count):
                seasonal = self.hire(warehouse, hire_date, seasonal=True)
                seasonal.termination_date = SEASONAL_END
                seasonal.termination_type = "involuntary"
                seasonal.termination_reason = "End of seasonal assignment"

        pending_backfills: list[tuple[date, DepartmentSpec]] = []
        for month in month_starts(WINDOW_START, WINDOW_END):
            last_day = month_end(month)
            for backfill_date, spec in [p for p in pending_backfills if month <= p[0] <= last_day]:
                self.hire(spec, backfill_date)
            pending_backfills = [p for p in pending_backfills if p[0] > last_day]

            for spec in DEPARTMENTS:
                if spec.opening_headcount == 0:
                    continue
                for employee in self.active(spec, month):
                    if employee.termination_date is not None or rng.random() >= spec.monthly_attrition:
                        continue
                    employee.termination_date = random_day(rng, month, last_day)
                    if rng.random() < 0.78:
                        employee.termination_type = "voluntary"
                        employee.termination_reason = rng.choice(VOLUNTARY_REASONS)
                    else:
                        employee.termination_type = "involuntary"
                        employee.termination_reason = rng.choice(INVOLUNTARY_REASONS)
                    if rng.random() < 0.85:
                        lag = timedelta(days=rng.randint(21, 70))
                        pending_backfills.append((employee.termination_date + lag, spec))
                growth = int(spec.monthly_growth_hires) + (rng.random() < spec.monthly_growth_hires % 1)
                for _ in range(growth):
                    self.hire(spec, random_day(rng, month, last_day))

    def timecards(self) -> list[dict[str, object]]:
        rng = self.rng
        rows: list[dict[str, object]] = []
        week = WINDOW_START + timedelta(days=(7 - WINDOW_START.weekday()) % 7)
        while week <= WINDOW_END:
            week_end = week + timedelta(days=4)
            for e in self.employees:
                if e.hire_date > week_end or (e.termination_date is not None and e.termination_date < week):
                    continue
                base = 40.0 if e.employment_type == "full_time" else 24.0
                regular = base
                pto = rng.random()
                if pto < 0.05:
                    regular = base - 16.0
                elif pto < 0.13:
                    regular = base - 8.0
                overtime = 0.0
                if e.flsa_status == "non_exempt" and regular == base and rng.random() > 0.35:
                    mean = e.spec.weekly_ot_mean * e.spec.ot_seasonality.get(week.month, 1.0)
                    overtime = max(0.0, round(rng.gauss(mean, mean * 0.45) * 4) / 4)
                rows.append({
                    "employee_id": e.employee_id,
                    "week_start": week.isoformat(),
                    "regular_hours": f"{regular:.2f}",
                    "overtime_hours": f"{overtime:.2f}",
                })
            week += timedelta(days=7)
        return rows


def write_csv(path: Path, header: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    gen = Generator()
    gen.run()
    timecards = gen.timecards()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    write_csv(DATA_DIR / "departments.csv", ["department_id", "department_name", "cost_center"], [
        {"department_id": d.department_id, "department_name": d.name, "cost_center": d.cost_center}
        for d in DEPARTMENTS
    ])
    write_csv(DATA_DIR / "industry_cohorts.csv", ["department_id", "cohort_id", "cohort_name", "naics_sector"], [
        {"department_id": d.department_id, "cohort_id": d.cohort_id, "cohort_name": d.cohort_name,
         "naics_sector": d.naics_sector}
        for d in DEPARTMENTS
    ])
    write_csv(DATA_DIR / "employees.csv", [
        "employee_id", "department_id", "job_title", "flsa_status", "employment_type", "hourly_rate", "hire_date",
    ], [
        {"employee_id": e.employee_id, "department_id": e.spec.department_id, "job_title": e.job_title,
         "flsa_status": e.flsa_status, "employment_type": e.employment_type,
         "hourly_rate": f"{e.hourly_rate:.2f}", "hire_date": e.hire_date.isoformat()}
        for e in gen.employees
    ])
    write_csv(DATA_DIR / "terminations.csv", [
        "employee_id", "termination_date", "termination_type", "reason",
    ], [
        {"employee_id": e.employee_id, "termination_date": e.termination_date.isoformat(),
         "termination_type": e.termination_type, "reason": e.termination_reason}
        for e in sorted(gen.employees, key=lambda x: (x.termination_date or date.max, x.employee_id))
        if e.termination_date is not None
    ])
    write_csv(DATA_DIR / "timecards.csv", ["employee_id", "week_start", "regular_hours", "overtime_hours"], timecards)
    print(f"Wrote {len(gen.employees)} employees and {len(timecards)} timecards to {DATA_DIR}")


if __name__ == "__main__":
    main()
