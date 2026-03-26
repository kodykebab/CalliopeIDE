"""
Soroban testnet deployment routes — deploy compiled WASM contracts to Stellar testnet.
Addresses issue #50.

Endpoints:
  POST /api/soroban/deploy   — deploy a WASM contract to Stellar testnet
  GET  /api/soroban/deployments/<session_id>  — list deployments for a session
"""

import os
import glob
import logging
from pathlib import Path
from flask import Blueprint, request, jsonify
from server.utils.auth_utils import token_required
from server.utils.monitoring import capture_exception

try:
    from server.models import Session
except Exception:
    Session = None  # type: ignore

soroban_deploy_bp = Blueprint("soroban_deploy", __name__, url_prefix="/api/soroban")
logger = logging.getLogger(__name__)

STELLAR_TESTNET_RPC = "https://soroban-testnet.stellar.org"
STELLAR_TESTNET_NETWORK_PASSPHRASE = "Test SDF Network ; September 2015"
STELLAR_TESTNET_HORIZON = "https://horizon-testnet.stellar.org"
FRIENDBOT_URL = "https://friendbot.stellar.org"


def _get_stellar_sdk():
    """Lazy import stellar_sdk to avoid hard dependency at import time."""
    try:
        from stellar_sdk import (
            Keypair, Network, SorobanServer, TransactionBuilder,
            scval, xdr as stellar_xdr
        )
        from stellar_sdk.soroban_rpc import GetTransactionStatus
        return True, None
    except ImportError:
        return False, (
            "stellar-sdk is not installed. "
            "Add 'stellar-sdk>=11.0.0' to server/requirements.txt and reinstall."
        )


def _resolve_wasm_path(raw_path: str, instance_dir: str) -> str | None:
    """Resolve and validate WASM path is inside instance_dir."""
    base = os.path.abspath(instance_dir)
    target = os.path.abspath(os.path.join(base, raw_path))
    if not target.startswith(base + os.sep) and target != base:
        return None
    if not target.endswith(".wasm"):
        return None
    return target


