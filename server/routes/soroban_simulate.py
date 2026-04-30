"""
Soroban transaction pre-flight simulation routes.

Simulates contract invocations and WASM deployments against the RPC node
without submitting any transaction. Returns fee estimates, resource
footprints, and — for invoke simulations — the expected return value.

Endpoints:
  POST /api/soroban/simulate/invoke   — simulate a contract function call
  POST /api/soroban/simulate/deploy   — simulate WASM upload fee estimation
"""

import os
import logging
from flask import Blueprint, request, jsonify
from server.utils.auth_utils import token_required
from server.utils.monitoring import capture_exception

try:
    from server.models import Session
except Exception:
    Session = None  # type: ignore

soroban_simulate_bp = Blueprint(
    "soroban_simulate", __name__, url_prefix="/api/soroban/simulate"
)
logger = logging.getLogger(__name__)

_NETWORK_CONFIG = {
    "testnet": {
        "rpc": "https://soroban-testnet.stellar.org",
        "passphrase": "Test SDF Network ; September 2015",
    },
    "mainnet": {
        "rpc": "https://mainnet.sorobanrpc.com",
        "passphrase": "Public Global Stellar Network ; September 2015",
    },
}

_BASE_FEE_STROOPS = 100
_STROOPS_PER_XLM = 10_000_000


def _get_stellar_sdk():
    try:
        from stellar_sdk import Keypair, SorobanServer, TransactionBuilder  # noqa: F401
        return True, None
    except ImportError:
        return False, (
            "stellar-sdk is not installed. "
            "Add 'stellar-sdk>=11.0.0' to server/requirements.txt and reinstall."
        )


def _parse_param(raw: str):
    """Convert a typed string parameter to the appropriate SCVal."""
    from stellar_sdk import scval, Address

    raw = raw.strip()
    if ":" in raw:
        prefix, _, value = raw.partition(":")
        prefix = prefix.lower()
        dispatch = {
            "u32": lambda v: scval.to_uint32(int(v)),
            "u64": lambda v: scval.to_uint64(int(v)),
            "i32": lambda v: scval.to_int32(int(v)),
            "i64": lambda v: scval.to_int64(int(v)),
            "bool": lambda v: scval.to_bool(v.lower() == "true"),
            "address": lambda v: scval.to_address(Address(v)),
            "bytes": lambda v: scval.to_bytes(bytes.fromhex(v)),
            "sym": lambda v: scval.to_symbol(v),
            "str": lambda v: scval.to_string(v),
        }
        if prefix in dispatch:
            return dispatch[prefix](value)
    return scval.to_string(raw)


def _decode_sim_response(sim_response) -> dict:
    """
    Extract fee estimates, resource usage, and simulated return value
    from a SimulateTransactionResponse.
    """
    resource_fee = int(getattr(sim_response, "min_resource_fee", 0) or 0)
    cpu_insns = 0
    mem_bytes = 0
    read_bytes = 0
    write_bytes = 0

    cost = getattr(sim_response, "cost", None)
    if cost:
        cpu_insns = int(getattr(cost, "cpu_insns", 0) or 0)
        mem_bytes = int(getattr(cost, "mem_bytes", 0) or 0)

    tx_data = getattr(sim_response, "transaction_data", None)
    if tx_data:
        try:
            resources = getattr(tx_data, "resources", None)
            if resources:
                read_bytes = int(getattr(resources, "read_bytes", 0) or 0)
                write_bytes = int(getattr(resources, "write_bytes", 0) or 0)
        except Exception:
            pass

    simulated_result = None
    auth_entries: list[str] = []

    results = getattr(sim_response, "results", None) or []
    if results:
        first = results[0]
        xdr_val = getattr(first, "xdr", None)
        if xdr_val:
            try:
                from stellar_sdk import xdr as stellar_xdr
                from server.routes.soroban_invoke import _scval_to_python
                simulated_result = _scval_to_python(
                    stellar_xdr.SCVal.from_xdr(xdr_val)
                )
            except Exception:
                simulated_result = xdr_val

        raw_auth = getattr(first, "auth", None) or []
        auth_entries = [str(a) for a in raw_auth]

    return {
        "resource_fee": resource_fee,
        "cpu_insns": cpu_insns,
        "mem_bytes": mem_bytes,
        "read_bytes": read_bytes,
        "write_bytes": write_bytes,
        "simulated_result": simulated_result,
        "auth_entries": auth_entries,
        "sim_error": getattr(sim_response, "error", None),
    }


def _fee_summary(resource_fee: int) -> dict:
    total = _BASE_FEE_STROOPS + resource_fee
    return {
        "base_fee": _BASE_FEE_STROOPS,
        "resource_fee": resource_fee,
        "total_stroops": total,
        "xlm": f"{total / _STROOPS_PER_XLM:.7f}",
    }


# ---------------------------------------------------------------------------
# POST /api/soroban/simulate/invoke
# ---------------------------------------------------------------------------

