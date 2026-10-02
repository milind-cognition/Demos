import shutil

import pandas as pd
import pytest

from metrics.snapshot import SnapshotError, active_on, load_snapshot


def test_loads_typed_frames(mini_snapshot_dir):
    snapshot = load_snapshot(mini_snapshot_dir)
    assert pd.api.types.is_datetime64_any_dtype(snapshot.employees["hire_date"])
    assert pd.api.types.is_float_dtype(snapshot.timecards["overtime_hours"])
    assert snapshot.employees["hourly_rate"].sum() == pytest.approx(216.0)


def test_periods_span_timecards(mini_snapshot_dir):
    periods = load_snapshot(mini_snapshot_dir).periods
    assert [str(p) for p in periods] == ["2026-01", "2026-02", "2026-03"]


def test_staffed_departments_exclude_empty_department(mini_snapshot_dir):
    assert load_snapshot(mini_snapshot_dir).staffed_departments == ["Analytics", "Assembly"]


def test_active_on_treats_termination_date_as_last_day_exclusive(mini_snapshot_dir):
    roster = load_snapshot(mini_snapshot_dir).employee_roster()
    assert "E5" in set(active_on(roster, pd.Timestamp("2026-03-30"))["employee_id"])
    assert "E5" not in set(active_on(roster, pd.Timestamp("2026-03-31"))["employee_id"])


def test_missing_file_raises_clear_error(tmp_path, mini_snapshot_dir):
    shutil.copytree(mini_snapshot_dir, tmp_path / "snap")
    (tmp_path / "snap" / "timecards.csv").unlink()
    with pytest.raises(SnapshotError, match="timecards.csv"):
        load_snapshot(tmp_path / "snap")


def test_missing_column_raises_clear_error(tmp_path, mini_snapshot_dir):
    shutil.copytree(mini_snapshot_dir, tmp_path / "snap")
    path = tmp_path / "snap" / "employees.csv"
    pd.read_csv(path).drop(columns=["hourly_rate"]).to_csv(path, index=False)
    with pytest.raises(SnapshotError, match="hourly_rate"):
        load_snapshot(tmp_path / "snap")
