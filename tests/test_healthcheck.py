"""Healthcheck probe tests.

Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "healthcheck.py"


def _run(*args, env=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, env=env, timeout=15,
    )


def test_unreachable_returns_1():
    proc = _run("--url", "http://127.0.0.1:1", "--timeout", "0.5")
    assert proc.returncode == 1, proc.stderr


def test_deep_mode_with_bad_url_still_returns_1():
    proc = _run("--url", "http://127.0.0.1:1", "--deep")
    assert proc.returncode == 1


def test_quota_db_check_succeeds_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("FREE_AI_DB_PATH", str(tmp_path / "h.db"))
    proc = _run("--url", "http://127.0.0.1:1", "--deep")
    assert proc.returncode == 1
