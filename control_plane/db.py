"""
control_plane/db.py — SQLite tenancy, virtual keys, budgets, usage.

Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST
"""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    rpm_limit   INTEGER NOT NULL DEFAULT 30,
    rpd_limit   INTEGER NOT NULL DEFAULT 1000,
    budget_usd  REAL,
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS api_keys (
    id           TEXT PRIMARY KEY,
    tenant_id    TEXT NOT NULL REFERENCES tenants(id),
    key_prefix   TEXT NOT NULL,
    key_hash     TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL DEFAULT 'default',
    status       TEXT NOT NULL DEFAULT 'active',
    created_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_keys_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_keys_tenant ON api_keys(tenant_id);

CREATE TABLE IF NOT EXISTS usage_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id   TEXT NOT NULL,
    key_id      TEXT,
    ts          REAL NOT NULL,
    date_str    TEXT NOT NULL,
    model       TEXT,
    status_code INTEGER,
    tokens_in   INTEGER DEFAULT 0,
    tokens_out  INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_usage_tenant_ts ON usage_events(tenant_id, ts);
CREATE INDEX IF NOT EXISTS idx_usage_tenant_day ON usage_events(tenant_id, date_str);
"""


def _utc_day(ts: float | None = None) -> str:
    dt = datetime.fromtimestamp(ts or time.time(), tz=timezone.utc)
    return dt.strftime("%Y-%m-%d")


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_virtual_key() -> str:
    return "sk-fag-" + secrets.token_urlsafe(24)


@dataclass
class Tenant:
    id: str
    name: str
    status: str
    rpm_limit: int
    rpd_limit: int
    budget_usd: float | None
    created_at: float


@dataclass
class ApiKey:
    id: str
    tenant_id: str
    key_prefix: str
    name: str
    status: str
    created_at: float


@dataclass
class AuthContext:
    tenant: Tenant
    key: ApiKey


class ControlPlaneDB:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or os.getenv("CONTROL_PLANE_DB", "control_plane.db")
        self._local = threading.local()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5.0, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    @property
    def _conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = self._connect()
            self._local.conn = c
        return c

    def close(self) -> None:
        c = getattr(self._local, "conn", None)
        if c is not None:
            c.close()
            self._local.conn = None

    def _init(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(SCHEMA)
        finally:
            conn.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Cursor]:
        cur = self._conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE;")
            yield cur
            cur.execute("COMMIT;")
        except BaseException:
            try:
                cur.execute("ROLLBACK;")
            except sqlite3.Error:
                pass
            raise
        finally:
            cur.close()

    # --- tenants ---

    def create_tenant(
        self,
        name: str,
        *,
        tenant_id: str | None = None,
        rpm_limit: int = 30,
        rpd_limit: int = 1000,
        budget_usd: float | None = None,
    ) -> Tenant:
        tid = tenant_id or ("ten_" + secrets.token_hex(8))
        now = time.time()
        with self._tx() as cur:
            cur.execute(
                "INSERT INTO tenants (id, name, status, rpm_limit, rpd_limit, budget_usd, created_at) "
                "VALUES (?, ?, 'active', ?, ?, ?, ?);",
                (tid, name, rpm_limit, rpd_limit, budget_usd, now),
            )
        return Tenant(tid, name, "active", rpm_limit, rpd_limit, budget_usd, now)

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        row = self._conn.execute("SELECT * FROM tenants WHERE id = ?;", (tenant_id,)).fetchone()
        if not row:
            return None
        return Tenant(
            row["id"], row["name"], row["status"], row["rpm_limit"],
            row["rpd_limit"], row["budget_usd"], row["created_at"],
        )

    def list_tenants(self) -> list[Tenant]:
        rows = self._conn.execute("SELECT * FROM tenants ORDER BY created_at;").fetchall()
        return [
            Tenant(r["id"], r["name"], r["status"], r["rpm_limit"], r["rpd_limit"], r["budget_usd"], r["created_at"])
            for r in rows
        ]

    # --- keys ---

    def create_key(self, tenant_id: str, name: str = "default") -> tuple[ApiKey, str]:
        """Returns (ApiKey metadata, raw_key once)."""
        if not self.get_tenant(tenant_id):
            raise ValueError(f"unknown tenant: {tenant_id}")
        raw = generate_virtual_key()
        kid = "key_" + secrets.token_hex(8)
        prefix = raw[:12]
        now = time.time()
        with self._tx() as cur:
            cur.execute(
                "INSERT INTO api_keys (id, tenant_id, key_prefix, key_hash, name, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'active', ?);",
                (kid, tenant_id, prefix, hash_key(raw), name, now),
            )
        meta = ApiKey(kid, tenant_id, prefix, name, "active", now)
        return meta, raw

    def resolve_key(self, raw_key: str) -> AuthContext | None:
        row = self._conn.execute(
            "SELECT k.*, t.name AS t_name, t.status AS t_status, t.rpm_limit, t.rpd_limit, "
            "t.budget_usd, t.created_at AS t_created "
            "FROM api_keys k JOIN tenants t ON t.id = k.tenant_id "
            "WHERE k.key_hash = ?;",
            (hash_key(raw_key),),
        ).fetchone()
        if not row:
            return None
        if row["status"] != "active" or row["t_status"] != "active":
            return None
        tenant = Tenant(
            row["tenant_id"], row["t_name"], row["t_status"], row["rpm_limit"],
            row["rpd_limit"], row["budget_usd"], row["t_created"],
        )
        key = ApiKey(row["id"], row["tenant_id"], row["key_prefix"], row["name"], row["status"], row["created_at"])
        return AuthContext(tenant=tenant, key=key)

    def revoke_key(self, key_id: str) -> bool:
        with self._tx() as cur:
            cur.execute("UPDATE api_keys SET status = 'revoked' WHERE id = ?;", (key_id,))
            return cur.rowcount > 0

    # --- usage / limits ---

    def usage_rpm_rpd(self, tenant_id: str) -> tuple[int, int]:
        now = time.time()
        cur = self._conn.cursor()
        try:
            cur.execute(
                "SELECT COUNT(*) FROM usage_events WHERE tenant_id = ? AND ts >= ?;",
                (tenant_id, now - 60.0),
            )
            rpm = int(cur.fetchone()[0])
            cur.execute(
                "SELECT COUNT(*) FROM usage_events WHERE tenant_id = ? AND date_str = ?;",
                (tenant_id, _utc_day(now)),
            )
            rpd = int(cur.fetchone()[0])
            return rpm, rpd
        finally:
            cur.close()

    def check_and_record(
        self,
        tenant: Tenant,
        key: ApiKey,
        *,
        model: str | None = None,
    ) -> tuple[bool, str]:
        """Atomic RPM/RPD check + insert. Returns (allowed, reason)."""
        now = time.time()
        today = _utc_day(now)
        try:
            with self._tx() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM usage_events WHERE tenant_id = ? AND ts >= ?;",
                    (tenant.id, now - 60.0),
                )
                rpm = int(cur.fetchone()[0])
                if rpm >= tenant.rpm_limit:
                    return False, f"tenant RPM limit ({tenant.rpm_limit})"
                cur.execute(
                    "SELECT COUNT(*) FROM usage_events WHERE tenant_id = ? AND date_str = ?;",
                    (tenant.id, today),
                )
                rpd = int(cur.fetchone()[0])
                if rpd >= tenant.rpd_limit:
                    return False, f"tenant RPD limit ({tenant.rpd_limit})"
                cur.execute(
                    "INSERT INTO usage_events (tenant_id, key_id, ts, date_str, model, status_code) "
                    "VALUES (?, ?, ?, ?, ?, ?);",
                    (tenant.id, key.id, now, today, model, 0),
                )
            return True, "ok"
        except sqlite3.Error as exc:
            return False, f"db error: {exc}"

    def update_event_status(
        self,
        tenant_id: str,
        *,
        status_code: int,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> None:
        """Best-effort update of the latest open event for tenant (simple MVP)."""
        try:
            self._conn.execute(
                "UPDATE usage_events SET status_code = ?, tokens_in = ?, tokens_out = ? "
                "WHERE id = (SELECT id FROM usage_events WHERE tenant_id = ? ORDER BY id DESC LIMIT 1);",
                (status_code, tokens_in, tokens_out, tenant_id),
            )
        except sqlite3.Error:
            pass

    def tenant_stats(self, tenant_id: str) -> dict[str, Any]:
        rpm, rpd = self.usage_rpm_rpd(tenant_id)
        t = self.get_tenant(tenant_id)
        return {
            "tenant_id": tenant_id,
            "name": t.name if t else None,
            "rpm": rpm,
            "rpd": rpd,
            "rpm_limit": t.rpm_limit if t else None,
            "rpd_limit": t.rpd_limit if t else None,
            "budget_usd": t.budget_usd if t else None,
        }


# © 2026 Mourad Soltani — Mourad Soltani Technologies™ @MST
