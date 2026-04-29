"""
Soroban contract invocation and state viewer routes.
Addresses issue #58.

Endpoints:
  POST /api/soroban/invoke                           — call a contract function
  GET  /api/soroban/invocations/<session_id>         — list invocation history
  GET  /api/soroban/events/<session_id>              — contract events from invocations
  GET  /api/soroban/state/<session_id>/<contract_id> — read contract ledger state
"""

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from flask import Blueprint, request, jsonify
from server.utils.auth_utils import token_required
from server.utils.monitoring import capture_exception

try:
    from server.models import Session
except Exception:
    Session = None  # type: ignore

soroban_invoke_bp = Blueprint("soroban_invoke", __name__, url_prefix="/api/soroban")
logger = logging.getLogger(__name__)

STELLAR_TESTNET_RPC = "https://soroban-testnet.stellar.org"
STELLAR_TESTNET_NETWORK_PASSPHRASE = "Test SDF Network ; September 2015"


def _get_stellar_sdk():
    """Lazy import stellar_sdk to avoid hard dependency at import time."""
    try:
        from stellar_sdk import (  # noqa: F401
            Keypair, Network, SorobanServer, TransactionBuilder, Address, scval,
        )
        from stellar_sdk.soroban_rpc import GetTransactionStatus  # noqa: F401
        return True, None
    except ImportError:
        return False, (
            "stellar-sdk is not installed. "
            "Add 'stellar-sdk>=11.0.0' to server/requirements.txt and reinstall."
        )


def _parse_param(raw: str):
    """
    Convert a typed string parameter to the appropriate stellar_sdk SCVal.

    Supported prefixes:
      u32:<n>  u64:<n>  i32:<n>  i64:<n>
      bool:true / bool:false
      address:<G...>
      bytes:<hex>
      sym:<name>   (symbol)
      str:<text>   (string / default)
    """
    from stellar_sdk import scval, Address

    raw = raw.strip()
    if ":" in raw:
        prefix, _, value = raw.partition(":")
        prefix = prefix.lower()
        if prefix == "u32":
            return scval.to_uint32(int(value))
        if prefix == "u64":
            return scval.to_uint64(int(value))
        if prefix == "i32":
            return scval.to_int32(int(value))
        if prefix == "i64":
            return scval.to_int64(int(value))
        if prefix == "bool":
            return scval.to_bool(value.lower() == "true")
        if prefix == "address":
            return scval.to_address(Address(value))
        if prefix == "bytes":
            return scval.to_bytes(bytes.fromhex(value))
        if prefix == "sym":
            return scval.to_symbol(value)
        if prefix == "str":
            return scval.to_string(value)

    return scval.to_string(raw)


def _scval_to_python(val) -> object:
    """Best-effort conversion of an SCVal to a JSON-serialisable Python value."""
    try:
        from stellar_sdk import xdr as stellar_xdr, Address

        t = val.type
        T = stellar_xdr.SCValType

        simple = {
            T.SCV_BOOL: lambda v: v.b,
            T.SCV_VOID: lambda v: None,
            T.SCV_U32: lambda v: v.u32,
            T.SCV_I32: lambda v: v.i32,
            T.SCV_U64: lambda v: v.u64,
            T.SCV_I64: lambda v: v.i64,
            T.SCV_U128: lambda v: str(v.u128.hi << 64 | v.u128.lo),
            T.SCV_I128: lambda v: str(v.i128.hi << 64 | v.i128.lo),
            T.SCV_SYMBOL: lambda v: v.sym.sc_symbol.decode(),
            T.SCV_STRING: lambda v: v.str.sc_string.decode(errors="replace"),
            T.SCV_BYTES: lambda v: v.bytes.sc_bytes.hex(),
            T.SCV_ADDRESS: lambda v: Address.from_xdr_sc_address(v.address).address,
        }
        handler = simple.get(t)
        if handler:
            return handler(val)
        if t == T.SCV_VEC and val.vec:
            return [_scval_to_python(item) for item in val.vec.sc_vec]
        if t == T.SCV_MAP and val.map:
            return {
                _scval_to_python(e.key): _scval_to_python(e.val)
                for e in val.map.sc_map
            }
        return repr(val)
    except Exception:
        return repr(val)


