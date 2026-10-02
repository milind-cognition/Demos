from metrics.headcount import compute_headcount
from metrics.snapshot import ALL_DEPARTMENTS, METRIC_COLUMNS


def test_month_end_headcount(mini_snapshot_dir, as_lookup):
    values = as_lookup(compute_headcount(mini_snapshot_dir))
    assert values == {
        ("2026-01", "Analytics"): 3, ("2026-01", "Assembly"): 2, ("2026-01", ALL_DEPARTMENTS): 5,
        ("2026-02", "Analytics"): 3, ("2026-02", "Assembly"): 2, ("2026-02", ALL_DEPARTMENTS): 5,
        ("2026-03", "Analytics"): 2, ("2026-03", "Assembly"): 2, ("2026-03", ALL_DEPARTMENTS): 4,
    }


def test_frame_shape_and_order(mini_snapshot_dir):
    frame = compute_headcount(mini_snapshot_dir)
    assert list(frame.columns) == METRIC_COLUMNS
    assert frame["department"].tolist()[:3] == ["Analytics", "Assembly", ALL_DEPARTMENTS]


def test_department_without_employees_has_no_rows(mini_snapshot_dir):
    assert "Expansion" not in set(compute_headcount(mini_snapshot_dir)["department"])
