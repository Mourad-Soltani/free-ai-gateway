"""
tracker.py — SQLite (WAL) quota tracking for the Free AI Gateway.

Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Iterator, Optional, Tuple

SCHEMA_VERSION = 1

log = logging.getLogger("free_ai_gateway.tracker")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS api_usage (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    provider  TEXT    NOT NULL,
    timestamp REAL    NOT NULL,
    date_str  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_provider_ts   ON api_usage(provider, timestamp);
CREATE INDEX IF NOT EXISTS idx_provider_date ON api_usage(provider, date_str);
"""

_INSERT    = "INSERT INTO api_usage (provider, timestamp, date_str) VALUES (?, ?, ?);"
_COUNT_RPM = "SELECT COUNT(*) FROM api_usage WHERE provider = ? AND timestamp >= ?;"
_COUNT_RPD = "SELECT COUNT(*) FROM api_usage WHERE provider = ? AND date_str = ?;"
_STATS_RPM = ("SELECT provider, COUNT(*) FROM api_usage "
              "WHERE timestamp >= ? GROUP BY provider;")
_STATS_RPD = ("SELECT provider, COUNT(*) FROM api_usage "
              "WHERE date_str = ? GROUP BY provider;")


def _utc_day(ts: Optional[float] = None) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%d")


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


@dataclass(frozen=True)
class QuotaSnapshot:
    provider: str
    rpm: int
    rpd: int
    max_rpm: int = 0
    max_rpd: int = 0

    @property
    def rpm_util(self) -> float:
        return (self.rpm / self.max_rpm) if self.max_rpm else 0.0

    @property
    def rpd_util(self) -> float:
        return (self.rpd / self.max_rpd) if self.max_rpd else 0.0


class APIRateTracker:
    """Tracks per-provider request counts against RPM and RPD ceilings."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        *,
        fail_open: Optional[bool] = None,
        retention_days: Optional[int] = None,
        busy_timeout_ms: Optional[int] = None,
    ) -> None:
        self.db_path = db_path or os.getenv("FREE_AI_DB_PATH", "api_limits.db")
        self.retention_days = retention_days if retention_days is not None \
            else int(os.getenv("FREE_AI_RETENTION_DAYS", "7"))
        self.busy_timeout_ms = busy_timeout_ms if busy_timeout_ms is not None \
            else int(os.getenv("FREE_AI_BUSY_TIMEOUT_MS", "5000"))
        self.fail_open = fail_open if fail_open is not None \
            else _bool_env("FREE_AI_FAIL_OPEN", True)
        self._local = threading.local()
        self._init_db()

    def _new_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.busy_timeout_ms / 1000.0,
            isolation_level=None,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms};")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    @property
    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._new_connection()
            self._local.conn = conn
        return conn

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Cursor]:
        conn = self._conn
        cur = conn.cursor()
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

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    def _init_db(self) -> None:
        conn = self._new_connection()
        try:
            conn.executescript(_SCHEMA)
            self._prune(conn)
        finally:
            conn.close()

    def _prune(self, conn: sqlite3.Connection) -> None:
        cutoff = (datetime.now(timezone.utc)
                  - timedelta(days=self.retention_days)).strftime("%Y-%m-%d")
        try:
            conn.execute("DELETE FROM api_usage WHERE date_str < ?;", (cutoff,))
        except sqlite3.Error as exc:
            log.warning("prune failed: %s", exc)

    def record_request(self, provider: str, *, count: int = 1) -> None:
        if count <= 0:
            return
        now = time.time()
        today = _utc_day(now)
        try:
            with self._tx() as cur:
                cur.executemany(_INSERT, [(provider, now, today)] * count)
        except sqlite3.Error as exc:
            log.error("failed to record usage for %s: %s", provider, exc)

    def usage(self, provider: str) -> Tuple[int, int]:
        now = time.time()
        try:
            cur = self._conn.cursor()
            try:
                cur.execute(_COUNT_RPM, (provider, now - 60.0))
                rpm = cur.fetchone()[0]
                cur.execute(_COUNT_RPD, (provider, _utc_day(now)))
                rpd = cur.fetchone()[0]
            finally:
                cur.close()
            return rpm, rpd
        except sqlite3.Error as exc:
            log.error("usage query failed for %s: %s", provider, exc)
            return (0, 0)

    def is_allowed(self, provider: str, max_rpm: int, max_rpd: int) -> bool:
        rpm, rpd = self.usage(provider)
        if rpm >= max_rpm:
            log.warning("%s at RPM ceiling (%d/%d)", provider, rpm, max_rpm)
            return False
        if rpd >= max_rpd:
            log.warning("%s at RPD ceiling (%d/%d)", provider, rpd, max_rpd)
            return False
        return True

    def check_and_record(self, provider: str, max_rpm: int, max_rpd: int) -> bool:
        now = time.time()
        today = _utc_day(now)
        try:
            with self._tx() as cur:
                cur.execute(_COUNT_RPM, (provider, now - 60.0))
                if cur.fetchone()[0] >= max_rpm:
                    log.warning("%s at RPM ceiling (%d)", provider, max_rpm)
                    return False
                cur.execute(_COUNT_RPD, (provider, today))
                if cur.fetchone()[0] >= max_rpd:
                    log.warning("%s at RPD ceiling (%d)", provider, max_rpd)
                    return False
                cur.execute(_INSERT, (provider, now, today))
            return True
        except sqlite3.Error as exc:
            log.error("atomic rate check failed for %s: %s", provider, exc)
            return self.fail_open

    def snapshot(self, providers: Iterable) -> dict:
        out: dict = {}
        for p in providers:
            name = p if isinstance(p, str) else getattr(p, "name", p["name"])
            rpm, rpd = self.usage(name)
            out[name] = {"rpm": rpm, "rpd": rpd}
        return out

    def stats(self) -> dict:
        now = time.time()
        try:
            cur = self._conn.cursor()
            try:
                cur.execute(_STATS_RPM, (now - 60.0,))
                rpm_map = {row[0]: row[1] for row in cur.fetchall()}
                cur.execute(_STATS_RPD, (_utc_day(now),))
                rpd_map = {row[0]: row[1] for row in cur.fetchall()}
            finally:
                cur.close()
            providers = sorted(set(rpm_map) | set(rpd_map))
            return {
                "schema_version": SCHEMA_VERSION,
                "gateway_version": "1.2.0",
                "window_60s": rpm_map,
                "day_utc": rpd_map,
                "providers": providers,
                "generated_at": now,
            }
        except sqlite3.Error as exc:
            log.error("stats query failed: %s", exc)
            return {
                "schema_version": SCHEMA_VERSION,
                "gateway_version": "1.2.0",
                "window_60s": {}, "day_utc": {}, "providers": [],
                "generated_at": now, "error": str(exc),
            }


# © 2026 Mourad Soltani — Mourad Soltani Technologies™ @MST
