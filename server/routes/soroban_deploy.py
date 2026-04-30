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
from server.middleware.rate_limiter import (
    rate_limit, validate_soroban_request, check_friendbot_limits,
    get_client_ip
)

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
@rate_limit('soroban_deploy')
@validate_soroban_request(
    require_contract_id=False,
    require_function_name=False,
    require_secret_key=True,
    require_parameters=False
)
@check_friendbot_limits()
def deploy_contract(current_user):
    """
    [DEPRECATED] Deploy a compiled Soroban WASM contract to Stellar testnet.
    
    SECURITY WARNING: This endpoint accepts secret keys and is deprecated.
    Use /api/soroban/prepare-upload, /api/soroban/prepare-create, and /api/soroban/submit-tx with Freighter wallet instead.
    This endpoint will be removed in a future version.

    Request JSON:
        session_id      (int)   — active session ID
        wasm_path       (str)   — relative path to .wasm file inside instance dir
        deployer_secret (str)   — Stellar secret key of the deployer account [SECURITY RISK]
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
        session_id = data.get("session_id")
        wasm_path_raw = data.get("wasm_path")
        deployer_secret = data.get("deployer_secret")

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


@soroban_deploy_bp.route("/wasm/<int:session_id>", methods=["GET"])
@token_required
@rate_limit('soroban_state')
def download_wasm(current_user, session_id):
    """
    Download a compiled WASM file from a session workspace.
    
    Query params:
        path (str) - relative path to .wasm file
    """
    try:
        wasm_path_raw = request.args.get("path")
        if not wasm_path_raw:
            return jsonify({"success": False, "error": "path is required"}), 400

        session = Session.query.filter_by(
            id=session_id, user_id=current_user.id, is_active=True
        ).first()
        if not session:
            return jsonify({"success": False, "error": "Session not found"}), 404

        instance_dir = session.instance_dir
        wasm_path = _resolve_wasm_path(wasm_path_raw, instance_dir)
        if not wasm_path or not os.path.isfile(wasm_path):
            return jsonify({"success": False, "error": "WASM file not found"}), 404

        from flask import send_file
        return send_file(wasm_path, mimetype="application/wasm")

    except Exception as e:
        logger.exception("Download WASM error")
        return jsonify({"success": False, "error": str(e)}), 500


@soroban_deploy_bp.route("/prepare-upload", methods=["POST"])
@token_required
@rate_limit('soroban_deploy')
@validate_soroban_request(
    require_contract_id=False,
    require_function_name=False,
    require_secret_key=False,
    require_parameters=False
)
def prepare_upload(current_user):
    """
    Build an unsigned transaction to upload contract WASM.
    
    Request JSON:
        session_id    (int)
        wasm_path     (str)
        public_key    (str) - User's Freighter public key
    """
    try:
        data = request.get_json()
        session_id = data.get("session_id")
        wasm_path_raw = data.get("wasm_path")
        public_key = data.get("public_key")
        
        if not all([session_id, wasm_path_raw, public_key]):
            return jsonify({"success": False, "error": "session_id, wasm_path, and public_key are required"}), 400

        session = Session.query.filter_by(id=session_id, user_id=current_user.id, is_active=True).first()
        if not session:
            return jsonify({"success": False, "error": "Session not found"}), 404

        instance_dir = session.instance_dir
        wasm_path = _resolve_wasm_path(wasm_path_raw, instance_dir)
        if not wasm_path or not os.path.isfile(wasm_path):
            return jsonify({"success": False, "error": "WASM file not found"}), 404

        sdk_ok, sdk_err = _get_stellar_sdk()
        if not sdk_ok:
            return jsonify({"success": False, "error": sdk_err}), 500

        from stellar_sdk import SorobanServer, TransactionBuilder, Network
        server = SorobanServer(STELLAR_TESTNET_RPC)
        source_account = server.load_account(public_key)
        
        with open(wasm_path, "rb") as f:
            wasm_bytes = f.read()

        tx = (
            TransactionBuilder(
                source_account=source_account,
                network_passphrase=STELLAR_TESTNET_NETWORK_PASSPHRASE,
                base_fee=100,
            )
            .set_timeout(60)
            .append_upload_contract_wasm_op(wasm=wasm_bytes)
            .build()
        )
        
        tx = server.prepare_transaction(tx)
        
        return jsonify({
            "success": True,
            "unsigned_xdr": tx.to_xdr(),
            "network": "testnet"
        }), 200

    except Exception as e:
        logger.exception("Prepare upload error")
        return jsonify({"success": False, "error": str(e)}), 500


@soroban_deploy_bp.route("/prepare-create", methods=["POST"])
@token_required
@rate_limit('soroban_deploy')
@validate_soroban_request(
    require_contract_id=False,
    require_function_name=False,
    require_secret_key=False,
    require_parameters=False
)
def prepare_create(current_user):
    """
    Build an unsigned transaction to create a contract instance.
    """
    try:
        data = request.get_json()
        session_id = data.get("session_id")
        wasm_hash = data.get("wasm_hash")
        public_key = data.get("public_key")
        
        if not all([session_id, wasm_hash, public_key]):
            return jsonify({"success": False, "error": "session_id, wasm_hash, and public_key are required"}), 400

        sdk_ok, sdk_err = _get_stellar_sdk()
        if not sdk_ok:
            return jsonify({"success": False, "error": sdk_err}), 500

        from stellar_sdk import SorobanServer, TransactionBuilder
        server = SorobanServer(STELLAR_TESTNET_RPC)
        source_account = server.load_account(public_key)

        tx = (
            TransactionBuilder(
                source_account=source_account,
                network_passphrase=STELLAR_TESTNET_NETWORK_PASSPHRASE,
                base_fee=100,
            )
            .set_timeout(60)
            .append_create_contract_op(wasm_hash=wasm_hash, address=public_key)
            .build()
        )
        
        tx = server.prepare_transaction(tx)
        
        return jsonify({
            "success": True,
            "unsigned_xdr": tx.to_xdr(),
            "network": "testnet"
        }), 200

    except Exception as e:
        logger.exception("Prepare create error")
        return jsonify({"success": False, "error": str(e)}), 500


@soroban_deploy_bp.route("/submit-tx", methods=["POST"])
@token_required
@rate_limit('soroban_deploy')
def submit_signed_tx(current_user):
    """
    Submit a signed transaction XDR to the network.
    """
    try:
        data = request.get_json()
        signed_xdr = data.get("signed_xdr")
        
        if not signed_xdr:
            return jsonify({"success": False, "error": "signed_xdr is required"}), 400

        sdk_ok, sdk_err = _get_stellar_sdk()
        if not sdk_ok:
            return jsonify({"success": False, "error": sdk_err}), 500

        from stellar_sdk import SorobanServer, TransactionEnvelope
        server = SorobanServer(STELLAR_TESTNET_RPC)
        
        # We need to know the result to extract wasm_hash or contract_id
        envelope = TransactionEnvelope.from_xdr(signed_xdr, STELLAR_TESTNET_NETWORK_PASSPHRASE)
        submit_response = server.send_transaction(envelope)
        
        result = _wait_for_transaction(server, submit_response.hash)
        if not result["success"]:
            return jsonify({
                "success": False, 
                "error": result["error"],
                "transaction_hash": submit_response.hash
            }), 422

        return jsonify({
            "success": True,
            "transaction_hash": submit_response.hash,
            "wasm_hash": result.get("wasm_hash"),
            "contract_id": result.get("contract_id")
        }), 200

    except Exception as e:
        logger.exception("Submit transaction error")
        return jsonify({"success": False, "error": str(e)}), 500


@soroban_deploy_bp.route("/deployments/<int:session_id>", methods=["GET"])
@token_required
@rate_limit('soroban_state')
def list_deployments(current_user, session_id):
    """
    List deployment records stored in the session workspace.
    """
    try:
        session = Session.query.filter_by(
            id=session_id, user_id=current_user.id, is_active=True
        ).first()
        if not session:
            return jsonify({"success": False, "error": "Session not found"}), 404

        instance_dir = session.instance_dir
        if not instance_dir or not os.path.isdir(instance_dir):
            return jsonify({"success": True, "deployments": [], "total": 0}), 200

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
        return jsonify({"success": False, "error": "Internal error"}), 500
