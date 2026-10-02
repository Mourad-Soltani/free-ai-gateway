"""Optional Jev quota shield tests.

Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST
"""
from unittest.mock import MagicMock, patch

from providers.typesafe import JevDecision, call_jev, jev_enabled


def test_jev_disabled_by_default(monkeypatch):
    monkeypatch.delenv("JEV_ENABLED", raising=False)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    assert jev_enabled() is False
    d = call_jev("hello")
    assert d.skipped is True
    assert d.allow_llm is True
    assert d.reason == "jev_disabled"


def test_jev_requires_key(monkeypatch):
    monkeypatch.setenv("JEV_ENABLED", "true")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    assert jev_enabled() is False


def test_fail_open_on_error(monkeypatch):
    monkeypatch.setenv("JEV_ENABLED", "true")
    monkeypatch.setenv("TYPESAFE_API_KEY", "tsk_test")
    monkeypatch.setenv("JEV_FAIL_OPEN", "true")
    with patch("providers.typesafe.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.side_effect = RuntimeError("down")
        d = call_jev("hello")
    assert d.skipped is True
    assert d.allow_llm is True
    assert "fail_open" in d.reason


def test_spam_blocks_llm(monkeypatch):
    monkeypatch.setenv("JEV_ENABLED", "true")
    monkeypatch.setenv("TYPESAFE_API_KEY", "tsk_test")
    payload = {"route": {"value": "SPAM"}, "urgency": {"value": 0.9}}
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = payload
    with patch("providers.typesafe.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.return_value = mock_resp
        with patch("providers.typesafe.APIRateTracker", create=True):
            d = call_jev("buy now", record_usage=False)
    assert d.route == "SPAM"
    assert d.allow_llm is False


def test_decision_dataclass():
    d = JevDecision(route="ANSWER", urgency=0.8, raw=None, skipped=False)
    assert d.allow_llm is True
