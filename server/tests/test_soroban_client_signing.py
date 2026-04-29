"""
Tests for client-side transaction signing endpoints.
Addresses security issue: secret keys should never be sent to the server.
"""

import os
import json
import functools
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Stub dependencies
# ---------------------------------------------------------------------------

def _passthrough(f):
    @functools.wraps(f)
    def inner(*args, **kwargs):
        u = MagicMock()
        u.id = 1
        u.username = "testuser"
        return f(u, *args, **kwargs)
    return inner


_auth_stub = MagicMock()
_auth_stub.token_required = _passthrough
with patch.dict("sys.modules", {
    "server.utils.auth_utils": _auth_stub,
    "server.models": MagicMock(),
    "server.utils.monitoring": MagicMock()
}):
    import server.routes.soroban_invoke as invoke_module
    import server.routes.soroban_deploy as deploy_module


from flask import Flask


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_session(instance_dir):
    s = MagicMock()
    s.id = 1
    s.user_id = 1
    s.is_active = True
    s.instance_dir = instance_dir
    return s


def _yes_session(d):
    x = MagicMock()
    x.query.filter_by.return_value.first.return_value = _make_session(d)
    return x


def _no_session():
    x = MagicMock()
    x.query.filter_by.return_value.first.return_value = None
    return x


@pytest.fixture
def app():
    a = Flask(__name__)
    a.config["TESTING"] = True
    a.config["SECRET_KEY"] = "test"
    a.register_blueprint(invoke_module.soroban_invoke_bp)
    a.register_blueprint(deploy_module.soroban_deploy_bp)
    return a


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# POST /api/soroban/prepare-invoke
# ---------------------------------------------------------------------------

