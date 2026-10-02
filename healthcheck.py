"""
healthcheck.py — production probe for Docker / Kubernetes / systemd.

Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST

Exit codes:
  0 healthy / 1 unreachable / 2 degraded / 3 DB error / 4 upstream error
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:4000")


def _check_liveness(c: httpx.Client, url: str) -> int:
    r = c.get(f"{url}/health/liveliness")
    return 0 if r.status_code == 200 else 1


def _check_readiness(c: httpx.Client, url: str) -> int:
    try:
        r = c.get(f"{url}/health/readiness")
    except httpx.HTTPError:
        return 0
    return 0 if r.status_code == 200 else 2


def _check_startup(c: httpx.Client, url: str) -> int:
    try:
        r = c.get(f"{url}/health/startup")
    except httpx.HTTPError:
        return 0
    return 0 if r.status_code == 200 else 2


def _check_quota_db() -> int:
    try:
        from tracker import APIRateTracker
        t = APIRateTracker()
        try:
            _ = t.stats()
        finally:
            t.close()
        return 0
    except Exception as exc:
        print(f"quota-db-error: {exc}", file=sys.stderr)
        return 3


def _check_upstream(c: httpx.Client, url: str, key: str) -> int:
    try:
        r = c.post(
            f"{url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            json={"model": "free-llm-router",
                  "messages": [{"role": "user", "content": "ping"}],
                  "max_tokens": 4},
        )
        return 0 if r.status_code == 200 else 4
    except httpx.HTTPError as exc:
        print(f"upstream-error: {exc}", file=sys.stderr)
        return 4


def main() -> int:
    parser = argparse.ArgumentParser(description="Free AI Gateway healthcheck.")
    parser.add_argument("--url", default=GATEWAY_URL)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--level",
                        choices=["live", "ready", "startup", "full"],
                        default="ready")
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--upstream", action="store_true")
    args = parser.parse_args()

    if args.deep:
        args.level = "full"

    try:
        with httpx.Client(timeout=args.timeout) as c:
            if _check_liveness(c, args.url) != 0:
                print("unhealthy: liveliness failed", file=sys.stderr)
                return 1
            if args.level in ("ready", "full", "startup"):
                rc = _check_readiness(c, args.url) if args.level != "startup" \
                    else _check_startup(c, args.url)
                if rc != 0:
                    print(f"degraded: {args.level} check failed", file=sys.stderr)
                    return rc
            if args.level == "full":
                rc = _check_quota_db()
                if rc != 0:
                    return rc
    except httpx.HTTPError as exc:
        print(f"unreachable: {exc}", file=sys.stderr)
        return 1

    if args.upstream:
        key = os.getenv("LITELLM_MASTER_KEY", "")
        if not key:
            print("upstream-check skipped: LITELLM_MASTER_KEY not set",
                  file=sys.stderr)
        else:
            with httpx.Client(timeout=args.timeout * 4) as c:
                rc = _check_upstream(c, args.url, key)
                if rc != 0:
                    return rc

    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# © 2026 Mourad Soltani — Mourad Soltani Technologies™ @MST
