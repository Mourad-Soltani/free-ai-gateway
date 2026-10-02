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
    db = str(tmp_path / "r.db")
    t = APIRateTracker(db, retention_days=7)
    t.record_request("groq")
    # Backdate the row so it falls outside the retention window
    old_ts = time.time() - 10 * 86400
    t._conn.execute(
        "UPDATE api_usage SET timestamp = ?, date_str = ?;",
        (old_ts, "2020-01-01"),
    )
    t.close()
    # Re-open triggers prune of date_str older than retention
    t2 = APIRateTracker(db, retention_days=7)
    assert t2.usage("groq")[0] == 0
    t2.close()
