# Quota Shield (optional Jev / TypeSafe)

> Author: Mourad Soltani — Mourad Soltani Technologies™ @MST  
> Status: **Optional** — core Free AI Gateway runs without it.

## Purpose

Protect free-tier RPM/RPD (Groq / Gemini / OpenRouter) by classifying a prompt
**before** any `free-llm-router` call.

```
task → Jev (optional) → SPAM / low urgency → drop (no free LLM)
                      → ANSWER / TOOL      → free-llm-router
```

Jev is **not** a chat model and is **not** registered as `free-llm-router`.

## Enable

```bash
# .env
JEV_ENABLED=true
TYPESAFE_API_KEY=tsk_...
# JEV_FAIL_OPEN=true   # default: on Jev error, still call free LLM
# JEV_MIN_URGENCY=0.2  # below this → treat as drop
```

```bash
python agents/agent.py --task "Buy cheap viagra now!!!"
# → [quota-shield] Dropped before free LLM ...

python agents/agent.py --no-jev --task "Explain WAL mode"
# → always hits free LLM path
```

## Cost (honest)

- Indicative TypeSafe pricing: **~$0.042 per 1M input tokens** (verify on their site).
- Trial credits may apply for new accounts; **not free forever**.
- Timeout default 2s; failures follow `JEV_FAIL_OPEN` (default true).

## Design rules

| Rule | Why |
|------|-----|
| Default **off** | MIT core must work with only free LLM keys |
| Fail-**open** default | Gateway still answers if TypeSafe is down |
| Client/agent gate first | Matches this repo (LiteLLM owns `/v1/chat/completions`) |
| Separate ledger key `jev` | Do not mix with Groq free RPD semantics |

## Sellable packaging

- **Community:** shield code open, optional.
- **Turnkey / Pro:** we enable, tune thresholds, and wire keys safely.

---

© 2026 Mourad Soltani — Mourad Soltani Technologies™ @MST