@soroban_simulate_bp.route("/invoke", methods=["POST"])
@token_required
def simulate_invoke(current_user):
    """
    Simulate a Soroban contract function call.

    No transaction is submitted; this is a pure read-only preflight
    against the Soroban RPC simulate_transaction endpoint.

    Request JSON:
        session_id          (int)       — active session ID
        contract_id         (str)       — deployed contract address (C...)
        function_name       (str)       — function to simulate
        parameters          (list[str]) — typed params e.g. ["u32:42", "bool:true"]
        invoker_public_key  (str)       — Stellar public key (G...)
        network             (str)       — "testnet" | "mainnet" (default: "testnet")

    Response JSON:
        success             (bool)
        fee                 (dict)  — base_fee, resource_fee, total_stroops, xlm
        resources           (dict)  — cpu_insns, mem_bytes, read_bytes, write_bytes
        simulated_result    (any)   — decoded return value from simulation
        auth_entries        (list)  — auth entries this call requires
        network             (str)
        simulation_error    (str|null) — RPC-level error, if the call would revert
    """
    try:
        data = request.get_json(silent=True, force=True)
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        session_id = data.get("session_id")
        contract_id = (data.get("contract_id") or "").strip()
        function_name = (data.get("function_name") or "").strip()
        invoker_public_key = (data.get("invoker_public_key") or "").strip()
        parameters = data.get("parameters") or []
        network = (data.get("network") or "testnet").lower()

        if not session_id:
            return jsonify({"success": False, "error": "session_id is required"}), 400
        if not contract_id:
            return jsonify({"success": False, "error": "contract_id is required"}), 400
        if not function_name:
            return jsonify({"success": False, "error": "function_name is required"}), 400
        if not invoker_public_key:
            return jsonify({"success": False, "error": "invoker_public_key is required"}), 400
        if not isinstance(parameters, list):
            return jsonify({"success": False, "error": "parameters must be a list"}), 400
        if network not in _NETWORK_CONFIG:
            return jsonify({
                "success": False,
                "error": f"Unsupported network '{network}'. Use 'testnet' or 'mainnet'",
            }), 400

        session = Session.query.filter_by(
            id=session_id, user_id=current_user.id, is_active=True
        ).first()
        if not session:
            return jsonify({"success": False, "error": "Session not found or access denied"}), 404

        sdk_ok, sdk_err = _get_stellar_sdk()
        if not sdk_ok:
            return jsonify({"success": False, "error": sdk_err}), 500

        from stellar_sdk import Keypair, SorobanServer, TransactionBuilder

        try:
            Keypair.from_public_key(invoker_public_key)
        except Exception:
            return jsonify({"success": False, "error": "Invalid invoker_public_key"}), 400

        try:
            sc_params = [_parse_param(p) for p in parameters]
        except Exception as exc:
            return jsonify({"success": False, "error": f"Invalid parameter format: {exc}"}), 400

        cfg = _NETWORK_CONFIG[network]
        server = SorobanServer(cfg["rpc"])

        try:
            source_account = server.load_account(invoker_public_key)
        except Exception as exc:
            return jsonify({
                "success": False,
                "error": (
                    f"Could not load account {invoker_public_key}: {exc}. "
                    "Ensure the account is funded on this network."
                ),
            }), 422

        tx = (
            TransactionBuilder(
                source_account=source_account,
                network_passphrase=cfg["passphrase"],
                base_fee=_BASE_FEE_STROOPS,
            )
            .set_timeout(30)
            .append_invoke_contract_function_op(
                contract_id=contract_id,
                function_name=function_name,
                parameters=sc_params,
            )
            .build()
        )

        try:
            sim_response = server.simulate_transaction(tx)
        except Exception as exc:
            return jsonify({"success": False, "error": f"RPC simulation failed: {exc}"}), 502

        decoded = _decode_sim_response(sim_response)

        logger.info(
            "simulate_invoke: user=%s contract=%s fn=%s fee=%d stroops network=%s",
            current_user.username,
            contract_id,
            function_name,
            _BASE_FEE_STROOPS + decoded["resource_fee"],
            network,
        )

        return jsonify({
            "success": True,
            "fee": _fee_summary(decoded["resource_fee"]),
            "resources": {
                "cpu_insns": decoded["cpu_insns"],
                "mem_bytes": decoded["mem_bytes"],
                "read_bytes": decoded["read_bytes"],
                "write_bytes": decoded["write_bytes"],
            },
            "simulated_result": decoded["simulated_result"],
            "auth_entries": decoded["auth_entries"],
            "network": network,
            "simulation_error": decoded["sim_error"],
        }), 200

    except Exception as e:
        logger.exception("simulate_invoke error")
        capture_exception(e, {
            "route": "soroban_simulate.simulate_invoke",
            "user_id": current_user.id,
        })
        return jsonify({"success": False, "error": "An error occurred during simulation"}), 500


