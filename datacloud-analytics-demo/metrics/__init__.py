"""Workforce metrics engine.

Every metric is a function ``(data_dir) -> DataFrame[period, department, value]``
registered in :mod:`metrics.registry`.
"""

from metrics.registry import REGISTRY, MetricDefinition, get_metric, metric_keys
from metrics.snapshot import ALL_DEPARTMENTS, METRIC_COLUMNS, Snapshot, load_snapshot

__all__ = [
    "ALL_DEPARTMENTS",
    "METRIC_COLUMNS",
    "REGISTRY",
    "MetricDefinition",
    "Snapshot",
    "get_metric",
    "load_snapshot",
    "metric_keys",
]