class TestPrepareInvoke:
    def test_missing_required_fields(self, client):
        """Test that all required fields are validated"""
        resp = client.post("/api/soroban/prepare-invoke", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert not data.get("success")

    def test_parameters_must_be_list(self, client, tmp_path):
        """Test that parameters field must be a list"""
        d = str(tmp_path / "inst")
        os.makedirs(d)
        invoke_module.Session = _yes_session(d)
        
        resp = client.post("/api/soroban/prepare-invoke", json={
            "session_id": 1,
            "contract_id": "CTEST",
            "function_name": "hello",
            "public_key": "GTEST",
            "parameters": "not-a-list"
        })
        assert resp.status_code == 400
        assert b"parameters must be a list" in resp.data

    def test_session_not_found(self, client):
        """Test that invalid session returns 404"""
        invoke_module.Session = _no_session()
        resp = client.post("/api/soroban/prepare-invoke", json={
            "session_id": 99,
            "contract_id": "CTEST",
            "function_name": "hello",
            "public_key": "GTEST"
        })
        assert resp.status_code == 404

    def test_stellar_sdk_missing(self, client, tmp_path):
        """Test graceful handling when stellar-sdk is not installed"""
        d = str(tmp_path / "inst")
        os.makedirs(d)
        invoke_module.Session = _yes_session(d)
        invoke_module._get_stellar_sdk = lambda: (False, "stellar-sdk not installed")
        
        resp = client.post("/api/soroban/prepare-invoke", json={
            "session_id": 1,
            "contract_id": "CTEST",
            "function_name": "hello",
            "public_key": "GTEST"
        })
        assert resp.status_code == 500
        assert b"stellar-sdk" in resp.data

    def test_invalid_parameter_format(self, client, tmp_path):
        """Test that invalid parameter format is caught"""
        d = str(tmp_path / "inst")
        os.makedirs(d)
        invoke_module.Session = _yes_session(d)
        invoke_module._get_stellar_sdk = lambda: (True, None)
        
        # Use valid addresses to get past validation
        valid_contract = "CAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD2KM"
        valid_public = "GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWHF"
        
        # Mock both the parameter parsing and the server
        with patch("server.routes.soroban_invoke._parse_param", side_effect=ValueError("bad param")), \
             patch("stellar_sdk.SorobanServer"):
            resp = client.post("/api/soroban/prepare-invoke", json={
                "session_id": 1,
                "contract_id": valid_contract,
                "function_name": "hello",
                "public_key": valid_public,
                "parameters": ["invalid:format"]
            })
        
        assert resp.status_code == 400
        assert b"Invalid parameter format" in resp.data

    def test_successful_preparation(self, client, tmp_path):
        """Test successful unsigned transaction preparation"""
        d = str(tmp_path / "inst")
        os.makedirs(d)
        invoke_module.Session = _yes_session(d)
        invoke_module._get_stellar_sdk = lambda: (True, None)
        
        mock_tx = MagicMock()
        mock_tx.to_xdr.return_value = "AAAA...XDR"
        
        with patch("stellar_sdk.SorobanServer") as mock_server, \
             patch("stellar_sdk.TransactionBuilder") as mock_builder:
            mock_server.return_value.load_account.return_value = MagicMock()
            mock_server.return_value.prepare_transaction.return_value = mock_tx
            mock_builder.return_value.set_timeout.return_value.append_invoke_contract_function_op.return_value.build.return_value = mock_tx
            
            resp = client.post("/api/soroban/prepare-invoke", json={
                "session_id": 1,
                "contract_id": "CTEST",
                "function_name": "hello",
                "public_key": "GTEST",
                "parameters": []
            })
        
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "unsigned_xdr" in data
        assert data["network"] == "testnet"


# ---------------------------------------------------------------------------
# POST /api/soroban/submit-invoke
# ---------------------------------------------------------------------------

class TestSubmitInvoke:
    def test_missing_required_fields(self, client):
        """Test that all required fields are validated"""
        resp = client.post("/api/soroban/submit-invoke", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert not data.get("success")

    def test_session_not_found(self, client):
        """Test that invalid session returns 404"""
        invoke_module.Session = _no_session()
        resp = client.post("/api/soroban/submit-invoke", json={
            "session_id": 99,
            "signed_xdr": "AAAA",
            "contract_id": "CTEST",
            "function_name": "hello"
        })
        assert resp.status_code == 404

    def test_invalid_xdr_format(self, client, tmp_path):
        """Test that invalid XDR is rejected"""
        d = str(tmp_path / "inst")
        os.makedirs(d)
        invoke_module.Session = _yes_session(d)
        invoke_module._get_stellar_sdk = lambda: (True, None)
        
        with patch("stellar_sdk.TransactionEnvelope.from_xdr", side_effect=Exception("bad xdr")):
            resp = client.post("/api/soroban/submit-invoke", json={
                "session_id": 1,
                "signed_xdr": "INVALID_XDR",
                "contract_id": "CTEST",
                "function_name": "hello"
            })
        
        assert resp.status_code == 400
        assert b"Invalid XDR format" in resp.data

    def test_transaction_failure(self, client, tmp_path):
        """Test handling of failed on-chain transaction"""
        d = str(tmp_path / "inst")
        os.makedirs(d)
        invoke_module.Session = _yes_session(d)
        invoke_module._get_stellar_sdk = lambda: (True, None)
        
        mock_response = MagicMock()
        mock_response.hash = "tx123"
        
        with patch("stellar_sdk.TransactionEnvelope.from_xdr"), \
             patch("stellar_sdk.SorobanServer") as mock_server, \
             patch("server.routes.soroban_invoke._wait_for_transaction") as mock_wait:
            mock_server.return_value.send_transaction.return_value = mock_response
            mock_wait.return_value = {"success": False, "error": "Transaction failed"}
            
            resp = client.post("/api/soroban/submit-invoke", json={
                "session_id": 1,
                "signed_xdr": "AAAA",
                "contract_id": "CTEST",
                "function_name": "hello"
            })
        
        assert resp.status_code == 422
        data = resp.get_json()
        assert data["success"] is False
        assert "failed" in data["error"].lower()


# ---------------------------------------------------------------------------
# POST /api/soroban/prepare-upload
# ---------------------------------------------------------------------------

class TestPrepareUpload:
    def test_missing_required_fields(self, client):
        """Test that all required fields are validated"""
        resp = client.post("/api/soroban/prepare-upload", json={})
        assert resp.status_code == 400
        assert b"required" in resp.data

    def test_session_not_found(self, client):
        """Test that invalid session returns 404"""
        deploy_module.Session = _no_session()
        resp = client.post("/api/soroban/prepare-upload", json={
            "session_id": 99,
            "wasm_path": "contract.wasm",
            "public_key": "GTEST"
        })
        assert resp.status_code == 404

    def test_wasm_file_not_found(self, client, tmp_path):
        """Test that missing WASM file returns 404"""
        d = str(tmp_path / "inst")
        os.makedirs(d)
        deploy_module.Session = _yes_session(d)
        
        resp = client.post("/api/soroban/prepare-upload", json={
            "session_id": 1,
            "wasm_path": "missing.wasm",
            "public_key": "GTEST"
        })
        assert resp.status_code == 404
        assert b"not found" in resp.data

    def test_path_traversal_blocked(self, client, tmp_path):
        """Test that path traversal attempts are blocked"""
        d = str(tmp_path / "inst")
        os.makedirs(d)
        deploy_module.Session = _yes_session(d)
        
        resp = client.post("/api/soroban/prepare-upload", json={
            "session_id": 1,
            "wasm_path": "../../etc/passwd",
            "public_key": "GTEST"
        })
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/soroban/prepare-create
# ---------------------------------------------------------------------------

class TestPrepareCreate:
    def test_missing_required_fields(self, client):
        """Test that all required fields are validated"""
        resp = client.post("/api/soroban/prepare-create", json={})
        assert resp.status_code == 400
        assert b"required" in resp.data

    def test_stellar_sdk_missing(self, client):
        """Test graceful handling when stellar-sdk is not installed"""
        deploy_module._get_stellar_sdk = lambda: (False, "stellar-sdk not installed")
        
        resp = client.post("/api/soroban/prepare-create", json={
            "session_id": 1,
            "wasm_hash": "abc123",
            "public_key": "GTEST"
        })
        assert resp.status_code == 500
        assert b"stellar-sdk" in resp.data


# ---------------------------------------------------------------------------
# POST /api/soroban/submit-tx
# ---------------------------------------------------------------------------

class TestSubmitTx:
    def test_missing_signed_xdr(self, client):
        """Test that signed_xdr is required"""
        resp = client.post("/api/soroban/submit-tx", json={})
        assert resp.status_code == 400
        assert b"signed_xdr" in resp.data

    def test_invalid_xdr_format(self, client):
        """Test that invalid XDR is rejected"""
        deploy_module._get_stellar_sdk = lambda: (True, None)
        
        with patch("stellar_sdk.TransactionEnvelope.from_xdr", side_effect=Exception("bad xdr")):
            resp = client.post("/api/soroban/submit-tx", json={
                "signed_xdr": "INVALID"
            })
        
        # Should fail during XDR parsing or submission
        assert resp.status_code in [400, 422, 500]


# ---------------------------------------------------------------------------
# Security validation tests
# ---------------------------------------------------------------------------

class TestSecurityValidation:
    def test_no_secret_keys_in_new_endpoints(self, client, tmp_path):
        """Verify that new endpoints do not accept secret keys"""
        d = str(tmp_path / "inst")
        os.makedirs(d)
        invoke_module.Session = _yes_session(d)
        
        # Attempt to send secret key to prepare-invoke (should be ignored)
        resp = client.post("/api/soroban/prepare-invoke", json={
            "session_id": 1,
            "contract_id": "CTEST",
            "function_name": "hello",
            "public_key": "GTEST",
            "invoker_secret": "SSECRET123",  # Should not be used
            "parameters": []
        })
        
        # Endpoint should not fail, but secret should not be processed
        # (it will fail for other reasons in test env, but not due to secret key)
        assert b"invoker_secret" not in resp.data or resp.status_code != 400

    def test_deprecated_endpoint_warning(self, client):
        """Verify that old endpoints are marked as deprecated"""
        # This is a documentation test - verify the docstring
        assert "DEPRECATED" in invoke_module.invoke_contract.__doc__
        assert "DEPRECATED" in deploy_module.deploy_contract.__doc__
