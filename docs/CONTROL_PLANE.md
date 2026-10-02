# Multi-tenant Control Plane (MVP)

> Author: Mourad Soltani — Mourad Soltani Technologies™ @MST  
> Version: 0.1.0

Edge layer in front of LiteLLM that adds **tenants**, **virtual API keys**, and
**per-tenant RPM/RPD** without changing the free-tier router core.

```
Client  --Bearer sk-fag-...-->  Control Plane :4100
                                    │  auth + tenant limits
                                    ▼
                               LiteLLM :4000  (master key)
                                    │
                          Groq → Gemini → OpenRouter
```

## Quick start

```bash
# terminal 1 — free-tier router
./run.sh

# terminal 2 — control plane
export CONTROL_PLANE_ADMIN_TOKEN="adm-$(openssl rand -hex 16)"
export LITELLM_MASTER_KEY="..."   # same as gateway
export GATEWAY_URL=http://127.0.0.1:4000
./run_control_plane.sh

# create tenant + key
python -m control_plane.cli tenant create "Acme" --rpm 20 --rpd 500
python -m control_plane.cli key create ten_...

# call via control plane (not :4000)
curl http://127.0.0.1:4100/v1/chat/completions \
  -H "Authorization: Bearer sk-fag-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"free-llm-router","messages":[{"role":"user","content":"hi"}]}'
```

## Admin HTTP

All `/admin/*` routes require `Authorization: Bearer $CONTROL_PLANE_ADMIN_TOKEN`.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/admin/tenants` | Create tenant |
| GET | `/admin/tenants` | List tenants |
| POST | `/admin/tenants/{id}/keys` | Issue virtual key (**shown once**) |
| GET | `/admin/tenants/{id}/stats` | RPM/RPD usage |
| POST | `/admin/keys/{id}/revoke` | Revoke key |

Tenant self-service: `GET /v1/tenant/me` with the virtual key.

## Env

```bash
CONTROL_PLANE_PORT=4100
CONTROL_PLANE_DB=control_plane.db
CONTROL_PLANE_ADMIN_TOKEN=...   # required for /admin
GATEWAY_URL=http://127.0.0.1:4000
LITELLM_MASTER_KEY=...          # upstream master key
```

## Security notes

- Virtual keys are stored as **SHA-256 hashes** only.
- Upstream provider keys never leave the LiteLLM process.
- Do not expose `:4000` publicly when using the control plane; expose `:4100` only.
- Rotate `CONTROL_PLANE_ADMIN_TOKEN` like a root password.

## Roadmap (not in MVP)

- Spend/budget hard-stop in USD  
- Per-key RPM  
- SSO / team roles  
- Stripe billing webhooks  
- UI dashboard  

## Commercial angle

| Free core | Paid control plane story |
|-----------|---------------------------|
| Single master key | Per-customer virtual keys |
| Shared free pool | Isolated RPM/RPD per tenant |
| Self-host DIY | Turnkey multi-tenant install |

---

© 2026 Mourad Soltani — Mourad Soltani Technologies™ @MST
