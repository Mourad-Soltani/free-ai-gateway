# Changelog

## [1.3.0] — 2026-10-03
### Added
- Multi-tenant **control plane** (`control_plane/`) — virtual keys, per-tenant RPM/RPD
- Edge proxy `:4100` → LiteLLM `:4000` with master key
- CLI: `python -m control_plane.cli`
- docs/CONTROL_PLANE.md

## [1.2.2] — 2026-10-03
### Added
- Optional Quota Shield (Jev / TypeSafe) — `providers/typesafe.py`
- Agent gate: drop SPAM/low-urgency before free LLM (`JEV_ENABLED`, `--no-jev`)
- docs/QUOTA_SHIELD.md

### Notes
- Shield is **off by default**; fail-open on Jev errors
- Not registered as free-llm-router

## [1.2.1] — 2026-10-02
### Added
- `landing/index.html` — product landing page (features, providers, agent demo, pricing)
- `agents/agent.py` — Free AI Gateway native multi-step tool agent
- `agents/README.md` — agent usage and tool catalogue

## [1.2.0] — 2026-01-15
### Added
- Trademark notice (TRADEMARK.md)
- COMMERCIAL.md — 2026 pricing model with dynamic quota multiplier
- Enhanced health system (liveliness, readiness, startup, deep probes)
- tests/test_healthcheck.py
- verify.sh — post-install sanity check

### Changed
- config.yaml ceilings annotated with 2026 verified values
- client.py PROVIDERS updated for OpenRouter $10-credit unlock
- pyproject.toml → v1.2.0, Production/Stable

### Fixed
- Healthcheck --deep closes tracker connection deterministically
- stats() returns schema_version

## [1.1.0] — 2026-01-02
- async_client.py, streaming, Retry-After honouring, healthcheck.py

## [1.0.0] — 2025-12-20
- Initial public release

---

*© 2026 Mourad Soltani — Mourad Soltani Technologies™ @MST*
