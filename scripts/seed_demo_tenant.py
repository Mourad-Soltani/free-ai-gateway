#!/usr/bin/env python3
"""Seed a public demo tenant + print virtual key once."""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from control_plane.db import ControlPlaneDB

def main() -> int:
    db = ControlPlaneDB(os.getenv("CONTROL_PLANE_DB", "control_plane.db"))
    existing = [t for t in db.list_tenants() if t.name == "PublicDemo"]
    if existing:
        t = existing[0]
        print(json.dumps({"tenant_id": t.id, "name": t.name, "note": "exists — create a new key with cli"}))
    else:
        t = db.create_tenant("PublicDemo", rpm_limit=8, rpd_limit=50)
        meta, raw = db.create_key(t.id, name="public-demo")
        print(json.dumps({
            "tenant_id": t.id,
            "key_id": meta.id,
            "api_key": raw,
            "rpm_limit": t.rpm_limit,
            "rpd_limit": t.rpd_limit,
            "warning": "Save api_key now; shown once.",
        }, indent=2))
    db.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
