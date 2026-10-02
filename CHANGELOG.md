# Changelog

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
