import json
from pathlib import Path

from metrics.export import write_all
from metrics.registry import REGISTRY

DASHBOARD_METRICS_DIR = Path(__file__).resolve().parents[2] / "dashboard" / "public" / "metrics"


def test_writes_payload_per_metric_and_index(tmp_path, mini_snapshot_dir):
    write_all(mini_snapshot_dir, tmp_path)
    index = json.loads((tmp_path / "index.json").read_text())
    assert [m["key"] for m in index["metrics"]] == list(REGISTRY)

    headcount = json.loads((tmp_path / "headcount.json").read_text())
    assert headcount["periods"] == ["2026-01", "2026-02", "2026-03"]
    assert headcount["total"][-1] == {"period": "2026-03", "value": 4}
    assert [d["department"] for d in headcount["by_department"]] == ["Analytics", "Assembly"]
    assert isinstance(headcount["total"][0]["value"], int)


def test_removes_stale_metric_files(tmp_path, mini_snapshot_dir):
    (tmp_path / "retired_metric.json").write_text("{}")
    write_all(mini_snapshot_dir, tmp_path)
    assert not (tmp_path / "retired_metric.json").exists()


def test_checked_in_dashboard_json_is_up_to_date(tmp_path, seed_data_dir):
    """Fails when data/ or the engine changed without re-running scripts/compute_metrics.py."""
    write_all(seed_data_dir, tmp_path)
    expected = sorted(p.name for p in tmp_path.glob("*.json"))
    assert sorted(p.name for p in DASHBOARD_METRICS_DIR.glob("*.json")) == expected
    for name in expected:
        assert (DASHBOARD_METRICS_DIR / name).read_text() == (tmp_path / name).read_text(), name