@soroban_deploy_bp.route("/deploy", methods=["POST"])
@token_required
def deploy_contract(current_user):
    """
    Deploy a compiled Soroban WASM contract to Stellar testnet.

    Request JSON:
        session_id      (int)   — active session ID
        wasm_path       (str)   — relative path to .wasm file inside instance dir
        deployer_secret (str)   — Stellar secret key of the deployer account
        fund_account    (bool)  — fund account via Friendbot if balance is zero (default: true)

    Response JSON:
        success         (bool)
        contract_id     (str)   — deployed contract ID (C...)
        transaction_hash (str)
        network         (str)
        deployer_public_key (str)
        wasm_path       (str)
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        session_id = data.get("session_id")
        if not session_id:
            return jsonify({"success": False, "error": "session_id is required"}), 400

        wasm_path_raw = data.get("wasm_path")
        if not wasm_path_raw:
            return jsonify({"success": False, "error": "wasm_path is required"}), 400

        deployer_secret = data.get("deployer_secret")
        if not deployer_secret:
            return jsonify({"success": False, "error": "deployer_secret is required"}), 400

        # Verify session
        session = Session.query.filter_by(
            id=session_id, user_id=current_user.id, is_active=True
        ).first()
        if not session:
            return jsonify({"success": False, "error": "Session not found or access denied"}), 404

        instance_dir = session.instance_dir
        if not instance_dir or not os.path.isdir(instance_dir):
            return jsonify({"success": False, "error": "Session workspace not found"}), 404

        # Resolve WASM path safely
        wasm_path = _resolve_wasm_path(wasm_path_raw, instance_dir)
        if not wasm_path:
            return jsonify({
                "success": False,
                "error": "Invalid wasm_path — must be a .wasm file inside the session workspace"
            }), 400

        if not os.path.isfile(wasm_path):
            return jsonify({
                "success": False,
                "error": f"WASM file not found: {wasm_path_raw}. Compile the contract first."
            }), 404

        # Check stellar-sdk
        sdk_ok, sdk_err = _get_stellar_sdk()
        if not sdk_ok:
            return jsonify({"success": False, "error": sdk_err}), 500

        # Import SDK
        from stellar_sdk import Keypair, Network, SorobanServer, TransactionBuilder
        from stellar_sdk.exceptions import NotFoundError
        import requests as _requests

        # Validate keypair
        try:
            keypair = Keypair.from_secret(deployer_secret)
        except Exception:
            return jsonify({"success": False, "error": "Invalid deployer_secret key"}), 400

        deployer_public = keypair.public_key
        logger.info(
            f"User {current_user.username} deploying contract "
            f"from {wasm_path_raw} with account {deployer_public}"
        )

        server = SorobanServer(STELLAR_TESTNET_RPC)

        # Fund via Friendbot if requested
        fund_account = data.get("fund_account", True)
        if fund_account:
            try:
                server.load_account(deployer_public)
            except NotFoundError:
                logger.info(f"Funding account {deployer_public} via Friendbot")
                resp = _requests.get(f"{FRIENDBOT_URL}?addr={deployer_public}", timeout=15)
                if not resp.ok:
                    return jsonify({
                        "success": False,
                        "error": f"Friendbot funding failed: {resp.text}"
                    }), 502

        # Load account and read WASM
        source_account = server.load_account(deployer_public)
        with open(wasm_path, "rb") as f:
            wasm_bytes = f.read()

        # Step 1: Upload contract WASM
        upload_tx = (
            TransactionBuilder(
                source_account=source_account,
                network_passphrase=STELLAR_TESTNET_NETWORK_PASSPHRASE,
                base_fee=100,
            )
            .set_timeout(30)
            .append_upload_contract_wasm_op(wasm=wasm_bytes)
            .build()
        )

        upload_tx = server.prepare_transaction(upload_tx)
        upload_tx.sign(keypair)
        upload_response = server.send_transaction(upload_tx)

        # Wait for upload to complete
        upload_result = _wait_for_transaction(server, upload_response.hash)
        if not upload_result["success"]:
            return jsonify({
                "success": False,
                "error": f"WASM upload failed: {upload_result['error']}",
                "transaction_hash": upload_response.hash,
            }), 422

        wasm_hash = upload_result["wasm_hash"]

        # Step 2: Create contract instance
        source_account = server.load_account(deployer_public)
        create_tx = (
            TransactionBuilder(
                source_account=source_account,
                network_passphrase=STELLAR_TESTNET_NETWORK_PASSPHRASE,
                base_fee=100,
            )
            .set_timeout(30)
            .append_create_contract_op(wasm_hash=wasm_hash, address=deployer_public)
            .build()
        )

        create_tx = server.prepare_transaction(create_tx)
        create_tx.sign(keypair)
        create_response = server.send_transaction(create_tx)

        create_result = _wait_for_transaction(server, create_response.hash)
        if not create_result["success"]:
            return jsonify({
                "success": False,
                "error": f"Contract creation failed: {create_result['error']}",
                "transaction_hash": create_response.hash,
                "wasm_upload_hash": upload_response.hash,
            }), 422

        contract_id = create_result["contract_id"]

        logger.info(
            f"Contract deployed successfully by {current_user.username}: "
            f"contract_id={contract_id}, tx={create_response.hash}"
        )

        return jsonify({
            "success": True,
            "contract_id": contract_id,
            "transaction_hash": create_response.hash,
            "wasm_upload_hash": upload_response.hash,
            "network": "testnet",
            "network_passphrase": STELLAR_TESTNET_NETWORK_PASSPHRASE,
            "deployer_public_key": deployer_public,
            "wasm_path": wasm_path_raw,
            "explorer_url": f"https://stellar.expert/explorer/testnet/contract/{contract_id}",
        }), 200

    except Exception as e:
        logger.exception("Deploy contract error")
        capture_exception(e, {
            "route": "soroban_deploy.deploy_contract",
            "user_id": current_user.id,
        })
        return jsonify({"success": False, "error": "An error occurred during deployment"}), 500


def _wait_for_transaction(server, tx_hash: str, max_attempts: int = 10) -> dict:
    """
    Poll for transaction completion. Returns dict with success, and
    wasm_hash or contract_id extracted from the result.
    """
    import time
    from stellar_sdk.soroban_rpc import GetTransactionStatus

    for _ in range(max_attempts):
        time.sleep(2)
        try:
            result = server.get_transaction(tx_hash)
            if result.status == GetTransactionStatus.SUCCESS:
                # Extract wasm_hash or contract_id from result meta
                wasm_hash = None
                contract_id = None
                try:
                    meta = result.result_meta_xdr
                    if meta:
                        from stellar_sdk import xdr as stellar_xdr
                        import base64
                        meta_xdr = stellar_xdr.TransactionMeta.from_xdr(meta)
                        ops = meta_xdr.v3.operations if meta_xdr.v3 else []
                        for op in ops:
                            for change in (op.changes.ledger_entry_changes or []):
                                if hasattr(change, 'created') and change.created:
                                    entry = change.created.data
                                    if hasattr(entry, 'contract_code') and entry.contract_code:
                                        wasm_hash = entry.contract_code.hash.hash.hex()
                                    if hasattr(entry, 'contract_data') and entry.contract_data:
                                        key = entry.contract_data.key
                                        if hasattr(key, 'instance'):
                                            contract_id = _extract_contract_id(result)
                except Exception:
                    # Fallback — try to get contract_id from return value
                    contract_id = _extract_contract_id(result)

                return {"success": True, "wasm_hash": wasm_hash, "contract_id": contract_id}

            elif result.status == GetTransactionStatus.FAILED:
                return {"success": False, "error": "Transaction failed on-chain", "contract_id": None}

        except Exception as e:
            return {"success": False, "error": str(e), "contract_id": None}

    return {"success": False, "error": "Transaction timed out waiting for confirmation", "contract_id": None}


def _extract_contract_id(tx_result) -> str | None:
    """Try to extract contract ID from transaction result."""
    try:
        from stellar_sdk import xdr as stellar_xdr
        if tx_result.return_value:
            val = stellar_xdr.SCVal.from_xdr(tx_result.return_value)
            if val.address:
                from stellar_sdk import Address
                addr = Address.from_xdr_sc_address(val.address)
                return addr.address
    except Exception:
        pass
    return None


@soroban_deploy_bp.route("/deployments/<int:session_id>", methods=["GET"])
@token_required
def list_deployments(current_user, session_id):
    """
    List deployment records stored in the session workspace.

    Response JSON:
        success      (bool)
        deployments  (list[dict])
    """
    try:
        session = Session.query.filter_by(
            id=session_id, user_id=current_user.id, is_active=True
        ).first()
        if not session:
            return jsonify({"success": False, "error": "Session not found or access denied"}), 404

        instance_dir = session.instance_dir
        if not instance_dir or not os.path.isdir(instance_dir):
            return jsonify({"success": True, "deployments": [], "total": 0}), 200

        # Read deployment records from .deployments/ directory
        deploy_dir = os.path.join(instance_dir, ".deployments")
        deployments = []
        if os.path.isdir(deploy_dir):
            import json
            for f in sorted(Path(deploy_dir).glob("*.json"), reverse=True):
                try:
                    deployments.append(json.loads(f.read_text()))
                except Exception:
                    pass

        return jsonify({
            "success": True,
            "deployments": deployments,
            "total": len(deployments),
        }), 200

    except Exception as e:
        logger.exception("List deployments error")
        capture_exception(e, {
            "route": "soroban_deploy.list_deployments",
            "user_id": current_user.id,
            "session_id": session_id,
        })
        return jsonify({"success": False, "error": "An error occurred while listing deployments"}), 500
