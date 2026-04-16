"""Tests for server/routes/soroban_deploy.py"""

import pytest
import os
import json
import sys
import functools
from unittest.mock import MagicMock, patch

# Force fresh stubs — override anything set by previously collected test files
def _passthrough(f):
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

import server.routes.soroban_deploy as m
deploy_bp = m.soroban_deploy_bp

# Clean up stubs immediately
for _mod in ["server.utils.auth_utils", "server.models", "server.utils.monitoring"]:
    sys.modules.pop(_mod, None)

from flask import Flask


def make_session(instance_dir):
    s = MagicMock(); s.id = 1; s.user_id = 1; s.is_active = True
    s.instance_dir = instance_dir; return s

def no_session():
    x = MagicMock(); x.query.filter_by.return_value.first.return_value = None; return x

def yes_session(d):
    x = MagicMock(); x.query.filter_by.return_value.first.return_value = make_session(d); return x


@pytest.fixture
def app():
    a = Flask(__name__)
    a.config["TESTING"] = True
    a.config["SECRET_KEY"] = "test"
    a.register_blueprint(deploy_bp)
    return a

@pytest.fixture
def client(app):
    return app.test_client()


class TestDeployEndpoint:
    def test_missing_session_id(self, client):
        resp = client.post("/api/soroban/deploy", json={"wasm_path": "c.wasm", "deployer_secret": "S"})
        assert resp.status_code == 400
        assert b"session_id" in resp.data

    def test_missing_wasm_path(self, client):
        resp = client.post("/api/soroban/deploy", json={"session_id": 1})
        assert resp.status_code == 400
        assert b"wasm_path" in resp.data

    def test_missing_deployer_secret(self, client):
        resp = client.post("/api/soroban/deploy", json={
            "session_id": 1, "wasm_path": "contract.wasm"
        })
        assert resp.status_code == 400
        assert b"deployer_secret" in resp.data

    def test_session_not_found(self, client):
        m.Session = no_session()
        resp = client.post("/api/soroban/deploy", json={
            "session_id": 99, "wasm_path": "c.wasm", "deployer_secret": "S123"
        })
        assert resp.status_code == 404

    def test_path_traversal_blocked(self, client, tmp_path):
        d = str(tmp_path / "instance1_user1"); os.makedirs(d)
        m.Session = yes_session(d)
        resp = client.post("/api/soroban/deploy", json={
            "session_id": 1,
            "wasm_path": "../../etc/passwd",
            "deployer_secret": "STEST"
        })
        assert resp.status_code == 400
        assert b"Invalid wasm_path" in resp.data

    def test_non_wasm_file_blocked(self, client, tmp_path):
        d = str(tmp_path / "instance1_user1"); os.makedirs(d)
        m.Session = yes_session(d)
        resp = client.post("/api/soroban/deploy", json={
            "session_id": 1,
            "wasm_path": "Cargo.toml",
            "deployer_secret": "STEST"
        })
        assert resp.status_code == 400
        assert b"Invalid wasm_path" in resp.data

    def test_wasm_file_not_found(self, client, tmp_path):
        d = str(tmp_path / "instance1_user1"); os.makedirs(d)
        m.Session = yes_session(d)
        resp = client.post("/api/soroban/deploy", json={
            "session_id": 1,
            "wasm_path": "missing.wasm",
            "deployer_secret": "STEST"
        })
        assert resp.status_code == 404
        assert b"not found" in resp.data

    def test_stellar_sdk_missing(self, client, tmp_path):
        d = str(tmp_path / "instance1_user1"); os.makedirs(d)
        (tmp_path / "instance1_user1" / "c.wasm").write_bytes(b"\x00asm")
        m.Session = yes_session(d)
        m._get_stellar_sdk = lambda: (False, "stellar-sdk is not installed")
        resp = client.post("/api/soroban/deploy", json={
            "session_id": 1,
            "wasm_path": "c.wasm",
            "deployer_secret": "STEST"
        })
        assert resp.status_code == 500
        assert b"stellar-sdk" in resp.data

    def test_invalid_secret_key(self, client, tmp_path):
        d = str(tmp_path / "instance1_user1"); os.makedirs(d)
        (tmp_path / "instance1_user1" / "c.wasm").write_bytes(b"\x00asm")
        m.Session = yes_session(d)
        m._get_stellar_sdk = lambda: (True, None)

        # Patch Keypair directly in the module after stellar_sdk is imported
        mock_keypair_cls = MagicMock()
        mock_keypair_cls.from_secret.side_effect = Exception("Invalid key")

        import stellar_sdk as _sdk
        orig_kp = _sdk.Keypair
        _sdk.Keypair = mock_keypair_cls
        try:
            resp = client.post("/api/soroban/deploy", json={
                "session_id": 1,
                "wasm_path": "c.wasm",
                "deployer_secret": "INVALIDKEY"
            })
        finally:
            _sdk.Keypair = orig_kp

        assert resp.status_code == 400
        assert b"Invalid deployer_secret" in resp.data


class TestListDeployments:
    def test_session_not_found(self, client):
        m.Session = no_session()
        resp = client.get("/api/soroban/deployments/99")
        assert resp.status_code == 404

    def test_empty_deployments(self, client, tmp_path):
        d = str(tmp_path / "instance1_user1"); os.makedirs(d)
        m.Session = yes_session(d)
        resp = client.get("/api/soroban/deployments/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 0
        assert data["deployments"] == []

    def test_returns_deployment_records(self, client, tmp_path):
        d = str(tmp_path / "instance1_user1"); os.makedirs(d)
        deploy_dir = tmp_path / "instance1_user1" / ".deployments"
        os.makedirs(deploy_dir)
        record = {
            "contract_id": "CTEST123",
            "transaction_hash": "abc123",
            "network": "testnet"
        }
        (deploy_dir / "deploy_1.json").write_text(json.dumps(record))
        m.Session = yes_session(d)
        resp = client.get("/api/soroban/deployments/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        assert data["deployments"][0]["contract_id"] == "CTEST123"

    def test_resolve_wasm_path_traversal(self):
        result = m._resolve_wasm_path("../../etc/passwd", "/tmp/instance1_user1")
        assert result is None

    def test_resolve_wasm_path_non_wasm(self):
        result = m._resolve_wasm_path("Cargo.toml", "/tmp/instance1_user1")
        assert result is None

    def test_resolve_wasm_path_valid(self):
        import os
        base_dir = "/tmp/instance1_user1"
        result = m._resolve_wasm_path("target/release/c.wasm", base_dir)
        expected = os.path.abspath(os.path.join(base_dir, "target/release/c.wasm"))
        assert result == expected
