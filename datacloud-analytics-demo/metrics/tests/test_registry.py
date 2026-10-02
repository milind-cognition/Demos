import pandas as pd
import pytest

from metrics.registry import KEY_PATTERN, REGISTRY, get_metric, metric_keys
from metrics.schema import MetricFrameError, validate_metric_frame
from metrics.snapshot import ALL_DEPARTMENTS


def test_registered_metrics():
    assert metric_keys() == ["headcount", "turnover", "overtime", "overtime_cost_per_employee"]


def test_unknown_metric_lists_known_keys():
    with pytest.raises(KeyError, match="headcount"):
        get_metric("does_not_exist")


@pytest.mark.parametrize("key", list(REGISTRY))
def test_definition_metadata(key):
    definition = REGISTRY[key]
    assert KEY_PATTERN.match(definition.key)
    assert definition.label and definition.description.endswith(".")
    assert definition.unit in {"count", "percent", "currency", "hours", "index"}


@pytest.mark.parametrize("key", list(REGISTRY))
def test_every_metric_satisfies_contract_on_seed_data(key, seed_data_dir):
    frame = REGISTRY[key].compute(seed_data_dir)
    validate_metric_frame(frame, key)
    assert frame["period"].nunique() == 12


@pytest.mark.parametrize("key", list(REGISTRY))
def test_every_metric_is_deterministic(key, mini_snapshot_dir):
    compute = REGISTRY[key].compute
    pd.testing.assert_frame_equal(compute(mini_snapshot_dir), compute(mini_snapshot_dir))


def test_validator_rejects_missing_rollup():
    frame = pd.DataFrame({"period": ["2026-01"], "department": ["Sales"], "value": [1.0]})
    with pytest.raises(MetricFrameError, match=ALL_DEPARTMENTS):
        validate_metric_frame(frame, "example")


def test_validator_rejects_nulls():
    frame = pd.DataFrame({"period": ["2026-01"], "department": [ALL_DEPARTMENTS], "value": [float("nan")]})
    with pytest.raises(MetricFrameError, match="nulls"):
        validate_metric_frame(frame, "example")
