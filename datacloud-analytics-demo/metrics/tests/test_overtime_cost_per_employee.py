import pandas as pd
import pytest

from metrics.overtime_cost_per_employee import compute_overtime_cost_per_employee
from metrics.schema import validate_metric_frame
from metrics.snapshot import ALL_DEPARTMENTS, active_on, load_snapshot

# mini_snapshot cohorts: Manufacturing (Assembly), Technology (Analytics), New Markets (no employees).
# Month-end active employees:
#   2026-01  Manufacturing E1,E2        = 2   Technology E4,E5,E6 = 3   total 5
#   2026-02  Manufacturing E1,E3        = 2   Technology E4,E5,E6 = 3   total 5   (E2 left 02-20)
#   2026-03  Manufacturing E1,E3        = 2   Technology E4,E6    = 2   total 4   (E5 left 03-31)
# Overtime cost = overtime_hours x hourly_rate x 1.5:
#   2026-01  E1 5h x 25 = 187.50
#   2026-02  E1 8h x 25 = 300.00, E2 2h x 22 = 66.00 (leaver, still counted), E6 4h x 30 = 180.00
#   2026-03  E1 10h x 25 = 375.00, E3 6h x 24 = 216.00


@pytest.fixture
def values(mini_snapshot_dir, as_lookup):
    return as_lookup(compute_overtime_cost_per_employee(mini_snapshot_dir))


def test_cost_per_employee_by_cohort(values):
    assert values[("2026-01", "Manufacturing")] == pytest.approx(93.75)  # 187.50 / 2
    assert values[("2026-01", "Technology")] == 0.0  # no overtime
    assert values[("2026-02", "Manufacturing")] == pytest.approx(183.0)  # (300 + 66) / 2
    assert values[("2026-02", "Technology")] == pytest.approx(60.0)  # 180 / 3
    assert values[("2026-03", "Manufacturing")] == pytest.approx(295.5)  # (375 + 216) / 2
    assert values[("2026-03", "Technology")] == 0.0  # 0 / 2


def test_company_rollup_is_total_cost_over_total_employees(values):
    assert values[("2026-01", ALL_DEPARTMENTS)] == pytest.approx(37.5)  # 187.50 / 5
    assert values[("2026-02", ALL_DEPARTMENTS)] == pytest.approx(109.2)  # 546 / 5
    assert values[("2026-03", ALL_DEPARTMENTS)] == pytest.approx(147.75)  # 591 / 4


def test_rollup_is_headcount_weighted_average_of_cohorts(values):
    # Feb: (183 x 2 + 60 x 3) / 5 = 109.2, whereas the simple mean of the three cohorts would be 81.0.
    assert values[("2026-02", ALL_DEPARTMENTS)] == pytest.approx((183.0 * 2 + 60.0 * 3) / 5)


def test_rollup_reconciles_on_seed_data(seed_data_dir):
    frame = compute_overtime_cost_per_employee(seed_data_dir)
    snapshot = load_snapshot(seed_data_dir)
    roster = snapshot.employee_roster().merge(snapshot.industry_cohorts, on="department_id")
    for period, group in frame.groupby("period"):
        active = active_on(roster, pd.Period(period, "M").end_time.normalize())
        headcount = active.groupby("cohort_name").size()
        cohorts = group[group["department"] != ALL_DEPARTMENTS]
        weighted = sum(row.value * headcount.get(row.department, 0) for row in cohorts.itertuples())
        rollup = group.loc[group["department"] == ALL_DEPARTMENTS, "value"].item()
        assert weighted / len(active) == pytest.approx(rollup, abs=0.01)


def test_cohort_without_employees_reports_zero(values):
    assert [values[(p, "New Markets")] for p in ("2026-01", "2026-02", "2026-03")] == [0.0, 0.0, 0.0]


def test_every_cohort_appears(mini_snapshot_dir, seed_data_dir):
    mini = compute_overtime_cost_per_employee(mini_snapshot_dir)
    assert list(mini["department"].unique()) == ["Manufacturing", "New Markets", "Technology", ALL_DEPARTMENTS]
    seed = compute_overtime_cost_per_employee(seed_data_dir)
    expected = set(load_snapshot(seed_data_dir).industry_cohorts["cohort_name"]) | {ALL_DEPARTMENTS}
    assert set(seed["department"]) == expected
    assert (seed.groupby("period").size() == len(expected)).all()


def test_satisfies_contract(mini_snapshot_dir):
    frame = compute_overtime_cost_per_employee(mini_snapshot_dir)
    validate_metric_frame(frame, "overtime_cost_per_employee")
    assert (frame["value"] >= 0).all()
    assert (frame["value"] == frame["value"].round(2)).all()
