"""Client routing tests.

Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST
"""
from unittest.mock import MagicMock, patch

import pytest

import client as gateway_client
from tracker import APIRateTracker


@pytest.fixture()
def fresh_tracker(tmp_path, monkeypatch):
    t = APIRateTracker(str(tmp_path / "c.db"))
    monkeypatch.setattr(gateway_client, "tracker", t)
    return t


def _fake_response(content="hello"):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    return resp


def test_happy_path_uses_primary(fresh_tracker):
    with patch.object(gateway_client._client.chat.completions, "create",
                      return_value=_fake_response("ok")) as mock_create:
        out = gateway_client.query_llm("hi")
    assert out == "ok"
    assert mock_create.call_args.kwargs["model"] == "free-llm-router"
    assert fresh_tracker.usage("groq")[0] == 1


def test_falls_back_on_hard_failure(fresh_tracker):
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs["model"])
        if kwargs["model"] == "free-llm-router":
            raise ValueError("boom")
        return _fake_response("fallback")

    with patch.object(gateway_client._client.chat.completions, "create",
                      side_effect=fake_create):
        out = gateway_client.query_llm("hi")
    assert out == "fallback"
    assert "free-llm-router-fallback-1" in calls
    assert fresh_tracker.usage("gemini")[0] == 1
