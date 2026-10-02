"""
control_plane/app.py — multi-tenant edge proxy in front of LiteLLM.

Clients authenticate with virtual keys (sk-fag-...).
Control plane enforces per-tenant RPM/RPD, then forwards to upstream
LiteLLM using LITELLM_MASTER_KEY.

Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST

Run:
  uvicorn control_plane.app:app --host 0.0.0.0 --port 4100
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from control_plane.db import ControlPlaneDB

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("free_ai_gateway.control_plane")

UPSTREAM = os.getenv("GATEWAY_URL", "http://127.0.0.1:4000").rstrip("/")
MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "")
ADMIN_TOKEN = os.getenv("CONTROL_PLANE_ADMIN_TOKEN", "")

db = ControlPlaneDB()
app = FastAPI(
    title="Free AI Gateway — Control Plane",
    version="0.1.0",
    description="Multi-tenant virtual keys + budgets in front of LiteLLM free-tier router.",
)

def _cors_origins() -> list[str]:
    if os.getenv("DEMO_MODE", "").lower() in {"1", "true", "yes"}:
        return ["*"]
    raw = os.getenv(
        "CORS_ORIGINS",
        "https://mourad-soltani.github.io,http://localhost:8080,http://127.0.0.1:8080",
    )
    return [o.strip() for o in raw.split(",") if o.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=os.getenv("DEMO_MODE", "").lower() not in {"1", "true", "yes"},
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Expected Bearer token")
    return parts[1].strip()


def _require_admin(authorization: str | None) -> None:
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="CONTROL_PLANE_ADMIN_TOKEN not configured")
    token = _extract_bearer(authorization)
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")


@app.on_event("shutdown")
def _shutdown() -> None:
    db.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "control-plane"}


@app.get("/v1/tenant/me")
def tenant_me(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    raw = _extract_bearer(authorization)
    ctx = db.resolve_key(raw)
    if not ctx:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return db.tenant_stats(ctx.tenant.id)


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    authorization: str | None = Header(default=None),
) -> Response:
    raw = _extract_bearer(authorization)
    ctx = db.resolve_key(raw)
    if not ctx:
        raise HTTPException(status_code=401, detail="Invalid API key")

    try:
        body: dict[str, Any] = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc

    model = body.get("model", "free-llm-router")
    allowed, reason = db.check_and_record(ctx.tenant, ctx.key, model=str(model))
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)

    if not MASTER_KEY:
        raise HTTPException(status_code=503, detail="LITELLM_MASTER_KEY not set on control plane")

    headers = {
        "Authorization": f"Bearer {MASTER_KEY}",
        "Content-Type": "application/json",
    }
    # Preserve stream flag
    stream = bool(body.get("stream"))

    timeout = float(os.getenv("REQUEST_TIMEOUT", "60"))
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            upstream = await client.post(
                f"{UPSTREAM}/v1/chat/completions",
                headers=headers,
                json=body,
            )
    except httpx.HTTPError as exc:
        log.error("upstream error tenant=%s: %s", ctx.tenant.id, exc)
        db.update_event_status(ctx.tenant.id, status_code=502)
        raise HTTPException(status_code=502, detail=f"Upstream unreachable: {exc}") from exc

    db.update_event_status(ctx.tenant.id, status_code=upstream.status_code)

    if stream:
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "text/event-stream"),
        )

    try:
        payload = upstream.json()
    except Exception:
        return Response(content=upstream.content, status_code=upstream.status_code)

    return JSONResponse(content=payload, status_code=upstream.status_code)


# --- Admin API (CONTROL_PLANE_ADMIN_TOKEN) ---


@app.post("/admin/tenants")
async def admin_create_tenant(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_admin(authorization)
    body = await request.json()
    name = body.get("name") or "tenant"
    tenant = db.create_tenant(
        name,
        rpm_limit=int(body.get("rpm_limit", 30)),
        rpd_limit=int(body.get("rpd_limit", 1000)),
        budget_usd=body.get("budget_usd"),
    )
    return {
        "id": tenant.id,
        "name": tenant.name,
        "rpm_limit": tenant.rpm_limit,
        "rpd_limit": tenant.rpd_limit,
        "budget_usd": tenant.budget_usd,
    }


@app.get("/admin/tenants")
def admin_list_tenants(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
    _require_admin(authorization)
    return [
        {
            "id": t.id,
            "name": t.name,
            "status": t.status,
            "rpm_limit": t.rpm_limit,
            "rpd_limit": t.rpd_limit,
        }
        for t in db.list_tenants()
    ]


@app.post("/admin/tenants/{tenant_id}/keys")
async def admin_create_key(
    tenant_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_admin(authorization)
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    try:
        meta, raw = db.create_key(tenant_id, name=str(body.get("name", "default")))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": meta.id,
        "tenant_id": meta.tenant_id,
        "name": meta.name,
        "key_prefix": meta.key_prefix,
        "api_key": raw,  # shown once
        "warning": "Store this key now; it cannot be retrieved again.",
    }


@app.get("/admin/tenants/{tenant_id}/stats")
def admin_tenant_stats(
    tenant_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_admin(authorization)
    if not db.get_tenant(tenant_id):
        raise HTTPException(status_code=404, detail="tenant not found")
    return db.tenant_stats(tenant_id)


@app.post("/admin/keys/{key_id}/revoke")
def admin_revoke_key(
    key_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    _require_admin(authorization)
    ok = db.revoke_key(key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="key not found")
    return {"status": "revoked", "key_id": key_id}


# © 2026 Mourad Soltani — Mourad Soltani Technologies™ @MST
