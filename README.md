# Free AI Gateway™

> Author: **Mourad Soltani** — *AGI Architect*
> Trademark: **Mourad Soltani Technologies™ @MST**
> License: MIT · Version: 1.2.0 · Year: 2026 · Status: Production-Ready

An OpenAI-compatible HTTP proxy that fuses the free tiers of Groq,
Google AI Studio (Gemini), and OpenRouter into a single, high-availability
endpoint — with local SQLite quota accounting, automatic failover,
streaming, Prometheus metrics, and health probes.

## Features

| Feature | Notes |
|---|---|
| OpenAI-compatible | Drop-in `base_url` swap |
| Automatic failover | Groq → Gemini → OpenRouter |
| Local quota ledger | SQLite WAL, RPM + RPD per provider |
| Atomic reservations | BEGIN IMMEDIATE prevents overshoot |
| Full-jitter backoff | Honours Retry-After |
| Streaming | Sync + async clients |
| Observability | Prometheus /metrics, health probes |
| Zero-trust | Master-key auth required |

## Health probes

| Endpoint | Level |
|---|---|
| /health/liveliness | live |
| /health/readiness | ready |
| /health/startup | startup |
| /metrics | deep |

    ./venv/bin/python healthcheck.py --level live
    ./venv/bin/python healthcheck.py --level full
    ./venv/bin/python healthcheck.py --deep --upstream

Exit codes: 0 healthy · 1 unreachable · 2 degraded · 3 DB error · 4 upstream error.

## Quickstart

    git clone https://github.com/mouradsoltani/free-ai-gateway
    cd free-ai-gateway
    ./install.sh
    nano .env
    ./run.sh
    python client.py --stats
    make health

Generate master key:

    python -c "import secrets; print('sk-' + secrets.token_urlsafe(32))"

## Model names (2026 verified)

| model | Upstream | Free ceiling |
|---|---|---|
| free-llm-router | Groq llama-3.3-70b-versatile | 30 RPM / 1,000 RPD |
| free-llm-router-fallback-1 | Gemini gemini-2.5-flash-lite | ~15 RPM / 1,000 RPD |
| free-llm-router-fallback-2 | OpenRouter llama-3.3-70b:free | 20 RPM / 50 RPD (1,000 after $10 credit) |

Aggregate capacity: ~65 RPM / ~1,050–2,050 RPD.

## Commercial licensing

See [COMMERCIAL.md](COMMERCIAL.md).

## Trademark

See [TRADEMARK.md](TRADEMARK.md).

## License

MIT © 2026 **Mourad Soltani — Mourad Soltani Technologies™ @MST**.
