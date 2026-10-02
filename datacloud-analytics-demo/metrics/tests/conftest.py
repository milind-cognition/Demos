from pathlib import Path

import pandas as pd
import pytest

DEMO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def mini_snapshot_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "mini_snapshot"


@pytest.fixture
def seed_data_dir() -> Path:
    return DEMO_ROOT / "data"


@pytest.fixture
def as_lookup():
    """Turn a metric frame into ``{(period, department): value}`` for compact assertions."""

    def _lookup(frame: pd.DataFrame) -> dict[tuple[str, str], float]:
        return {(row.period, row.department): row.value for row in frame.itertuples()}

    return _lookup
