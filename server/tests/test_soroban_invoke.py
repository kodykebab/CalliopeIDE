"""Tests for server/routes/soroban_invoke.py — issue #58"""

import os
import json
import sys
import functools
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Stub auth / models / monitoring before importing the module under test
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
    import server.routes.soroban_invoke as m  # noqa: E402


from flask import Flask  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(instance_dir):
    s = MagicMock()
    s.id = 1
    s.user_id = 1
    s.is_active = True
    s.instance_dir = instance_dir
    return s


def _no_session():
    x = MagicMock()
    x.query.filter_by.return_value.first.return_value = None
    return x


def _yes_session(d):
    x = MagicMock()
    x.query.filter_by.return_value.first.return_value = _make_session(d)
    return x


@pytest.fixture
def app():
    a = Flask(__name__)
    a.config["TESTING"] = True
    a.config["SECRET_KEY"] = "test"
    a.register_blueprint(m.soroban_invoke_bp)
    return a


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# POST /api/soroban/invoke — validation
# ---------------------------------------------------------------------------

class TestInvokeValidation:
    def test_missing_session_id(self, client):
        resp = client.post("/api/soroban/invoke", json={
            "contract_id": "CTEST", "function_name": "hello", "invoker_secret": "S"
        })
        assert resp.status_code == 400
        assert b"session_id" in resp.data

    def test_missing_contract_id(self, client):
        resp = client.post("/api/soroban/invoke", json={
            "session_id": 1, "function_name": "hello", "invoker_secret": "S"
        })
        assert resp.status_code == 400
        assert b"contract_id" in resp.data

    def test_missing_function_name(self, client):
        valid_contract = "CAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD2KM"
        resp = client.post("/api/soroban/invoke", json={
            "session_id": 1, "contract_id": valid_contract, "invoker_secret": "S"
        })
        assert resp.status_code == 400
        assert b"function_name" in resp.data

    def test_missing_invoker_secret(self, client):
        valid_contract = "CAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD2KM"
        resp = client.post("/api/soroban/invoke", json={
            "session_id": 1, "contract_id": valid_contract, "function_name": "hello"
        })
        assert resp.status_code == 400
        assert b"invoker_secret" in resp.data

    def test_parameters_not_list(self, client, tmp_path):
        d = str(tmp_path / "inst"); os.makedirs(d)
        m.Session = _yes_session(d)
        valid_contract = "CAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD2KM"
        resp = client.post("/api/soroban/invoke", json={
            "session_id": 1, "contract_id": valid_contract,
            "function_name": "hello", "invoker_secret": "S",
            "parameters": "not-a-list",
        })
        assert resp.status_code == 400
        assert b"parameters" in resp.data

    def test_session_not_found(self, client):
        m.Session = _no_session()
        valid_contract = "CAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD2KM"
        resp = client.post("/api/soroban/invoke", json={
            "session_id": 99, "contract_id": valid_contract,
            "function_name": "hello", "invoker_secret": "S"
        })
        assert resp.status_code == 404

    def test_stellar_sdk_missing(self, client, tmp_path):
        d = str(tmp_path / "inst"); os.makedirs(d)
        m.Session = _yes_session(d)
        m._get_stellar_sdk = lambda: (False, "stellar-sdk is not installed")
        valid_contract = "CAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD2KM"
        resp = client.post("/api/soroban/invoke", json={
            "session_id": 1, "contract_id": valid_contract,
            "function_name": "hello", "invoker_secret": "S"
        })
        assert resp.status_code == 500
        assert b"stellar-sdk" in resp.data

    def test_invalid_invoker_secret(self, client, tmp_path):
        d = str(tmp_path / "inst"); os.makedirs(d)
        m.Session = _yes_session(d)
        m._get_stellar_sdk = lambda: (True, None)
        valid_contract = "CAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD2KM"

        with patch("stellar_sdk.Keypair.from_secret", side_effect=Exception("bad key")):
            resp = client.post("/api/soroban/invoke", json={
                "session_id": 1, "contract_id": valid_contract,
                "function_name": "hello", "invoker_secret": "BADKEY"
            })

        assert resp.status_code == 400
        assert b"Invalid invoker_secret" in resp.data


# ---------------------------------------------------------------------------
# GET /api/soroban/invocations/<session_id>
# ---------------------------------------------------------------------------

