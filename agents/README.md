# Free AI Agent

Gateway-native multi-step agent that routes **every** LLM call through Free AI Gateway™
(Groq → Gemini → OpenRouter free tiers) with local quota accounting.

## Tools

| Tool | Purpose |
|------|---------|
| `utc_now` | Current UTC timestamp (ISO-8601) |
| `calculator` | Safe arithmetic (`+ - * / ( )`) |
| `quota_stats` | Local RPM/RPD ledger snapshot |
| `echo` | Identity / debug |

## Usage

```bash
# one-shot
python agents/agent.py --task "What is (42 / 7) + 3? Also give UTC time."

# interactive
python agents/agent.py --interactive

# demo (no args)
python agents/agent.py
```

Requires a running gateway (`./run.sh`) and valid keys in `.env`.

## Quota Shield (optional)

When `JEV_ENABLED=true` and `TYPESAFE_API_KEY` is set, each task is classified
before any free-LLM call. SPAM / low urgency returns early without burning RPM.

```bash
export JEV_ENABLED=true TYPESAFE_API_KEY=tsk_...
python agents/agent.py --task "spam text"
python agents/agent.py --no-jev --task "force free LLM path"
```

See [docs/QUOTA_SHIELD.md](../docs/QUOTA_SHIELD.md).

## Design

- Tool calls are plain text: `TOOL <name> <arg>`
- Max steps configurable (`--max-steps`)
- Records usage against the provider chosen by the client router

---

© 2026 Mourad Soltani — Mourad Soltani Technologies™ @MST
