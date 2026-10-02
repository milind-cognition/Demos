import pytest

from metrics.snapshot import ALL_DEPARTMENTS
from metrics.turnover import compute_turnover


def test_turnover_rates(mini_snapshot_dir, as_lookup):
    values = as_lookup(compute_turnover(mini_snapshot_dir))
    assert values[("2026-01", "Assembly")] == 0.0
    assert values[("2026-02", "Assembly")] == 50.0  # 1 leaver / avg(2, 2)
    assert values[("2026-02", ALL_DEPARTMENTS)] == 20.0  # 1 / avg(5, 5)
    assert values[("2026-03", "Analytics")] == 40.0  # month-end leaver: 1 / avg(3, 2)
    assert values[("2026-03", ALL_DEPARTMENTS)] == pytest.approx(22.22)  # 1 / avg(5, 4)


def test_rollup_is_not_average_of_departments(mini_snapshot_dir, as_lookup):
    values = as_lookup(compute_turnover(mini_snapshot_dir))
    departments_mean = (values[("2026-02", "Assembly")] + values[("2026-02", "Analytics")]) / 2
    assert values[("2026-02", ALL_DEPARTMENTS)] != departments_mean
