"""
async_client.py — asyncio-native client for the Free AI Gateway.

Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import sys
from collections.abc import AsyncIterator

import openai
from dotenv import load_dotenv
from openai import AsyncOpenAI

from tracker import APIRateTracker

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("free_ai_gateway.async_client")

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:4000")
GATEWAY_KEY = os.getenv("LITELLM_MASTER_KEY", "sk-no-key-required")
BACKOFF_CAP = float(os.getenv("BACKOFF_CAP_SECONDS", "30"))

_OR_CREDIT = os.getenv("OPENROUTER_CREDIT_PURCHASED", "").lower() in {"1", "true", "yes"}

PROVIDERS = [
    {"name": "groq",       "model": "free-llm-router",            "rpm": 30, "rpd": 1000},
    {"name": "gemini",     "model": "free-llm-router-fallback-1", "rpm": 15, "rpd": 1000},
    {"name": "openrouter", "model": "free-llm-router-fallback-2", "rpm": 20,
     "rpd": 1000 if _OR_CREDIT else 50},
]

TRANSIENT_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

tracker = APIRateTracker()
_client = AsyncOpenAI(base_url=GATEWAY_URL, api_key=GATEWAY_KEY, max_retries=0)


def _backoff(attempt: int, base: float = 1.0) -> float:
    return min(BACKOFF_CAP, base * (2 ** (attempt - 1))) + random.uniform(0.0, 0.5)


def _status_of(exc: Exception) -> int | None:
    for attr in ("status_code", "http_status", "code"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            return val
    resp = getattr(exc, "response", None)
    if resp is not None:
        code = getattr(resp, "status_code", None)
        if isinstance(code, int):
            return code
    return None


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError,
                        openai.RateLimitError, openai.InternalServerError)):
        return True
    status = _status_of(exc)
    return status in TRANSIENT_STATUS if status else False


async def query_llm_async(prompt: str, *, system=None, temperature=0.7,
                          max_tokens=None, max_retries_per_provider=3,
                          timeout=60.0) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    failures: list[str] = []

    for provider in PROVIDERS:
        if not await asyncio.to_thread(
            tracker.is_allowed, provider["name"], provider["rpm"], provider["rpd"]
        ):
            log.info("skip %-10s — local quota window exhausted", provider["name"])
            continue
        log.info("async routing -> %s (%s)", provider["name"], provider["model"])
        for attempt in range(1, max_retries_per_provider + 1):
            try:
                response = await _client.chat.completions.create(
                    model=provider["model"], messages=messages,
                    temperature=temperature, timeout=timeout,
                    **({"max_tokens": max_tokens} if max_tokens else {}),
                )
                await asyncio.to_thread(tracker.record_request, provider["name"])
                return response.choices[0].message.content or ""
            except Exception as exc:
                status = _status_of(exc)
                if not _is_transient(exc):
                    failures.append(f"{provider['name']}: {exc}")
                    break
                if attempt == max_retries_per_provider:
                    failures.append(f"{provider['name']}: {status or exc}")
                    break
                delay = _backoff(attempt)
                log.warning("%s transient (status=%s) — retry %d/%d in %.2fs",
                            provider["name"], status, attempt,
                            max_retries_per_provider, delay)
                await asyncio.sleep(delay)

    raise RuntimeError(
        "All free API targets exhausted. "
        f"Failures: {'; '.join(failures) if failures else 'local rate limits'}"
    )


async def stream_llm_async(prompt: str, *, system=None, temperature=0.7,
                           max_tokens=None, timeout=60.0) -> AsyncIterator[str]:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    for provider in PROVIDERS:
        if not await asyncio.to_thread(
            tracker.is_allowed, provider["name"], provider["rpm"], provider["rpd"]
        ):
            continue
        try:
            stream = await _client.chat.completions.create(
                model=provider["model"], messages=messages,
                temperature=temperature, timeout=timeout, stream=True,
                **({"max_tokens": max_tokens} if max_tokens else {}),
            )
            await asyncio.to_thread(tracker.record_request, provider["name"])
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield delta
            return
        except Exception as exc:
            if not _is_transient(exc):
                continue
            log.warning("%s stream transient error: %s", provider["name"], exc)

    raise RuntimeError("All free API targets exhausted while streaming.")


async def _demo() -> None:
    out = await query_llm_async("List three benefits of WAL mode in SQLite.")
    print(out)


if __name__ == "__main__":
    try:
        asyncio.run(_demo())
    except KeyboardInterrupt:
        sys.exit(130)


# © 2026 Mourad Soltani — Mourad Soltani Technologies™ @MST