class TestListInvocations:
    def test_session_not_found(self, client):
        m.Session = _no_session()
        resp = client.get("/api/soroban/invocations/99")
        assert resp.status_code == 404

    def test_empty_history(self, client, tmp_path):
        d = str(tmp_path / "inst"); os.makedirs(d)
        m.Session = _yes_session(d)
        resp = client.get("/api/soroban/invocations/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 0
        assert data["invocations"] == []

    def test_returns_records(self, client, tmp_path):
        d = str(tmp_path / "inst"); os.makedirs(d)
        inv_dir = tmp_path / "inst" / ".invocations"
        os.makedirs(inv_dir)
        record = {
            "contract_id": "CTEST123",
            "function_name": "hello",
            "result": "world",
            "transaction_hash": "abc123",
        }
        (inv_dir / "invoke_20260101T000000000000.json").write_text(json.dumps(record))
        m.Session = _yes_session(d)
        resp = client.get("/api/soroban/invocations/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        assert data["invocations"][0]["contract_id"] == "CTEST123"
        assert data["invocations"][0]["function_name"] == "hello"


# ---------------------------------------------------------------------------
# GET /api/soroban/state/<session_id>/<contract_id>
# ---------------------------------------------------------------------------

class TestGetContractState:
    # A valid Stellar contract address (C... strkey, 56 chars)
    VALID_CONTRACT = "CAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD2KM"

    def test_session_not_found(self, client):
        m.Session = _no_session()
        resp = client.get("/api/soroban/state/99/CTEST")
        assert resp.status_code == 404

    def test_stellar_sdk_missing(self, client, tmp_path):
        d = str(tmp_path / "inst"); os.makedirs(d)
        m.Session = _yes_session(d)
        m._get_stellar_sdk = lambda: (False, "stellar-sdk is not installed")
        resp = client.get("/api/soroban/state/1/CTEST")
        assert resp.status_code == 500
        assert b"stellar-sdk" in resp.data

    def test_invalid_contract_id_returns_400(self, client, tmp_path):
        d = str(tmp_path / "inst"); os.makedirs(d)
        m.Session = _yes_session(d)
        m._get_stellar_sdk = lambda: (True, None)
        resp = client.get("/api/soroban/state/1/NOTACONTRACT")
        assert resp.status_code == 400
        assert b"Invalid contract_id" in resp.data

    def test_rpc_error_returns_502(self, client, tmp_path):
        d = str(tmp_path / "inst"); os.makedirs(d)
        m.Session = _yes_session(d)
        m._get_stellar_sdk = lambda: (True, None)

        with patch("stellar_sdk.SorobanServer") as mock_srv:
            mock_srv.return_value.get_ledger_entries.side_effect = Exception("RPC error")
            resp = client.get(f"/api/soroban/state/1/{self.VALID_CONTRACT}")

        assert resp.status_code == 502
        assert b"Failed to fetch" in resp.data

    def test_empty_state(self, client, tmp_path):
        d = str(tmp_path / "inst"); os.makedirs(d)
        m.Session = _yes_session(d)
        m._get_stellar_sdk = lambda: (True, None)

        with patch("stellar_sdk.SorobanServer") as mock_srv:
            mock_srv.return_value.get_ledger_entries.return_value.entries = []
            resp = client.get(f"/api/soroban/state/1/{self.VALID_CONTRACT}")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["total"] == 0
        assert data["state_entries"] == []


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# GET /api/soroban/events/<session_id>
# ---------------------------------------------------------------------------

class TestListContractEvents:
    def test_session_not_found(self, client):
        m.Session = _no_session()
        resp = client.get("/api/soroban/events/99")
        assert resp.status_code == 404

    def test_empty_when_no_invocations(self, client, tmp_path):
        d = str(tmp_path / "inst")
        os.makedirs(d)
        m.Session = _yes_session(d)
        resp = client.get("/api/soroban/events/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["events"] == []
        assert data["total"] == 0

    def test_returns_events_from_invocation_records(self, client, tmp_path):
        d = str(tmp_path / "inst")
        os.makedirs(d)
        inv_dir = tmp_path / "inst" / ".invocations"
        os.makedirs(inv_dir)

        record = {
            "contract_id": "CTEST123",
            "function_name": "transfer",
            "transaction_hash": "abc123",
            "timestamp": "2026-04-29T10:00:00+00:00",
            "events": [
                {
                    "type": "CONTRACT",
                    "contract_id": "CTEST123",
                    "topics": ["transfer"],
                    "data": {"amount": 100},
                }
            ],
        }
        (inv_dir / "invoke_20260429T100000000000.json").write_text(
            json.dumps(record)
        )
        m.Session = _yes_session(d)
        resp = client.get("/api/soroban/events/1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        evt = data["events"][0]
        assert evt["type"] == "CONTRACT"
        assert evt["contract_id"] == "CTEST123"
        assert evt["topics"] == ["transfer"]
        assert evt["transaction_hash"] == "abc123"
        assert evt["invoked_function"] == "transfer"

    def test_filter_by_contract_id(self, client, tmp_path):
        d = str(tmp_path / "inst")
        os.makedirs(d)
        inv_dir = tmp_path / "inst" / ".invocations"
        os.makedirs(inv_dir)

        for i, cid in enumerate(["CAAAA", "CBBBB"]):
            record = {
                "contract_id": cid,
                "function_name": "fn",
                "transaction_hash": f"tx{i}",
                "timestamp": "2026-04-29T10:00:00+00:00",
                "events": [
                    {"type": "CONTRACT", "contract_id": cid, "topics": ["evt"], "data": None}
                ],
            }
            (inv_dir / f"invoke_2026042900000000000{i}.json").write_text(json.dumps(record))

        m.Session = _yes_session(d)
        resp = client.get("/api/soroban/events/1?contract_id=CAAAA")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        assert data["events"][0]["contract_id"] == "CAAAA"

    def test_invocations_without_events_field_are_skipped(self, client, tmp_path):
        d = str(tmp_path / "inst")
        os.makedirs(d)
        inv_dir = tmp_path / "inst" / ".invocations"
        os.makedirs(inv_dir)

        # Old-style record without events field
        record = {
            "contract_id": "CTEST",
            "function_name": "hello",
            "transaction_hash": "abc",
        }
        (inv_dir / "invoke_20260429T000000000000.json").write_text(json.dumps(record))

        m.Session = _yes_session(d)
        resp = client.get("/api/soroban/events/1")
        assert resp.status_code == 200
        assert resp.get_json()["total"] == 0


# ---------------------------------------------------------------------------
# Unit tests — _extract_soroban_events
# ---------------------------------------------------------------------------

class TestExtractSorobanEvents:
    def test_empty_string_returns_empty(self):
        assert m._extract_soroban_events("") == []

    def test_none_returns_empty(self):
        assert m._extract_soroban_events(None) == []  # type: ignore[arg-type]

    def test_invalid_xdr_returns_empty(self):
        assert m._extract_soroban_events("not-valid-xdr") == []

    def test_diagnostic_events_are_filtered(self):
        mock_event = MagicMock()
        mock_event.type.name = "DIAGNOSTIC"

        mock_meta = MagicMock()
        mock_meta.v3.soroban_meta.events = [mock_event]

        with patch("stellar_sdk.xdr.TransactionMeta.from_xdr", return_value=mock_meta), \
             patch("stellar_sdk.StrKey"):
            result = m._extract_soroban_events("fakexdr")

        assert result == []

    def test_contract_event_decoded(self):
        from stellar_sdk import scval

        mock_topic_val = MagicMock()
        mock_data_val = MagicMock()

        mock_event = MagicMock()
        mock_event.type.name = "CONTRACT"
        mock_event.contract_id = None
        mock_event.body.v0.topics.sc_vec = [mock_topic_val]
        mock_event.body.v0.data = mock_data_val

        mock_meta = MagicMock()
        mock_meta.v3.soroban_meta.events = [mock_event]

        with patch("stellar_sdk.xdr.TransactionMeta.from_xdr", return_value=mock_meta), \
             patch.object(m, "_scval_to_python", side_effect=["transfer_topic", "transfer_data"]):
            result = m._extract_soroban_events("fakexdr")

        assert len(result) == 1
        assert result[0]["type"] == "CONTRACT"
        assert result[0]["contract_id"] is None
        assert result[0]["topics"] == ["transfer_topic"]
        assert result[0]["data"] == "transfer_data"


class TestParseParam:
    def test_u32(self):
        from stellar_sdk import scval
        result = m._parse_param("u32:42")
        assert result == scval.to_uint32(42)

    def test_bool_true(self):
        from stellar_sdk import scval
        result = m._parse_param("bool:true")
        assert result == scval.to_bool(True)

    def test_bool_false(self):
        from stellar_sdk import scval
        result = m._parse_param("bool:false")
        assert result == scval.to_bool(False)

    def test_sym(self):
        from stellar_sdk import scval
        result = m._parse_param("sym:transfer")
        assert result == scval.to_symbol("transfer")

    def test_str_prefix(self):
        from stellar_sdk import scval
        result = m._parse_param("str:hello world")
        assert result == scval.to_string("hello world")

    def test_default_string(self):
        from stellar_sdk import scval
        result = m._parse_param("plain text")
        assert result == scval.to_string("plain text")

    def test_bytes(self):
        from stellar_sdk import scval
        result = m._parse_param("bytes:deadbeef")
        assert result == scval.to_bytes(bytes.fromhex("deadbeef"))
