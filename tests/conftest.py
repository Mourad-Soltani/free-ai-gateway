"""Shared pytest fixtures.

Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST
"""
import pytest

from tracker import APIRateTracker


@pytest.fixture()
def tracker(tmp_path):
    t = APIRateTracker(
        str(tmp_path / "limits.db"),
        retention_days=7,
        busy_timeout_ms=2000,
    )
    yield t
    t.close()
