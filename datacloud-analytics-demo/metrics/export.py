"""Serialize registered metrics to the JSON payloads the dashboard reads."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from metrics.registry import REGISTRY, MetricDefinition
from metrics.schema import validate_metric_frame
from metrics.snapshot import ALL_DEPARTMENTS

SCHEMA_VERSION = 1
INDEX_FILE = "index.json"


def _value(definition: MetricDefinition, raw: float) -> float | int:
    return int(round(raw)) if definition.unit == "count" else round(float(raw), 2)


def _series(definition: MetricDefinition, frame: pd.DataFrame) -> list[dict[str, object]]:
    return [{"period": row.period, "value": _value(definition, row.value)} for row in frame.itertuples()]


def build_payload(definition: MetricDefinition, frame: pd.DataFrame) -> dict[str, object]:
    validate_metric_frame(frame, definition.key)
    periods = sorted(frame["period"].unique().tolist())
    total = frame[frame["department"] == ALL_DEPARTMENTS]
    departments = frame[frame["department"] != ALL_DEPARTMENTS]
    return {
        "schema_version": SCHEMA_VERSION,
        "key": definition.key,
        "label": definition.label,
        "description": definition.description,
        "unit": definition.unit,
        "higher_is_better": definition.higher_is_better,
        "periods": periods,
        "total": _series(definition, total),
        "by_department": [
            {"department": name, "series": _series(definition, group)}
            for name, group in departments.groupby("department", sort=True)
        ],
    }


def _dump(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_all(data_dir: str | Path, out_dir: str | Path, keys: list[str] | None = None) -> list[Path]:
    """Compute every registered metric (or ``keys``) and write ``<key>.json`` plus ``index.json``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    selected = list(REGISTRY) if keys is None else keys
    unknown = [k for k in selected if k not in REGISTRY]
    if unknown:
        raise KeyError(f"Unknown metric(s): {', '.join(unknown)}")

    written: list[Path] = []
    for key in selected:
        definition = REGISTRY[key]
        payload = build_payload(definition, definition.compute(data_dir))
        path = out / f"{key}.json"
        _dump(path, payload)
        written.append(path)

    if keys is None:
        for stale in out.glob("*.json"):
            if stale.name != INDEX_FILE and stale.stem not in REGISTRY:
                stale.unlink()

    index = {
        "schema_version": SCHEMA_VERSION,
        "metrics": [
            {"key": d.key, "label": d.label, "unit": d.unit, "file": f"{d.key}.json"} for d in REGISTRY.values()
        ],
    }
    index_path = out / INDEX_FILE
    _dump(index_path, index)
    written.append(index_path)
    return written