def _extract_soroban_events(result_meta_xdr: str) -> list[dict]:
    """
    Decode contract events emitted during a Soroban transaction.

    Parses the TransactionMetaV3.soroban_meta.events field from the
    result_meta_xdr returned by get_transaction. Only CONTRACT and SYSTEM
    events are included; DIAGNOSTIC events are filtered out.

    Returns a list of dicts with keys: type, contract_id, topics, data.
    Returns an empty list if the XDR cannot be parsed or contains no events.
    """
    if not result_meta_xdr:
        return []
    try:
        from stellar_sdk import xdr as stellar_xdr, StrKey

        meta = stellar_xdr.TransactionMeta.from_xdr(result_meta_xdr)
        if not (meta.v3 and meta.v3.soroban_meta):
            return []

        decoded_events = []
        for event in meta.v3.soroban_meta.events:
            event_type = event.type.name  # "CONTRACT", "SYSTEM", "DIAGNOSTIC"
            if event_type == "DIAGNOSTIC":
                continue

            contract_id = None
            if event.contract_id:
                try:
                    contract_id = StrKey.encode_contract(event.contract_id.hash)
                except Exception:
                    contract_id = event.contract_id.hash.hex()

            topics: list = []
            data = None
            if event.body and event.body.v0:
                v0 = event.body.v0
                topics = [_scval_to_python(t) for t in (v0.topics.sc_vec or [])]
                data = _scval_to_python(v0.data)

            decoded_events.append({
                "type": event_type,
                "contract_id": contract_id,
                "topics": topics,
                "data": data,
            })

        return decoded_events
    except Exception:
        logger.debug("Failed to extract Soroban events from result_meta_xdr", exc_info=True)
        return []


