# Security Policy

Maintained by **Mourad Soltani — AGI Architect**.

## Reporting

**Do not open a public issue for security problems.** Use GitHub's
private "Report a vulnerability" button.

Include: description, impact, reproduction steps, affected version.

Ack within 72h, remediation timeline within 7 days.

## Scope

In scope: auth bypass, SSRF via config.yaml, SQL injection in tracker.py,
path traversal in scripts.

Out of scope: upstream provider quota behaviour, DoS via legitimate traffic,
third-party dependency issues.

## Hardening checklist

- Strong `LITELLM_MASTER_KEY` (>=32 random bytes)
- Terminate TLS via nginx/Caddy — never expose the gateway directly
- Restrict `/metrics` to your monitoring network
- `.env` mode 600, owned by the service user
- systemd hardening directives shipped in the unit file

---

*© 2026 Mourad Soltani — Mourad Soltani Technologies™ @MST*