# ---------------------------------------------------------------------------
# POST /api/soroban/simulate/deploy
# ---------------------------------------------------------------------------

@soroban_simulate_bp.route("/deploy", methods=["POST"])
@token_required
def simulate_deploy(current_user):
    """
    Simulate the WASM upload step of a Soroban contract deployment.

    The contract creation step fee depends on the resulting WASM hash
    (computed after upload) so only the upload fee can be pre-flighted.
    The response includes a conservative combined estimate.

    Request JSON:
        session_id           (int)  — active session ID
        wasm_path            (str)  — relative path to .wasm inside session workspace
        deployer_public_key  (str)  — Stellar public key (G...)
        network              (str)  — "testnet" | "mainnet" (default: "testnet")

    Response JSON:
        success              (bool)
        upload_fee           (dict) — fee breakdown for the WASM upload step
        wasm_size_bytes      (int)
        network              (str)
        note                 (str)  — explains the create_fee estimation limitation
    """
    try:
        data = request.get_json(silent=True, force=True)
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        session_id = data.get("session_id")
        wasm_path_raw = (data.get("wasm_path") or "").strip()
        deployer_public_key = (data.get("deployer_public_key") or "").strip()
        network = (data.get("network") or "testnet").lower()

        if not session_id:
            return jsonify({"success": False, "error": "session_id is required"}), 400
        if not wasm_path_raw:
            return jsonify({"success": False, "error": "wasm_path is required"}), 400
        if not deployer_public_key:
            return jsonify({"success": False, "error": "deployer_public_key is required"}), 400
        if network not in _NETWORK_CONFIG:
            return jsonify({"success": False, "error": f"Unsupported network '{network}'"}), 400

        session = Session.query.filter_by(
            id=session_id, user_id=current_user.id, is_active=True
        ).first()
        if not session:
            return jsonify({"success": False, "error": "Session not found or access denied"}), 404

        instance_dir = session.instance_dir
        if not instance_dir or not os.path.isdir(instance_dir):
            return jsonify({"success": False, "error": "Session workspace not found"}), 404

        from server.routes.soroban_deploy import _resolve_wasm_path
        wasm_path = _resolve_wasm_path(wasm_path_raw, instance_dir)
        if not wasm_path or not os.path.isfile(wasm_path):
            return jsonify({
                "success": False,
                "error": f"WASM file not found: {wasm_path_raw}. Compile the contract first.",
            }), 404

        sdk_ok, sdk_err = _get_stellar_sdk()
        if not sdk_ok:
            return jsonify({"success": False, "error": sdk_err}), 500

        from stellar_sdk import Keypair, SorobanServer, TransactionBuilder

        try:
            Keypair.from_public_key(deployer_public_key)
        except Exception:
            return jsonify({"success": False, "error": "Invalid deployer_public_key"}), 400

        cfg = _NETWORK_CONFIG[network]
        server = SorobanServer(cfg["rpc"])

        try:
            source_account = server.load_account(deployer_public_key)
        except Exception as exc:
            return jsonify({
                "success": False,
                "error": f"Could not load account {deployer_public_key}: {exc}",
            }), 422

        with open(wasm_path, "rb") as f:
            wasm_bytes = f.read()

        upload_tx = (
            TransactionBuilder(
                source_account=source_account,
                network_passphrase=cfg["passphrase"],
                base_fee=_BASE_FEE_STROOPS,
            )
            .set_timeout(30)
            .append_upload_contract_wasm_op(wasm=wasm_bytes)
            .build()
        )

        try:
            sim_response = server.simulate_transaction(upload_tx)
        except Exception as exc:
            return jsonify({"success": False, "error": f"Upload simulation failed: {exc}"}), 502

        decoded = _decode_sim_response(sim_response)
        upload_fee = _fee_summary(decoded["resource_fee"])

        logger.info(
            "simulate_deploy: user=%s wasm_size=%d upload_fee=%d stroops network=%s",
            current_user.username,
            len(wasm_bytes),
            upload_fee["total_stroops"],
            network,
        )

        return jsonify({
            "success": True,
            "upload_fee": {
                **upload_fee,
                "resources": {
                    "cpu_insns": decoded["cpu_insns"],
                    "mem_bytes": decoded["mem_bytes"],
                    "read_bytes": decoded["read_bytes"],
                    "write_bytes": decoded["write_bytes"],
                },
            },
            "wasm_size_bytes": len(wasm_bytes),
            "network": network,
            "note": (
                "create_fee depends on the uploaded WASM hash and can only be "
                "estimated after the upload transaction is confirmed."
            ),
        }), 200

    except Exception as e:
        logger.exception("simulate_deploy error")
        capture_exception(e, {
            "route": "soroban_simulate.simulate_deploy",
            "user_id": current_user.id,
        })
        return jsonify({"success": False, "error": "An error occurred during simulation"}), 500
