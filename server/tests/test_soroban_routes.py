"""Tests for server/routes/soroban_routes.py"""
import pytest, os, subprocess, sys
from unittest.mock import MagicMock

def _passthrough(f):
    import functools
    @functools.wraps(f)
    def inner(*args, **kwargs):
        u = MagicMock(); u.id = 1; u.username = "testuser"
        return f(u, *args, **kwargs)
    return inner

_auth_stub = MagicMock()
_auth_stub.token_required = _passthrough
sys.modules["server.utils.auth_utils"] = _auth_stub
sys.modules["server.models"] = MagicMock()
sys.modules["server.utils.monitoring"] = MagicMock()

import server.routes.soroban_routes as m

# Restore sys.modules immediately after import to avoid contaminating other test modules
for _mod in ["server.utils.auth_utils", "server.models", "server.utils.monitoring"]:
    sys.modules.pop(_mod, None)


soroban_bp = m.soroban_bp
from flask import Flask

def make_user():
    u = MagicMock(); u.id = 1; u.username = "testuser"; return u

def make_session(d):
    s = MagicMock(); s.id = 1; s.user_id = 1; s.is_active = True; s.instance_dir = d; return s

def no_sess():
    x = MagicMock(); x.query.filter_by.return_value.first.return_value = None; return x

def yes_sess(d):
    x = MagicMock(); x.query.filter_by.return_value.first.return_value = make_session(d); return x

@pytest.fixture
def app():
    a = Flask(__name__)
    a.config["TESTING"] = True
    a.config["SECRET_KEY"] = "test"
    a.register_blueprint(soroban_bp)
    return a

@pytest.fixture
def client(app):
    return app.test_client()

class TestCompile:
    def setup_method(self):
        import server.routes.soroban_routes as m
        m.Session = MagicMock()
        m._check_rust_toolchain = m._check_rust_toolchain.__wrapped__ if hasattr(m._check_rust_toolchain, '__wrapped__') else m._check_rust_toolchain

    def setup_method(self):
        import server.routes.soroban_routes as m
        m.Session = MagicMock()
        m._check_rust_toolchain = m._check_rust_toolchain.__wrapped__ if hasattr(m._check_rust_toolchain, '__wrapped__') else m._check_rust_toolchain

    def test_no_session_id(self, client):
        resp = client.post("/api/soroban/compile", json={"session_id": None})
        assert resp.status_code == 400
        assert b"session_id" in resp.data

    def test_session_not_found(self, client):
        m.Session = no_sess()
        resp = client.post("/api/soroban/compile", json={"session_id": 99})
        assert resp.status_code == 404

    def test_path_traversal(self, client, tmp_path):
        d = str(tmp_path / "instance1_user1"); os.makedirs(d)
        m.Session = yes_sess(d)
        resp = client.post("/api/soroban/compile", json={"session_id": 1, "project_path": "../../etc"})
        assert resp.status_code == 400

    def test_no_cargo_toml(self, client, tmp_path):
        d = str(tmp_path / "instance1_user1"); os.makedirs(d)
        m.Session = yes_sess(d)
        resp = client.post("/api/soroban/compile", json={"session_id": 1})
        assert resp.status_code == 400
        assert b"Cargo.toml" in resp.data

    def test_toolchain_missing(self, client, tmp_path):
        d = str(tmp_path / "instance1_user1"); os.makedirs(d)
        (tmp_path / "instance1_user1" / "Cargo.toml").write_text("[package]")
        m.Session = yes_sess(d)
        m._check_rust_toolchain = lambda: (False, "cargo not found")
        resp = client.post("/api/soroban/compile", json={"session_id": 1})
        assert resp.status_code == 500

    def test_success(self, client, tmp_path):
        d = str(tmp_path / "instance1_user1"); os.makedirs(d)
        (tmp_path / "instance1_user1" / "Cargo.toml").write_text("[package]")
        wd = tmp_path / "instance1_user1" / "target" / "wasm32-unknown-unknown" / "release"
        os.makedirs(wd); (wd / "c.wasm").write_bytes(b"\x00asm")
        m.Session = yes_sess(d)
        m._check_rust_toolchain = lambda: (True, "ok")
        r = MagicMock(); r.returncode = 0; r.stdout = "ok"; r.stderr = ""
        sp = MagicMock(); sp.run.return_value = r
        orig = m.subprocess; m.subprocess = sp
        resp = client.post("/api/soroban/compile", json={"session_id": 1})
        m.subprocess = orig
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
        assert len(resp.get_json()["wasm_artifacts"]) == 1

    def test_failure_422(self, client, tmp_path):
        d = str(tmp_path / "instance1_user1"); os.makedirs(d)
        (tmp_path / "instance1_user1" / "Cargo.toml").write_text("[package]")
        m.Session = yes_sess(d)
        m._check_rust_toolchain = lambda: (True, "ok")
        r = MagicMock(); r.returncode = 1; r.stdout = ""; r.stderr = "error"
        sp = MagicMock(); sp.run.return_value = r
        orig = m.subprocess; m.subprocess = sp
        resp = client.post("/api/soroban/compile", json={"session_id": 1})
        m.subprocess = orig
        assert resp.status_code == 422

    def test_timeout_408(self, client, tmp_path):
        d = str(tmp_path / "instance1_user1"); os.makedirs(d)
        (tmp_path / "instance1_user1" / "Cargo.toml").write_text("[package]")
        m.Session = yes_sess(d)
        m._check_rust_toolchain = lambda: (True, "ok")
        sp = MagicMock()
        sp.run.side_effect = subprocess.TimeoutExpired(cmd="cargo", timeout=120)
        sp.TimeoutExpired = subprocess.TimeoutExpired
        orig = m.subprocess; m.subprocess = sp
        resp = client.post("/api/soroban/compile", json={"session_id": 1})
        m.subprocess = orig
        assert resp.status_code == 408

class TestArtifacts:
    def setup_method(self):
        import server.routes.soroban_routes as m
        m.Session = MagicMock()

    def setup_method(self):
        import server.routes.soroban_routes as m
        m.Session = MagicMock()

    def test_not_found(self, client):
        m.Session = no_sess()
        resp = client.get("/api/soroban/artifacts/99")
        assert resp.status_code == 404

    def test_lists_wasm(self, client, tmp_path):
        d = str(tmp_path / "instance1_user1")
        wd = tmp_path / "instance1_user1" / "target" / "wasm32-unknown-unknown" / "release"
        os.makedirs(wd); (wd / "c.wasm").write_bytes(b"\x00asm")
        m.Session = yes_sess(d)
        resp = client.get("/api/soroban/artifacts/1")
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 1

    def test_empty(self, client, tmp_path):
        d = str(tmp_path / "instance1_user1"); os.makedirs(d)
        m.Session = yes_sess(d)
        resp = client.get("/api/soroban/artifacts/1")
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 0
