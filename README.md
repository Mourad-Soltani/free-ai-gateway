# Free AI Gateway™

[![CI](https://github.com/Mourad-Soltani/free-ai-gateway/actions/workflows/ci.yml/badge.svg)](https://github.com/Mourad-Soltani/free-ai-gateway/actions/workflows/ci.yml)
[![Pages](https://github.com/Mourad-Soltani/free-ai-gateway/actions/workflows/pages.yml/badge.svg)](https://github.com/Mourad-Soltani/free-ai-gateway/actions/workflows/pages.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/Mourad-Soltani/free-ai-gateway?include_prereleases&sort=semver)](https://github.com/Mourad-Soltani/free-ai-gateway/releases)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

> Author: **Mourad Soltani** — *AGI Architect*  
> Trademark: **Mourad Soltani Technologies™ @MST**  
> License: MIT · Version: **1.2.1** · Year: 2026 · Status: Production-Ready  
> Site: [mourad-soltani.github.io/free-ai-gateway](https://mourad-soltani.github.io/free-ai-gateway/)

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
| Landing page | `landing/index.html` — product site |
| AI agent | `agents/agent.py` — tool-using agent via gateway |

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

    git clone https://github.com/Mourad-Soltani/free-ai-gateway
    cd free-ai-gateway
    ./install.sh
    nano .env
    ./run.sh
    python client.py --stats
    make health
    python agents/agent.py --task "What is 17*3? Give UTC time too."

Generate master key:

    python -c "import secrets; print('sk-' + secrets.token_urlsafe(32))"

## Model names (2026 verified)

| model | Upstream | Free ceiling |
|---|---|---|
| free-llm-router | Groq llama-3.3-70b-versatile | 30 RPM / 1,000 RPD |
| free-llm-router-fallback-1 | Gemini gemini-2.5-flash-lite | ~15 RPM / 1,000 RPD |
| free-llm-router-fallback-2 | OpenRouter llama-3.3-70b:free | 20 RPM / 50 RPD (1,000 after $10 credit) |

Aggregate capacity: ~65 RPM / ~1,050–2,050 RPD.

## Landing page

Open the product page locally:

    open landing/index.html
    # or serve: python -m http.server 8080 --directory landing

## AI agent

Multi-step tool agent that routes through the gateway:

    python agents/agent.py --task "Compute (10+5)*2 and show quota stats"
    python agents/agent.py --interactive

Tools: `utc_now`, `calculator`, `quota_stats`, `echo`. See [agents/README.md](agents/README.md).

## Quota Shield (optional)

Optional **Jev / TypeSafe** decision layer runs *before* free LLM calls so spam
and low-urgency prompts do not consume Groq/Gemini/OpenRouter RPM/RPD.

- **Default: off** — core gateway needs no TypeSafe key
- Enable: `JEV_ENABLED=true` + `TYPESAFE_API_KEY` in `.env`
- Agent: automatic when enabled; disable per run with `--no-jev`
- Docs: [docs/QUOTA_SHIELD.md](docs/QUOTA_SHIELD.md)

## Commercial licensing


See [COMMERCIAL.md](COMMERCIAL.md).

## Trademark

See [TRADEMARK.md](TRADEMARK.md).

## License

MIT © 2026 **Mourad Soltani — Mourad Soltani Technologies™ @MST**.
