"""Control plane tenancy tests.

Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST
"""
from control_plane.db import ControlPlaneDB


def test_create_tenant_and_key(tmp_path):
    db = ControlPlaneDB(str(tmp_path / "cp.db"))
    t = db.create_tenant("Acme", rpm_limit=5, rpd_limit=10)
    assert t.id.startswith("ten_")
    meta, raw = db.create_key(t.id, name="ci")
    assert raw.startswith("sk-fag-")
    ctx = db.resolve_key(raw)
    assert ctx is not None
    assert ctx.tenant.id == t.id
    assert ctx.key.id == meta.id
    db.close()


def test_invalid_key(tmp_path):
    db = ControlPlaneDB(str(tmp_path / "cp.db"))
    assert db.resolve_key("sk-fag-nope") is None
    db.close()


def test_rpm_limit(tmp_path):
    db = ControlPlaneDB(str(tmp_path / "cp.db"))
    t = db.create_tenant("Limited", rpm_limit=2, rpd_limit=100)
    _, raw = db.create_key(t.id)
    ctx = db.resolve_key(raw)
    assert ctx
    ok1, _ = db.check_and_record(ctx.tenant, ctx.key, model="free-llm-router")
    ok2, _ = db.check_and_record(ctx.tenant, ctx.key, model="free-llm-router")
    ok3, reason = db.check_and_record(ctx.tenant, ctx.key, model="free-llm-router")
    assert ok1 and ok2
    assert ok3 is False
    assert "RPM" in reason
    db.close()


def test_revoke(tmp_path):
    db = ControlPlaneDB(str(tmp_path / "cp.db"))
    t = db.create_tenant("X")
    meta, raw = db.create_key(t.id)
    assert db.resolve_key(raw) is not None
    db.revoke_key(meta.id)
    assert db.resolve_key(raw) is None
    db.close()
