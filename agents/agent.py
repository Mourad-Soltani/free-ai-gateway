#!/usr/bin/env python3
"""
agents/agent.py — Free AI Gateway native agent (tool-using, multi-step).

Routes every LLM call through the Free AI Gateway (Groq → Gemini → OpenRouter)
with local quota accounting. Includes simple tools: time, calculator, quota stats.

Optional Quota Shield (Jev / TypeSafe): when JEV_ENABLED=true, classifies the
task before any free-LLM call so spam/low-urgency prompts do not burn RPM/RPD.
Core gateway works with Jev off (default).

Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST
Usage:
  python agents/agent.py --task "What is 17 * 23 and current UTC time?"
  python agents/agent.py --interactive
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Allow running from repo root or agents/
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("free_ai_gateway.agent")

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def tool_utc_now(_: str = "") -> str:
    """Return current UTC time in ISO-8601."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tool_calculator(expression: str) -> str:
    """Evaluate a simple arithmetic expression (digits, + - * / ( ) . only)."""
    expr = expression.strip()
    if not re.fullmatch(r"[0-9+\-*/().\s]+", expr):
        return "error: only digits and + - * / ( ) . allowed"
    try:
        # Restricted eval — no names, no builtins
        result = eval(expr, {"__builtins__": {}}, {})  # noqa: S307
        return str(result)
    except Exception as exc:
        return f"error: {exc}"


def tool_quota_stats(_: str = "") -> str:
    """Return local Free AI Gateway quota snapshot (RPM / RPD per provider)."""
    try:
        from tracker import APIRateTracker

        t = APIRateTracker()
        try:
            stats = t.stats()
        finally:
            t.close()
        return json.dumps(stats, indent=2)
    except Exception as exc:
        return f"error reading quota ledger: {exc}"


def tool_echo(text: str) -> str:
    """Echo back the input (debug / identity check)."""
    return text


TOOLS: dict[str, dict[str, Any]] = {
    "utc_now": {
        "fn": tool_utc_now,
        "description": "Return the current UTC timestamp (ISO-8601).",
        "args": "optional empty string",
    },
    "calculator": {
        "fn": tool_calculator,
        "description": "Evaluate arithmetic: digits and + - * / ( ) . only.",
        "args": "expression string, e.g. '(17 + 3) * 2'",
    },
    "quota_stats": {
        "fn": tool_quota_stats,
        "description": "Return Free AI Gateway local RPM/RPD usage per provider.",
        "args": "optional empty string",
    },
    "echo": {
        "fn": tool_echo,
        "description": "Echo the given text back unchanged.",
        "args": "any text",
    },
}


def _tool_catalogue() -> str:
    lines = []
    for name, meta in TOOLS.items():
        lines.append(f"- {name}({meta['args']}): {meta['description']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM via gateway client
# ---------------------------------------------------------------------------

def _call_llm(messages: list[dict[str, str]], *, temperature: float = 0.2) -> str:
    """Route chat completion through Free AI Gateway client (failover + quota)."""
    try:
        import client as gateway_client
    except ImportError as exc:
        raise RuntimeError(
            "Cannot import client.py — run from repo root or ensure PYTHONPATH."
        ) from exc

    # Build a single user blob that includes history for the simple client API
    # Prefer direct OpenAI SDK against gateway if available
    from openai import OpenAI

    url = os.getenv("GATEWAY_URL", "http://localhost:4000")
    key = os.getenv("LITELLM_MASTER_KEY", "sk-no-key-required")
    oai = OpenAI(base_url=url, api_key=key, max_retries=0)

    # Use primary model alias; gateway handles failover
    model = "free-llm-router"
    for provider in gateway_client.PROVIDERS:
        if gateway_client.tracker.is_allowed(
            provider.name, provider.max_rpm, provider.max_rpd
        ):
            model = provider.model
            break
        log.info("skip %s — local quota exhausted", provider.name)
    else:
        raise RuntimeError("All free providers at local quota ceiling")

    log.info("agent routing -> model=%s", model)
    response = oai.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        timeout=float(os.getenv("REQUEST_TIMEOUT", "60")),
    )
    # Record against the provider that owns this model alias
    for provider in gateway_client.PROVIDERS:
        if provider.model == model:
            gateway_client.tracker.record_request(provider.name)
            break
    return (response.choices[0].message.content or "").strip()


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = f"""You are Free AI Agent, a concise assistant that runs on Free AI Gateway™
(Mourad Soltani Technologies™ @MST). You have tools. When you need a tool, reply with EXACTLY one line:

TOOL <name> <argument>

Valid tools:
{_tool_catalogue()}

Rules:
- Use a tool only when needed; otherwise answer directly.
- After a tool result is provided, continue reasoning and either call another tool or give the final answer.
- Final answers must NOT start with "TOOL ".
- Keep answers short and factual.
"""


