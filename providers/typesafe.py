"""
providers/typesafe.py — optional Jev (TypeSafe) decision layer.

Quota shield: classify traffic BEFORE free LLM calls so Groq/Gemini/OpenRouter
RPM/RPD are not burned on spam or low-value prompts.

Not a chat model. Not part of free-llm-router.
Disabled unless JEV_ENABLED=true and TYPESAFE_API_KEY is set.
Default on failure: fail-open (allow the free LLM path).

Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger("free_ai_gateway.jev")

TYPESAFE_URL = os.getenv("TYPESAFE_URL", "https://api.typesafe.ai/v1/systemone")
JEV_MODEL = os.getenv("JEV_MODEL", "jev-latest")
JEV_TIMEOUT = float(os.getenv("JEV_TIMEOUT", "2.0"))


def _truthy(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


def jev_enabled() -> bool:
    """True only when explicitly enabled and a key is present."""
    if not _truthy("JEV_ENABLED", False):
        return False
    return bool(os.getenv("TYPESAFE_API_KEY", "").strip())


def jev_fail_open() -> bool:
    return _truthy("JEV_FAIL_OPEN", True)


@dataclass(frozen=True)
class JevDecision:
    """Normalized decision from Jev / fail-open fallback."""

    route: str  # ANSWER | SPAM | TOOL
    urgency: float
    raw: dict[str, Any] | None
    skipped: bool  # True if Jev was not called or failed open
    reason: str = ""

    @property
    def allow_llm(self) -> bool:
        if self.route == "SPAM":
            return False
        if self.urgency < float(os.getenv("JEV_MIN_URGENCY", "0.2")):
            return False
        return True


def _parse_decision(payload: dict[str, Any]) -> JevDecision:
    """Best-effort parse of TypeSafe systemone-style response."""
    route = "ANSWER"
    urgency = 1.0

    # Common shapes: {"route": {"value": "SPAM"}, "urgency": {"value": 0.1}}
    # or flat {"route": "SPAM", "urgency": 0.1} or answers list
    if "route" in payload:
        r = payload["route"]
        route = str(r.get("value", r) if isinstance(r, dict) else r).upper()
    if "urgency" in payload:
        u = payload["urgency"]
        try:
            urgency = float(u.get("value", u) if isinstance(u, dict) else u)
        except (TypeError, ValueError):
            urgency = 1.0

    # Alternate: answers / results array keyed by id
    for key in ("answers", "results", "questions"):
        items = payload.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            iid = str(item.get("id", "")).lower()
            val = item.get("value", item.get("answer"))
            if iid == "route" and val is not None:
                route = str(val).upper()
            if iid == "urgency" and val is not None:
                try:
                    urgency = float(val)
                except (TypeError, ValueError):
                    pass

    if route not in {"ANSWER", "SPAM", "TOOL"}:
        route = "ANSWER"

    return JevDecision(route=route, urgency=urgency, raw=payload, skipped=False)


def call_jev(
    state: str,
    questions: list[dict[str, Any]] | None = None,
    *,
    record_usage: bool = True,
) -> JevDecision:
    """
    Call TypeSafe Jev decision API.

    When disabled or on error with fail-open: returns ANSWER (allow LLM).
    On error with fail-closed: returns SPAM (block LLM).
    """
    if not jev_enabled():
        return JevDecision(
            route="ANSWER",
            urgency=1.0,
            raw=None,
            skipped=True,
            reason="jev_disabled",
        )

    key = os.getenv("TYPESAFE_API_KEY", "").strip()
    qs = questions or [
        {
            "id": "route",
            "type": "choice",
            "options": ["ANSWER", "SPAM", "TOOL"],
        },
        {
            "id": "urgency",
            "type": "score",
            "description": "urgency 0-1",
        },
    ]

    try:
        with httpx.Client(timeout=JEV_TIMEOUT) as client:
            r = client.post(
                TYPESAFE_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": JEV_MODEL,
                    "state": state,
                    "questions": qs,
                },
            )
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        log.warning("Jev call failed: %s", exc)
        if jev_fail_open():
            return JevDecision(
                route="ANSWER",
                urgency=1.0,
                raw=None,
                skipped=True,
                reason=f"fail_open:{exc}",
            )
        return JevDecision(
            route="SPAM",
            urgency=0.0,
            raw=None,
            skipped=True,
            reason=f"fail_closed:{exc}",
        )

    if record_usage:
        try:
            from tracker import APIRateTracker

            APIRateTracker().record_request("jev")
        except Exception as exc:
            log.debug("jev usage record skipped: %s", exc)

    decision = _parse_decision(data if isinstance(data, dict) else {})
    log.info(
        "Jev decision route=%s urgency=%.2f allow_llm=%s",
        decision.route,
        decision.urgency,
        decision.allow_llm,
    )
    return decision


# © 2026 Mourad Soltani — Mourad Soltani Technologies™ @MST
