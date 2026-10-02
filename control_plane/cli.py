#!/usr/bin/env python3
"""
control_plane/cli.py — admin CLI for tenants and virtual keys.

Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST

Usage:
  python -m control_plane.cli tenant create "Acme"
  python -m control_plane.cli key create ten_abc123
  python -m control_plane.cli tenant list
  python -m control_plane.cli stats ten_abc123
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# repo root on path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

from control_plane.db import ControlPlaneDB  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Free AI Gateway control-plane admin")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ten = sub.add_parser("tenant", help="Tenant operations")
    ten_sub = p_ten.add_subparsers(dest="action", required=True)
    c = ten_sub.add_parser("create")
    c.add_argument("name")
    c.add_argument("--rpm", type=int, default=30)
    c.add_argument("--rpd", type=int, default=1000)
    ten_sub.add_parser("list")

    p_key = sub.add_parser("key", help="Virtual key operations")
    key_sub = p_key.add_subparsers(dest="action", required=True)
    kc = key_sub.add_parser("create")
    kc.add_argument("tenant_id")
    kc.add_argument("--name", default="default")
    kr = key_sub.add_parser("revoke")
    kr.add_argument("key_id")

    p_stats = sub.add_parser("stats")
    p_stats.add_argument("tenant_id")

    args = parser.parse_args(argv)
    db = ControlPlaneDB()
    try:
        if args.cmd == "tenant" and args.action == "create":
            t = db.create_tenant(args.name, rpm_limit=args.rpm, rpd_limit=args.rpd)
            print(json.dumps({"id": t.id, "name": t.name, "rpm": t.rpm_limit, "rpd": t.rpd_limit}, indent=2))
        elif args.cmd == "tenant" and args.action == "list":
            rows = [
                {"id": t.id, "name": t.name, "status": t.status, "rpm": t.rpm_limit, "rpd": t.rpd_limit}
                for t in db.list_tenants()
            ]
            print(json.dumps(rows, indent=2))
        elif args.cmd == "key" and args.action == "create":
            meta, raw = db.create_key(args.tenant_id, name=args.name)
            print(json.dumps({
                "id": meta.id,
                "tenant_id": meta.tenant_id,
                "prefix": meta.key_prefix,
                "api_key": raw,
                "warning": "Save this key; it will not be shown again.",
            }, indent=2))
        elif args.cmd == "key" and args.action == "revoke":
            ok = db.revoke_key(args.key_id)
            print(json.dumps({"revoked": ok, "key_id": args.key_id}))
        elif args.cmd == "stats":
            print(json.dumps(db.tenant_stats(args.tenant_id), indent=2))
        else:
            parser.print_help()
            return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
