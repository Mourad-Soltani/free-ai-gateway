"""Quota-ledger tests.

Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST
"""
import time

from tracker import APIRateTracker


def test_allows_under_limit(tracker):
    assert tracker.is_allowed("groq", 30, 1000) is True


def test_rpm_ceiling_blocks(tracker):
    for _ in range(3):
        tracker.record_request("groq")
    assert tracker.is_allowed("groq", 3, 1000) is False
    assert tracker.usage("groq")[0] == 3


def test_rpd_ceiling_blocks(tracker):
    for _ in range(5):
        tracker.record_request("gemini")
    assert tracker.is_allowed("gemini", 100, 5) is False


def test_providers_are_isolated(tracker):
    for _ in range(5):
        tracker.record_request("groq")
    assert tracker.is_allowed("openrouter", 5, 5) is True


def test_check_and_record_is_atomic(tracker):
    assert tracker.check_and_record("groq", 2, 100) is True
    assert tracker.check_and_record("groq", 2, 100) is True
    assert tracker.check_and_record("groq", 2, 100) is False
    assert tracker.usage("groq")[0] == 2


def test_old_rows_expire_from_rpm_window(tracker):
    tracker.record_request("groq")
    assert tracker.is_allowed("groq", 1, 1000) is False
    tracker._conn.execute("UPDATE api_usage SET timestamp = ?;", (time.time() - 120,))
    assert tracker.is_allowed("groq", 1, 1000) is True


def test_stats_aggregates_across_providers(tracker):
    tracker.record_request("groq", count=3)
    tracker.record_request("gemini", count=2)
    stats = tracker.stats()
    assert stats["window_60s"].get("groq") == 3
    assert stats["window_60s"].get("gemini") == 2
    assert "groq" in stats["providers"]
    assert stats["schema_version"] == 1
    assert stats["gateway_version"] == "1.2.0"


def test_retention_prunes_old_rows(tmp_path):
    t = APIRateTracker(str(tmp_path / "r.db"), retention_days=0)
    t.record_request("groq")
    t2 = APIRateTracker(str(tmp_path / "r.db"), retention_days=0)
    assert t2.usage("groq")[0] == 0
    t.close(); t2.close()
