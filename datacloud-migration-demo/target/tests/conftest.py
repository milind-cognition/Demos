import os
import sys

import pytest

DEMO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if DEMO_ROOT not in sys.path:
    sys.path.insert(0, DEMO_ROOT)

from target.lib.spark import get_spark  # noqa: E402


@pytest.fixture(scope="session")
def spark():
    session = get_spark("hrdp-tests")
    yield session
    session.stop()
