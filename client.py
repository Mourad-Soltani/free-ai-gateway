"""
client.py — resilient OpenAI-compatible client for the Free AI Gateway.

Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass

import openai
from dotenv import load_dotenv
from openai import OpenAI

from tracker import APIRateTracker

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("free_ai_gateway.client")


@dataclass(frozen=True)
class Provider:
    name: str
    model: str
    max_rpm: int
    max_rpd: int
    notes: str = ""


_OR_CREDIT = os.getenv("OPENROUTER_CREDIT_PURCHASED", "").lower() in {"1", "true", "yes"}

PROVIDERS: list[Provider] = [
    Provider("groq",       "free-llm-router",             30, 1000,
             "llama-3.3-70b-versatile · 30 RPM / 1,000 RPD"),
    Provider("gemini",     "free-llm-router-fallback-1",  15, 1000,
             "gemini-2.5-flash-lite · ~15 RPM / 1,000 RPD"),
    Provider("openrouter", "free-llm-router-fallback-2",  20,
             1000 if _OR_CREDIT else 50,
             "meta-llama/llama-3.3-70b-instruct:free · 50 RPD free / 1,000 after $10 credit"),
]

TRANSIENT_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:4000")
GATEWAY_KEY = os.getenv("LITELLM_MASTER_KEY", "sk-no-key-required")
BACKOFF_CAP = float(os.getenv("BACKOFF_CAP_SECONDS", "30"))

tracker = APIRateTracker()
_client = OpenAI(base_url=GATEWAY_URL, api_key=GATEWAY_KEY, max_retries=0)


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


def _retry_after(exc: Exception) -> float | None:
    resp = getattr(exc, "response", None)
    if resp is None:
        return None
    headers = getattr(resp, "headers", None)
    if not headers:
        return None
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if not raw:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError,
                        openai.RateLimitError, openai.InternalServerError)):
        return True
    status = _status_of(exc)
    return status in TRANSIENT_STATUS if status else False


def _build_messages(prompt: str, system: str | None) -> list:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    return msgs


def _handle_exception(exc, provider, attempt, max_retries, failures) -> bool:
    status = _status_of(exc)
    if not _is_transient(exc):
        log.error("%s hard failure: %s", provider.name, exc)
        failures.append(f"{provider.name}: {exc}")
        return False
    if attempt == max_retries:
        log.warning("%s exhausted %d attempts (last status=%s)",
                    provider.name, attempt, status)
        failures.append(f"{provider.name}: {status or exc}")
        return False
    delay = _retry_after(exc) or _backoff(attempt)
    log.warning("%s transient (status=%s) — retry %d/%d in %.2fs",
                provider.name, status, attempt, max_retries, delay)
    time.sleep(delay)
    return True


def query_llm(prompt, *, system=None, temperature=0.7, max_tokens=None,
              max_retries_per_provider=3, timeout=60.0) -> str:
    messages = _build_messages(prompt, system)
    failures: list[str] = []
    for provider in PROVIDERS:
        if not tracker.is_allowed(provider.name, provider.max_rpm, provider.max_rpd):
            log.info("skip %-10s — local quota window exhausted", provider.name)
            continue
        log.info("routing -> %s (%s)", provider.name, provider.model)
        for attempt in range(1, max_retries_per_provider + 1):
            try:
                response = _client.chat.completions.create(
                    model=provider.model, messages=messages,
                    temperature=temperature, timeout=timeout,
                    **({"max_tokens": max_tokens} if max_tokens else {}),
                )
                tracker.record_request(provider.name)
                return response.choices[0].message.content or ""
            except Exception as exc:
                if not _handle_exception(exc, provider, attempt,
                                          max_retries_per_provider, failures):
                    break
    raise RuntimeError(
        "All free API targets exhausted or unreachable. "
        f"Failures: {'; '.join(failures) if failures else 'local rate limits'}"
    )


def stream_llm(prompt, *, system=None, temperature=0.7, max_tokens=None,
               timeout=60.0) -> Iterator[str]:
    messages = _build_messages(prompt, system)
    for provider in PROVIDERS:
        if not tracker.is_allowed(provider.name, provider.max_rpm, provider.max_rpd):
            continue
        try:
            stream = _client.chat.completions.create(
                model=provider.model, messages=messages,
                temperature=temperature, timeout=timeout, stream=True,
                **({"max_tokens": max_tokens} if max_tokens else {}),
            )
            tracker.record_request(provider.name)
            for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield delta
            return
        except Exception as exc:
            if not _is_transient(exc):
                continue
            log.warning("%s stream transient: %s", provider.name, exc)
    raise RuntimeError("All free API targets exhausted while streaming.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Query the Free AI Gateway.",
        epilog="Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST",
    )
    parser.add_argument("prompt", nargs="?",
                        default="Explain quantum computing in two concise bullet points.")
    parser.add_argument("--system", default=None)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args(argv)

    if args.stats:
        import json
        print(json.dumps(tracker.stats(), indent=2))
        return 0

    try:
        if args.stream:
            print("--- Output (streaming) ---")
            for chunk in stream_llm(args.prompt, system=args.system,
                                     temperature=args.temperature,
                                     max_tokens=args.max_tokens,
                                     timeout=args.timeout):
                sys.stdout.write(chunk)
                sys.stdout.flush()
            print()
        else:
            out = query_llm(args.prompt, system=args.system,
                            temperature=args.temperature,
                            max_tokens=args.max_tokens,
                            max_retries_per_provider=args.retries,
                            timeout=args.timeout)
            print(f"\n--- Output ---\n{out}\n")
    except RuntimeError as exc:
        log.error("%s", exc)
        return 1
    log.info("quota snapshot: %s", tracker.snapshot(PROVIDERS))
    return 0


if __name__ == "__main__":
    sys.exit(main())


# © 2026 Mourad Soltani — Mourad Soltani Technologies™ @MST