def _save_invocation_record(instance_dir: str, record: dict) -> None:
    """Persist an invocation record to .invocations/ inside the session workspace."""
    inv_dir = os.path.join(instance_dir, ".invocations")
    os.makedirs(inv_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    Path(os.path.join(inv_dir, f"invoke_{ts}.json")).write_text(
        json.dumps(record, default=str)
    )


# ---------------------------------------------------------------------------
# POST /api/soroban/invoke
# ---------------------------------------------------------------------------

@soroban_invoke_bp.route("/invoke", methods=["POST"])
@token_required
def invoke_contract(current_user):
    """
    Call a function on a deployed Soroban contract.

    Request JSON:
        session_id      (int)       — active session ID
        contract_id     (str)       — deployed contract address (C...)
        function_name   (str)       — contract function to call
        parameters      (list[str]) — typed params e.g. ["u32:42", "address:G...", "str:hi"]
        invoker_secret  (str)       — Stellar secret key of the invoking account
        fund_account    (bool)      — fund via Friendbot if needed (default: true)

    Response JSON:
        success, result, transaction_hash, network, invoker_public_key,
        contract_id, function_name, explorer_url
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        session_id = data.get("session_id")
        if not session_id:
            return jsonify({"success": False, "error": "session_id is required"}), 400

        contract_id = (data.get("contract_id") or "").strip()
        if not contract_id:
            return jsonify({"success": False, "error": "contract_id is required"}), 400

        function_name = (data.get("function_name") or "").strip()
        if not function_name:
            return jsonify({"success": False, "error": "function_name is required"}), 400

        invoker_secret = (data.get("invoker_secret") or "").strip()
        if not invoker_secret:
            return jsonify({"success": False, "error": "invoker_secret is required"}), 400

        parameters = data.get("parameters") or []
        if not isinstance(parameters, list):
            return jsonify({"success": False, "error": "parameters must be a list"}), 400

        session = Session.query.filter_by(
            id=session_id, user_id=current_user.id, is_active=True
        ).first()
        if not session:
            return jsonify({"success": False, "error": "Session not found or access denied"}), 404

        instance_dir = session.instance_dir
        if not instance_dir or not os.path.isdir(instance_dir):
            return jsonify({"success": False, "error": "Session workspace not found"}), 404

        sdk_ok, sdk_err = _get_stellar_sdk()
        if not sdk_ok:
            return jsonify({"success": False, "error": sdk_err}), 500

        from stellar_sdk import Keypair, SorobanServer, TransactionBuilder
        from stellar_sdk.exceptions import NotFoundError
        import requests as _requests

        try:
            keypair = Keypair.from_secret(invoker_secret)
        except Exception:
            return jsonify({"success": False, "error": "Invalid invoker_secret key"}), 400

        invoker_public = keypair.public_key
        logger.info(
            "User %s invoking %s::%s with account %s",
            current_user.username, contract_id, function_name, invoker_public,
        )

        server = SorobanServer(STELLAR_TESTNET_RPC)

        if data.get("fund_account", True):
            try:
                server.load_account(invoker_public)
            except NotFoundError:
                logger.info("Funding account %s via Friendbot", invoker_public)
                resp = _requests.get(
                    f"https://friendbot.stellar.org?addr={invoker_public}", timeout=15
                )
                if not resp.ok:
                    return jsonify({
                        "success": False,
                        "error": f"Friendbot funding failed: {resp.text}",
                    }), 502

        try:
            sc_params = [_parse_param(p) for p in parameters]
        except Exception as exc:
            return jsonify({"success": False, "error": f"Invalid parameter format: {exc}"}), 400

        source_account = server.load_account(invoker_public)
        tx = (
            TransactionBuilder(
                source_account=source_account,
                network_passphrase=STELLAR_TESTNET_NETWORK_PASSPHRASE,
                base_fee=100,
            )
            .set_timeout(30)
            .append_invoke_contract_function_op(
                contract_id=contract_id,
                function_name=function_name,
                parameters=sc_params,
            )
            .build()
        )
        tx = server.prepare_transaction(tx)
        tx.sign(keypair)
        send_resp = server.send_transaction(tx)

        invoke_result = _wait_for_transaction(server, send_resp.hash)
        if not invoke_result["success"]:
            return jsonify({
                "success": False,
                "error": f"Invocation failed: {invoke_result['error']}",
                "transaction_hash": send_resp.hash,
            }), 422

        events = _extract_soroban_events(invoke_result.get("result_meta_xdr") or "")

        record = {
            "contract_id": contract_id,
            "function_name": function_name,
            "parameters": parameters,
            "result": invoke_result.get("result"),
            "events": events,
            "transaction_hash": send_resp.hash,
            "invoker_public_key": invoker_public,
            "network": "testnet",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _save_invocation_record(instance_dir, record)

        logger.info(
            "Invocation successful by %s: %s::%s tx=%s",
            current_user.username, contract_id, function_name, send_resp.hash,
        )

        return jsonify({
            "success": True,
            **record,
            "explorer_url": f"https://stellar.expert/explorer/testnet/tx/{send_resp.hash}",
            "event_count": len(events),
        }), 200

    except Exception as e:
        logger.exception("Invoke contract error")
        capture_exception(e, {"route": "soroban_invoke.invoke_contract", "user_id": current_user.id})
        return jsonify({"success": False, "error": "An error occurred during invocation"}), 500


# ---------------------------------------------------------------------------
# GET /api/soroban/invocations/<session_id>
# ---------------------------------------------------------------------------

@soroban_invoke_bp.route("/invocations/<int:session_id>", methods=["GET"])
@token_required
def list_invocations(current_user, session_id):
    """
    Return the invocation history stored in the session workspace.

    Response JSON:
        success, invocations (list), total (int)
    """
    try:
        session = Session.query.filter_by(
            id=session_id, user_id=current_user.id, is_active=True
        ).first()
        if not session:
            return jsonify({"success": False, "error": "Session not found or access denied"}), 404

        instance_dir = session.instance_dir
        if not instance_dir or not os.path.isdir(instance_dir):
            return jsonify({"success": True, "invocations": [], "total": 0}), 200

        inv_dir = os.path.join(instance_dir, ".invocations")
        invocations = []
        if os.path.isdir(inv_dir):
            for f in sorted(Path(inv_dir).glob("*.json"), reverse=True):
                try:
                    invocations.append(json.loads(f.read_text()))
                except Exception:
                    pass

        return jsonify({"success": True, "invocations": invocations, "total": len(invocations)}), 200

    except Exception as e:
        logger.exception("List invocations error")
        capture_exception(e, {
            "route": "soroban_invoke.list_invocations",
            "user_id": current_user.id,
            "session_id": session_id,
        })
        return jsonify({"success": False, "error": "An error occurred while listing invocations"}), 500


# ---------------------------------------------------------------------------
# GET /api/soroban/events/<session_id>
# ---------------------------------------------------------------------------

@soroban_invoke_bp.route("/events/<int:session_id>", methods=["GET"])
@token_required
def list_contract_events(current_user, session_id):
    """
    Return all Soroban contract events emitted across a session's invocations.

    Reads event data persisted in invocation records (populated since this
    feature was added). Supports optional filtering by contract_id.

    Query params:
        contract_id (str) — optional: filter events to a specific contract

    Response JSON:
        success, events (list), total (int)

    Each event dict contains:
        transaction_hash, timestamp, invoked_function,
        type, contract_id, topics, data
    """
    try:
        session = Session.query.filter_by(
            id=session_id, user_id=current_user.id, is_active=True
        ).first()
        if not session:
            return jsonify({"success": False, "error": "Session not found or access denied"}), 404

        instance_dir = session.instance_dir
        if not instance_dir or not os.path.isdir(instance_dir):
            return jsonify({"success": True, "events": [], "total": 0}), 200

        filter_contract = (request.args.get("contract_id") or "").strip() or None

        inv_dir = os.path.join(instance_dir, ".invocations")
        all_events: list[dict] = []

        if os.path.isdir(inv_dir):
            for f in sorted(Path(inv_dir).glob("*.json")):
                try:
                    record = json.loads(f.read_text())
                except Exception:
                    continue

                for event in record.get("events") or []:
                    if filter_contract and event.get("contract_id") != filter_contract:
                        continue
                    all_events.append({
                        "transaction_hash": record.get("transaction_hash"),
                        "timestamp": record.get("timestamp"),
                        "invoked_function": record.get("function_name"),
                        **event,
                    })

        return jsonify({
            "success": True,
            "events": all_events,
            "total": len(all_events),
        }), 200

    except Exception as e:
        logger.exception("list_contract_events error")
        capture_exception(e, {
            "route": "soroban_invoke.list_contract_events",
            "user_id": current_user.id,
            "session_id": session_id,
        })
        return jsonify({"success": False, "error": "An error occurred while listing events"}), 500


# ---------------------------------------------------------------------------
# GET /api/soroban/state/<session_id>/<contract_id>
# ---------------------------------------------------------------------------

@soroban_invoke_bp.route("/state/<int:session_id>/<contract_id>", methods=["GET"])
@token_required
def get_contract_state(current_user, session_id, contract_id):
    """
    Fetch and decode the ledger state entries for a deployed contract.

    Response JSON:
        success, contract_id, state_entries (list[{key, value, durability}]), total
    """
    try:
        session = Session.query.filter_by(
            id=session_id, user_id=current_user.id, is_active=True
        ).first()
        if not session:
            return jsonify({"success": False, "error": "Session not found or access denied"}), 404

        sdk_ok, sdk_err = _get_stellar_sdk()
        if not sdk_ok:
            return jsonify({"success": False, "error": sdk_err}), 500

        from stellar_sdk import SorobanServer, Address, xdr as stellar_xdr

        server = SorobanServer(STELLAR_TESTNET_RPC)

        # Validate contract_id is a proper Stellar contract address
        try:
            contract_address = Address(contract_id)
        except Exception:
            return jsonify({"success": False, "error": "Invalid contract_id — must be a valid Stellar contract address (C...)"}), 400

        # Build the ledger key for the contract instance entry
        instance_key = stellar_xdr.LedgerKey(
            type=stellar_xdr.LedgerEntryType.CONTRACT_DATA,
            contract_data=stellar_xdr.LedgerKeyContractData(
                contract=contract_address.to_xdr_sc_address(),
                key=stellar_xdr.SCVal(
                    type=stellar_xdr.SCValType.SCV_LEDGER_KEY_CONTRACT_INSTANCE
                ),
                durability=stellar_xdr.ContractDataDurability.PERSISTENT,
            ),
        )

        try:
            ledger_resp = server.get_ledger_entries([instance_key])
        except Exception as exc:
            return jsonify({"success": False, "error": f"Failed to fetch contract state: {exc}"}), 502

        state_entries = []
        for entry in (ledger_resp.entries or []):
            try:
                le = stellar_xdr.LedgerEntry.from_xdr(entry.xdr)
                cd = le.data.contract_data
                state_entries.append({
                    "key": _scval_to_python(cd.key),
                    "value": _scval_to_python(cd.val),
                    "durability": cd.durability.name,
                })
            except Exception:
                state_entries.append({"key": entry.xdr, "value": None, "durability": "UNKNOWN"})

        return jsonify({
            "success": True,
            "contract_id": contract_id,
            "state_entries": state_entries,
            "total": len(state_entries),
        }), 200

    except Exception as e:
        logger.exception("Get contract state error")
        capture_exception(e, {
            "route": "soroban_invoke.get_contract_state",
            "user_id": current_user.id,
            "session_id": session_id,
            "contract_id": contract_id,
        })
        return jsonify({"success": False, "error": "An error occurred while fetching contract state"}), 500


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _wait_for_transaction(server, tx_hash: str, max_attempts: int = 10) -> dict:
    """Poll until the transaction is confirmed or times out."""
    import time
    from stellar_sdk.soroban_rpc import GetTransactionStatus
    from stellar_sdk import xdr as stellar_xdr

    for _ in range(max_attempts):
        time.sleep(2)
        try:
            result = server.get_transaction(tx_hash)
            if result.status == GetTransactionStatus.SUCCESS:
                decoded = None
                try:
                    if result.return_value:
                        val = stellar_xdr.SCVal.from_xdr(result.return_value)
                        decoded = _scval_to_python(val)
                except Exception:
                    decoded = result.return_value
                return {
                    "success": True,
                    "result": decoded,
                    "result_meta_xdr": getattr(result, "result_meta_xdr", None),
                }
            if result.status == GetTransactionStatus.FAILED:
                return {"success": False, "error": "Transaction failed on-chain"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    return {"success": False, "error": "Transaction timed out waiting for confirmation"}