TOOL_RE = re.compile(r"^TOOL\s+(\w+)\s*(.*)$", re.IGNORECASE | re.DOTALL)


def run_agent(
    task: str,
    *,
    max_steps: int = 6,
    temperature: float = 0.2,
    verbose: bool = True,
    use_jev: bool | None = None,
) -> str:
    """Multi-step tool loop. Returns final natural-language answer.

    Optional Jev quota shield (see providers/typesafe.py): when enabled, SPAM or
    low-urgency tasks return early without calling free LLM providers.
    """
    # --- optional Quota Shield (Jev) — never required ---
    if use_jev is None:
        use_jev = True  # honour env; call_jev no-ops when disabled
    if use_jev:
        try:
            from providers.typesafe import call_jev, jev_enabled

            if jev_enabled():
                decision = call_jev(task)
                if verbose:
                    log.info(
                        "quota shield: route=%s urgency=%.2f skipped=%s reason=%s",
                        decision.route,
                        decision.urgency,
                        decision.skipped,
                        decision.reason,
                    )
                if not decision.allow_llm:
                    msg = (
                        f"[quota-shield] Dropped before free LLM "
                        f"(route={decision.route}, urgency={decision.urgency:.2f}). "
                        "Free-tier RPM/RPD not consumed."
                    )
                    if verbose:
                        print(msg)
                    return msg
        except Exception as exc:
            log.warning("quota shield error (continuing to LLM): %s", exc)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    for step in range(1, max_steps + 1):
        if verbose:
            log.info("agent step %d/%d", step, max_steps)
        reply = _call_llm(messages, temperature=temperature)
        if verbose:
            print(f"\n--- step {step} ---\n{reply}\n")

        m = TOOL_RE.match(reply.strip())
        if not m:
            return reply  # final answer

        name, arg = m.group(1).lower(), m.group(2).strip()
        if name not in TOOLS:
            tool_result = f"error: unknown tool '{name}'"
        else:
            try:
                tool_result = TOOLS[name]["fn"](arg)
            except Exception as exc:
                tool_result = f"error: {exc}"

        if verbose:
            print(f"[tool {name}] -> {tool_result[:500]}")

        messages.append({"role": "assistant", "content": reply})
        messages.append(
            {
                "role": "user",
                "content": f"TOOL_RESULT {name}:\n{tool_result}\n\nContinue. If done, give the final answer.",
            }
        )

    return "Agent stopped: max steps reached without a final answer."


def interactive_loop(*, use_jev: bool = True) -> int:
    print("Free AI Agent (interactive). Commands: /stats  /quit")
    print("Gateway:", os.getenv("GATEWAY_URL", "http://localhost:4000"))
    while True:
        try:
            line = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line in {"/quit", "/exit", "quit", "exit"}:
            return 0
        if line == "/stats":
            print(tool_quota_stats(""))
            continue
        try:
            answer = run_agent(line, verbose=True, use_jev=use_jev)
            print(f"\nAgent> {answer}")
        except Exception as exc:
            log.error("%s", exc)
            print(f"Error: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Free AI Gateway native agent (tools + multi-step).",
        epilog="Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST",
    )
    parser.add_argument("--task", "-t", default=None, help="One-shot task to solve")
    parser.add_argument("--interactive", "-i", action="store_true")
    parser.add_argument("--max-steps", type=int, default=6)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--no-jev",
        action="store_true",
        help="Disable optional Jev quota shield for this run",
    )
    args = parser.parse_args(argv)

    if args.interactive or not args.task:
        if not args.task and not args.interactive:
            # default demo task when nothing given
            demo = (
                "Compute (17 + 6) * 3 using the calculator tool, "
                "then report the current UTC time, and summarise quota_stats in one sentence."
            )
            print(f"No --task given; running demo:\n  {demo}\n")
            try:
                print(run_agent(demo, max_steps=args.max_steps, temperature=args.temperature, verbose=not args.quiet, use_jev=not args.no_jev))
                return 0
            except Exception as exc:
                log.error("%s", exc)
                print(
                    "\nHint: start the gateway first (./run.sh) and ensure .env has keys.",
                    file=sys.stderr,
                )
                return 1
        return interactive_loop(use_jev=not args.no_jev)

    try:
        out = run_agent(
            args.task,
            max_steps=args.max_steps,
            temperature=args.temperature,
            verbose=not args.quiet,
            use_jev=not args.no_jev,
        )
        print(out)
        return 0
    except Exception as exc:
        log.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())


# © 2026 Mourad Soltani — Mourad Soltani Technologies™ @MST
