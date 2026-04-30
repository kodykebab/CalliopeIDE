from flask import Blueprint, request, jsonify, g
from stellar_sdk import (
    Keypair,
    Network,
    Server,
    TransactionBuilder,
    StrKey,
)
from stellar_sdk.xdr import TransactionEnvelope
import base64
import os
from server.middleware.rate_limiter import (
    rate_limit, validate_stellar_address, get_client_ip
)
from server.utils.auth_utils import token_required

wallet_bp = Blueprint("soroban_wallet", __name__)

HORIZON_URLS = {
    "testnet": "https://horizon-testnet.stellar.org",
    "mainnet": "https://horizon.stellar.org",
}

NETWORK_PASSPHRASES = {
    "testnet": Network.TESTNET_NETWORK_PASSPHRASE,
    "mainnet": Network.PUBLIC_NETWORK_PASSPHRASE,
}


def get_horizon_server(network: str) -> Server:
    url = HORIZON_URLS.get(network)
    if not url:
        raise ValueError(f"Unsupported network: {network}")
    return Server(url)


@wallet_bp.route("/api/soroban/build-deploy-tx", methods=["POST"])
@token_required
@rate_limit('soroban_deploy')
def build_deploy_tx(current_user):
    """
    Build an unsigned deployment transaction XDR.
    The frontend signs this with Freighter — no secret key
    ever touches the server.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    required = ["session_id", "wasm_path", "deployer_public_key"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    public_key = data["deployer_public_key"]
    network = data.get("network", "testnet")
    fund_account = data.get("fund_account", True)

    # Validate public key format using our validation
    is_valid, error = validate_stellar_address(public_key, 'public_key')
    if not is_valid:
        return jsonify({"error": error}), 400

    if network not in HORIZON_URLS:
        return jsonify({"error": f"Unsupported network: {network}"}), 400

    try:
        horizon = get_horizon_server(network)

        # Fund via Friendbot if testnet and requested
        if network == "testnet" and fund_account:
            import requests as req
            req.get(
                f"https://friendbot.stellar.org?addr={public_key}",
                timeout=10,
            )

        # Load account
        account = horizon.load_account(public_key)

        # Read wasm bytes
        wasm_path = data["wasm_path"]
        if not os.path.exists(wasm_path):
            return jsonify({"error": f"WASM file not found: {wasm_path}"}), 404

        with open(wasm_path, "rb") as f:
            wasm_bytes = f.read()

        # Build upload + instantiate transaction (unsigned)
        passphrase = NETWORK_PASSPHRASES[network]
        tx = (
            TransactionBuilder(
                source_account=account,
                network_passphrase=passphrase,
                base_fee=100,
            )
            .append_upload_contract_wasm_op(wasm_bytes)
            .set_timeout(30)
            .build()
        )

        unsigned_xdr = tx.to_xdr()
        return jsonify({"unsigned_xdr": unsigned_xdr}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@wallet_bp.route("/api/soroban/submit-deploy", methods=["POST"])
@token_required
@rate_limit('soroban_deploy')
def submit_deploy(current_user):
    """
    Accept a Freighter-signed XDR and submit it to the network.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    required = ["session_id", "signed_xdr"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    network = data.get("network", "testnet")
    if network not in HORIZON_URLS:
        return jsonify({"error": f"Unsupported network: {network}"}), 400

    try:
        horizon = get_horizon_server(network)
        signed_xdr = data["signed_xdr"]

        # Validate XDR format before submitting
        try:
            TransactionEnvelope.from_xdr(signed_xdr)
        except Exception:
            return jsonify({"error": "Invalid XDR format"}), 400

        # Submit to network
        response = horizon.submit_transaction(
            TransactionEnvelope.from_xdr(signed_xdr)
        )

        contract_id = response.get("id") or response.get("hash", "")
        return jsonify({
            "contract_id": contract_id,
            "hash": response.get("hash", ""),
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
