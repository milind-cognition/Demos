"""Metric registry: the single extension point for new metrics.

To add a metric, write ``compute_<name>(data_dir) -> DataFrame`` in its own
module and append a :class:`MetricDefinition` to ``_DEFINITIONS`` below.
See docs/ARCHITECTURE.md for the full flow.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from metrics.headcount import compute_headcount
from metrics.overtime import compute_overtime
from metrics.overtime_cost_per_employee import compute_overtime_cost_per_employee
from metrics.turnover import compute_turnover

Unit = Literal["count", "percent", "currency", "hours", "index"]
MetricFn = Callable[[str | Path], pd.DataFrame]

KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    label: str
    description: str
    unit: Unit
    higher_is_better: bool
    compute: MetricFn


_DEFINITIONS: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        key="headcount",
        label="Headcount",
        description="Active employees on the last day of the period.",
        unit="count",
        higher_is_better=True,
        compute=compute_headcount,
    ),
    MetricDefinition(
        key="turnover",
        label="Turnover Rate",
        description="Terminations in the period divided by average headcount.",
        unit="percent",
        higher_is_better=False,
        compute=compute_turnover,
    ),
    MetricDefinition(
        key="overtime",
        label="Overtime Rate",
        description="Overtime hours as a share of total hours worked.",
        unit="percent",
        higher_is_better=False,
        compute=compute_overtime,
    ),
    MetricDefinition(
        key="overtime_cost_per_employee",
        label="Overtime Cost per Employee",
        description="Overtime pay at 1.5x hourly rate divided by active employees, by industry cohort.",
        unit="currency",
        higher_is_better=False,
        compute=compute_overtime_cost_per_employee,
    ),
)


def _build(definitions: tuple[MetricDefinition, ...]) -> dict[str, MetricDefinition]:
    registry: dict[str, MetricDefinition] = {}
    for definition in definitions:
        if not KEY_PATTERN.match(definition.key):
            raise ValueError(f"Metric key {definition.key!r} must be snake_case")
        if definition.key in registry:
            raise ValueError(f"Duplicate metric key {definition.key!r}")
        registry[definition.key] = definition
    return registry


REGISTRY: dict[str, MetricDefinition] = _build(_DEFINITIONS)


def metric_keys() -> list[str]:
    return list(REGISTRY)


def get_metric(key: str) -> MetricDefinition:
    try:
        return REGISTRY[key]
    except KeyError:
        raise KeyError(f"Unknown metric {key!r}; known metrics: {', '.join(REGISTRY)}") from None
