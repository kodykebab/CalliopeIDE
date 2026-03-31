import pytest
import json
from unittest.mock import patch, MagicMock

from flask import Flask
from server.routes.soroban_wallet import wallet_bp

@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(wallet_bp)
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_build_deploy_tx_missing_fields(client):
    res = client.post(
        "/api/soroban/build-deploy-tx",
        json={"session_id": 1},
        content_type="application/json",
    )
    assert res.status_code == 400
    data = json.loads(res.data)
    assert "Missing fields" in data["error"]


def test_build_deploy_tx_invalid_public_key(client):
    res = client.post(
        "/api/soroban/build-deploy-tx",
        json={
            "session_id": 1,
            "wasm_path": "/tmp/test.wasm",
            "deployer_public_key": "NOT_A_VALID_KEY",
        },
        content_type="application/json",
    )
    assert res.status_code == 400
    data = json.loads(res.data)
    assert "Invalid Stellar public key" in data["error"]


@patch("server.routes.soroban_wallet.StrKey.is_valid_ed25519_public_key", return_value=True)
def test_build_deploy_tx_unsupported_network(mock_valid, client):
    res = client.post(
        "/api/soroban/build-deploy-tx",
        json={
            "session_id": 1,
            "wasm_path": "/tmp/test.wasm",
            "deployer_public_key": "GAHJJJKMOKYE4RVPZEWZTKH5FVI4PA3VL7GK2LFNUBSGBV35JEJTMHZY",
            "network": "invalidnet",
        },
        content_type="application/json",
    )
    assert res.status_code == 400
    data = json.loads(res.data)
    assert "Unsupported network" in data["error"]


def test_submit_deploy_missing_fields(client):
    res = client.post(
        "/api/soroban/submit-deploy",
        json={"session_id": 1},
        content_type="application/json",
    )
    assert res.status_code == 400
    data = json.loads(res.data)
    assert "Missing fields" in data["error"]


def test_submit_deploy_invalid_xdr(client):
    res = client.post(
        "/api/soroban/submit-deploy",
        json={
            "session_id": 1,
            "signed_xdr": "THIS_IS_NOT_VALID_XDR",
            "network": "testnet",
        },
        content_type="application/json",
    )
    assert res.status_code == 400
    data = json.loads(res.data)
    assert "Invalid XDR" in data["error"]


def test_submit_deploy_unsupported_network(client):
    res = client.post(
        "/api/soroban/submit-deploy",
        json={
            "session_id": 1,
            "signed_xdr": "some_xdr",
            "network": "fakechain",
        },
        content_type="application/json",
    )
    assert res.status_code == 400
    data = json.loads(res.data)
    assert "Unsupported network" in data["error"]
