# Public demo on Fly.io

> Author: Mourad Soltani — Mourad Soltani Technologies™ @MST

## One-time

```bash
# install flyctl: https://fly.io/docs/hands-on/install-flyctl/
fly auth login
fly apps create free-ai-gateway-demo   # or use existing name in fly.toml
fly volumes create fag_data --region iad --size 1
```

## Secrets

```bash
fly secrets set \
  GROQ_API_KEY="gsk_..." \
  GEMINI_API_KEY="AIza..." \
  OPENROUTER_API_KEY="sk-or-..." \
  LITELLM_MASTER_KEY="sk-$(openssl rand -hex 24)" \
  CONTROL_PLANE_ADMIN_TOKEN="adm-$(openssl rand -hex 16)"
```

## Deploy

```bash
fly deploy
fly status
fly open
```

Public base URL: `https://free-ai-gateway-demo.fly.dev`

### Seed a demo tenant

```bash
fly ssh console -C "python -m control_plane.cli tenant create Demo --rpm 10 --rpd 100"
fly ssh console -C "python -m control_plane.cli key create ten_..."
```

Or via admin API with `CONTROL_PLANE_ADMIN_TOKEN`.

### Buyer test

```bash
curl https://free-ai-gateway-demo.fly.dev/health
curl https://free-ai-gateway-demo.fly.dev/v1/chat/completions \
  -H "Authorization: Bearer sk-fag-DEMO_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"free-llm-router","messages":[{"role":"user","content":"Say hello in one sentence."}]}'
```

## Rate limits

Demo tenants should use low RPM/RPD so free quotas last. Rotate keys if abused.

---

© 2026 Mourad Soltani — Mourad Soltani Technologies™ @MST
