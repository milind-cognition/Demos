import pytest

from metrics.overtime import compute_overtime
from metrics.snapshot import ALL_DEPARTMENTS


def test_overtime_share_of_hours(mini_snapshot_dir, as_lookup):
    values = as_lookup(compute_overtime(mini_snapshot_dir))
    assert values[("2026-01", "Assembly")] == pytest.approx(5.88)  # 5 / 85
    assert values[("2026-01", "Analytics")] == 0.0
    assert values[("2026-02", "Analytics")] == pytest.approx(3.85)  # 4 / 104
    assert values[("2026-02", ALL_DEPARTMENTS)] == pytest.approx(5.98)  # 14 / 234
    assert values[("2026-03", "Assembly")] == pytest.approx(16.67)  # 16 / 96
    assert values[("2026-03", ALL_DEPARTMENTS)] == 8.0  # 16 / 200


def test_values_are_rounded_to_two_places(mini_snapshot_dir):
    frame = compute_overtime(mini_snapshot_dir)
    assert (frame["value"] == frame["value"].round(2)).all()
