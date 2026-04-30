"""Tests for server/routes/soroban_simulate.py"""

import functools
import os
import pytest
from unittest.mock import MagicMock, patch
from flask import Flask


# ---------------------------------------------------------------------------
# Stub auth / models / monitoring so we can import the module under test
# without a live database or Stellar SDK
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

_soroban_deploy_stub = MagicMock()
_soroban_deploy_stub._resolve_wasm_path = MagicMock(return_value=None)

_module_stubs = {
    "server.utils.auth_utils": _auth_stub,
    "server.models": MagicMock(),
    "server.utils.monitoring": MagicMock(),
    "server.routes.soroban_deploy": _soroban_deploy_stub,
    "server.routes.soroban_invoke": MagicMock(),
    # Prevent auth_routes chain from being imported via server.routes.__init__
    "email_validator": MagicMock(),
    "flask_migrate": MagicMock(),
    "flask_sqlalchemy": MagicMock(),
    "sentry_sdk": MagicMock(),
    "sentry_sdk.integrations": MagicMock(),
    "sentry_sdk.integrations.flask": MagicMock(),
    "google.generativeai": MagicMock(),
    "google": MagicMock(),
}

with patch.dict("sys.modules", _module_stubs):
    import server.routes.soroban_simulate as m


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_session(instance_dir: str):
    s = MagicMock()
    s.id = 1
    s.user_id = 1
    s.is_active = True
    s.instance_dir = instance_dir
    return s


def _session_found(d: str):
    x = MagicMock()
    x.query.filter_by.return_value.first.return_value = _make_session(d)
    return x


def _session_not_found():
    x = MagicMock()
    x.query.filter_by.return_value.first.return_value = None
    return x


def _sim_response(resource_fee=5000, cpu_insns="1000000", mem_bytes="512000",
                  error=None, results=None):
    r = MagicMock()
    r.min_resource_fee = resource_fee
    r.cost.cpu_insns = cpu_insns
    r.cost.mem_bytes = mem_bytes
    r.error = error
    r.results = results or []
    r.transaction_data = None
    return r


@pytest.fixture
def app():
    a = Flask(__name__)
    a.config["TESTING"] = True
    a.register_blueprint(m.soroban_simulate_bp)
    return a


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# POST /api/soroban/simulate/invoke — input validation
# ---------------------------------------------------------------------------

class TestSimulateInvokeValidation:
    def test_no_body(self, client):
        resp = client.post("/api/soroban/simulate/invoke")
        assert resp.status_code == 400

    def test_missing_session_id(self, client):
        resp = client.post("/api/soroban/simulate/invoke", json={
            "contract_id": "CTEST",
            "function_name": "hello",
            "invoker_public_key": "G" + "A" * 55,
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "session_id" in data["error"]

    def test_missing_contract_id(self, client):
        resp = client.post("/api/soroban/simulate/invoke", json={
            "session_id": 1,
            "function_name": "hello",
            "invoker_public_key": "G" + "A" * 55,
        })
        assert resp.status_code == 400
        assert "contract_id" in resp.get_json()["error"]

    def test_missing_function_name(self, client):
        resp = client.post("/api/soroban/simulate/invoke", json={
            "session_id": 1,
            "contract_id": "CTEST",
            "invoker_public_key": "G" + "A" * 55,
        })
        assert resp.status_code == 400
        assert "function_name" in resp.get_json()["error"]

    def test_missing_invoker_public_key(self, client):
        resp = client.post("/api/soroban/simulate/invoke", json={
            "session_id": 1,
            "contract_id": "CTEST",
            "function_name": "hello",
        })
        assert resp.status_code == 400
        assert "invoker_public_key" in resp.get_json()["error"]

    def test_parameters_not_a_list(self, client, tmp_path):
        d = str(tmp_path / "inst")
        os.makedirs(d)
        m.Session = _session_found(d)
        resp = client.post("/api/soroban/simulate/invoke", json={
            "session_id": 1,
            "contract_id": "CTEST",
            "function_name": "hello",
            "invoker_public_key": "G" + "A" * 55,
            "parameters": "not-a-list",
        })
        assert resp.status_code == 400
        assert "parameters" in resp.get_json()["error"]

    def test_unsupported_network(self, client, tmp_path):
        d = str(tmp_path / "inst")
        os.makedirs(d)
        m.Session = _session_found(d)
        resp = client.post("/api/soroban/simulate/invoke", json={
            "session_id": 1,
            "contract_id": "CTEST",
            "function_name": "hello",
            "invoker_public_key": "G" + "A" * 55,
            "network": "devnet",
        })
        assert resp.status_code == 400
        assert "network" in resp.get_json()["error"].lower()

    def test_session_not_found(self, client):
        m.Session = _session_not_found()
        resp = client.post("/api/soroban/simulate/invoke", json={
            "session_id": 99,
            "contract_id": "CTEST",
            "function_name": "hello",
            "invoker_public_key": "G" + "A" * 55,
        })
        assert resp.status_code == 404

    def test_stellar_sdk_missing(self, client, tmp_path):
        d = str(tmp_path / "inst")
        os.makedirs(d)
        m.Session = _session_found(d)
        m._get_stellar_sdk = lambda: (False, "stellar-sdk is not installed")
        resp = client.post("/api/soroban/simulate/invoke", json={
            "session_id": 1,
            "contract_id": "CTEST",
            "function_name": "hello",
            "invoker_public_key": "G" + "A" * 55,
        })
        assert resp.status_code == 500
        assert "stellar-sdk" in resp.get_json()["error"]

    def test_invalid_public_key(self, client, tmp_path):
        d = str(tmp_path / "inst")
        os.makedirs(d)
        m.Session = _session_found(d)
        m._get_stellar_sdk = lambda: (True, None)

        with patch("stellar_sdk.Keypair.from_public_key", side_effect=Exception("bad key")):
            resp = client.post("/api/soroban/simulate/invoke", json={
                "session_id": 1,
                "contract_id": "CTEST",
                "function_name": "hello",
                "invoker_public_key": "NOTAKEY",
            })
        assert resp.status_code == 400
        assert "invoker_public_key" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# POST /api/soroban/simulate/invoke — happy path
# ---------------------------------------------------------------------------

class TestSimulateInvokeSuccess:
    _VALID_PUBKEY = "GAHJJJKMOKYE4RVPZEWZTKH5FVI4PA3VL7GK2LFNUBSGBV73AAUG4HA"

    def _setup(self, tmp_path):
        d = str(tmp_path / "inst")
        os.makedirs(d)
        m.Session = _session_found(d)
        m._get_stellar_sdk = lambda: (True, None)

    def test_returns_fee_and_resources(self, client, tmp_path):
        self._setup(tmp_path)

        sim = _sim_response(resource_fee=7500, cpu_insns="2500000", mem_bytes="640000")

        with patch("stellar_sdk.Keypair.from_public_key"), \
             patch("stellar_sdk.SorobanServer") as MockServer:
            srv = MockServer.return_value
            srv.load_account.return_value = MagicMock()
            srv.simulate_transaction.return_value = sim

            with patch("stellar_sdk.TransactionBuilder") as MockTxB:
                MockTxB.return_value.set_timeout.return_value.append_invoke_contract_function_op \
                    .return_value.build.return_value = MagicMock()

                resp = client.post("/api/soroban/simulate/invoke", json={
                    "session_id": 1,
                    "contract_id": "CTEST123",
                    "function_name": "balance",
                    "invoker_public_key": self._VALID_PUBKEY,
                    "parameters": [],
                    "network": "testnet",
                })

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

        fee = data["fee"]
        assert fee["base_fee"] == 100
        assert fee["resource_fee"] == 7500
        assert fee["total_stroops"] == 7600
        assert "XLM" not in fee["xlm"]  # just the number
        assert float(fee["xlm"]) > 0

        resources = data["resources"]
        assert resources["cpu_insns"] == 2500000
        assert resources["mem_bytes"] == 640000

        assert data["network"] == "testnet"

    def test_empty_parameters_accepted(self, client, tmp_path):
        self._setup(tmp_path)
        sim = _sim_response()

        with patch("stellar_sdk.Keypair.from_public_key"), \
             patch("stellar_sdk.SorobanServer") as MockServer, \
             patch("stellar_sdk.TransactionBuilder") as MockTxB:

            MockServer.return_value.load_account.return_value = MagicMock()
            MockServer.return_value.simulate_transaction.return_value = sim
            MockTxB.return_value.set_timeout.return_value \
                .append_invoke_contract_function_op.return_value.build.return_value = MagicMock()

            resp = client.post("/api/soroban/simulate/invoke", json={
                "session_id": 1,
                "contract_id": "CTEST",
                "function_name": "get_count",
                "invoker_public_key": self._VALID_PUBKEY,
            })

        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_simulation_error_propagated(self, client, tmp_path):
        self._setup(tmp_path)
        sim = _sim_response(error="HostError: value not found")

        with patch("stellar_sdk.Keypair.from_public_key"), \
             patch("stellar_sdk.SorobanServer") as MockServer, \
             patch("stellar_sdk.TransactionBuilder") as MockTxB:

            MockServer.return_value.load_account.return_value = MagicMock()
            MockServer.return_value.simulate_transaction.return_value = sim
            MockTxB.return_value.set_timeout.return_value \
                .append_invoke_contract_function_op.return_value.build.return_value = MagicMock()

            resp = client.post("/api/soroban/simulate/invoke", json={
                "session_id": 1,
                "contract_id": "CTEST",
                "function_name": "missing_fn",
                "invoker_public_key": self._VALID_PUBKEY,
            })

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "HostError" in data["simulation_error"]

    def test_rpc_error_returns_502(self, client, tmp_path):
        self._setup(tmp_path)

        with patch("stellar_sdk.Keypair.from_public_key"), \
             patch("stellar_sdk.SorobanServer") as MockServer, \
             patch("stellar_sdk.TransactionBuilder") as MockTxB:

            MockServer.return_value.load_account.return_value = MagicMock()
            MockServer.return_value.simulate_transaction.side_effect = Exception("connection refused")
            MockTxB.return_value.set_timeout.return_value \
                .append_invoke_contract_function_op.return_value.build.return_value = MagicMock()

            resp = client.post("/api/soroban/simulate/invoke", json={
                "session_id": 1,
                "contract_id": "CTEST",
                "function_name": "hello",
                "invoker_public_key": self._VALID_PUBKEY,
            })

        assert resp.status_code == 502

    def test_account_not_found_returns_422(self, client, tmp_path):
        self._setup(tmp_path)

        with patch("stellar_sdk.Keypair.from_public_key"), \
             patch("stellar_sdk.SorobanServer") as MockServer, \
             patch("stellar_sdk.TransactionBuilder"):

            MockServer.return_value.load_account.side_effect = Exception("not found")

            resp = client.post("/api/soroban/simulate/invoke", json={
                "session_id": 1,
                "contract_id": "CTEST",
                "function_name": "hello",
                "invoker_public_key": self._VALID_PUBKEY,
            })

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/soroban/simulate/deploy — input validation
# ---------------------------------------------------------------------------

class TestSimulateDeployValidation:
    def test_missing_session_id(self, client):
        resp = client.post("/api/soroban/simulate/deploy", json={
            "wasm_path": "contract.wasm",
            "deployer_public_key": "G" + "A" * 55,
        })
        assert resp.status_code == 400
        assert "session_id" in resp.get_json()["error"]

    def test_missing_wasm_path(self, client):
        resp = client.post("/api/soroban/simulate/deploy", json={
            "session_id": 1,
            "deployer_public_key": "G" + "A" * 55,
        })
        assert resp.status_code == 400
        assert "wasm_path" in resp.get_json()["error"]

    def test_missing_deployer_public_key(self, client):
        resp = client.post("/api/soroban/simulate/deploy", json={
            "session_id": 1,
            "wasm_path": "contract.wasm",
        })
        assert resp.status_code == 400
        assert "deployer_public_key" in resp.get_json()["error"]

    def test_session_not_found(self, client):
        m.Session = _session_not_found()
        resp = client.post("/api/soroban/simulate/deploy", json={
            "session_id": 99,
            "wasm_path": "contract.wasm",
            "deployer_public_key": "G" + "A" * 55,
        })
        assert resp.status_code == 404

    def test_wasm_file_not_found(self, client, tmp_path):
        d = str(tmp_path / "inst")
        os.makedirs(d)
        m.Session = _session_found(d)
        m._get_stellar_sdk = lambda: (True, None)

        deploy_stub = MagicMock()
        deploy_stub._resolve_wasm_path.return_value = None

        with patch.dict("sys.modules", {"server.routes.soroban_deploy": deploy_stub}):
            resp = client.post("/api/soroban/simulate/deploy", json={
                "session_id": 1,
                "wasm_path": "nonexistent.wasm",
                "deployer_public_key": "G" + "A" * 55,
            })
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/soroban/simulate/deploy — happy path
# ---------------------------------------------------------------------------

class TestSimulateDeploySuccess:
    _VALID_PUBKEY = "GAHJJJKMOKYE4RVPZEWZTKH5FVI4PA3VL7GK2LFNUBSGBV73AAUG4HA"

    def test_returns_upload_fee_and_wasm_size(self, client, tmp_path):
        d = str(tmp_path / "inst")
        os.makedirs(d)

        wasm_file = tmp_path / "inst" / "contract.wasm"
        wasm_bytes = b"\x00asm" + b"\x00" * 100
        wasm_file.write_bytes(wasm_bytes)

        m.Session = _session_found(d)
        m._get_stellar_sdk = lambda: (True, None)

        deploy_stub = MagicMock()
        deploy_stub._resolve_wasm_path.return_value = str(wasm_file)

        sim = _sim_response(resource_fee=12000)

        with patch.dict("sys.modules", {"server.routes.soroban_deploy": deploy_stub}), \
             patch("stellar_sdk.Keypair.from_public_key"), \
             patch("stellar_sdk.SorobanServer") as MockServer, \
             patch("stellar_sdk.TransactionBuilder") as MockTxB:

            MockServer.return_value.load_account.return_value = MagicMock()
            MockServer.return_value.simulate_transaction.return_value = sim
            MockTxB.return_value.set_timeout.return_value \
                .append_upload_contract_wasm_op.return_value.build.return_value = MagicMock()

            resp = client.post("/api/soroban/simulate/deploy", json={
                "session_id": 1,
                "wasm_path": "contract.wasm",
                "deployer_public_key": self._VALID_PUBKEY,
            })

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["wasm_size_bytes"] == len(wasm_bytes)
        assert data["upload_fee"]["resource_fee"] == 12000
        assert data["upload_fee"]["total_stroops"] == 12100
        assert data["network"] == "testnet"
        assert "note" in data


# ---------------------------------------------------------------------------
# Unit tests — _decode_sim_response
# ---------------------------------------------------------------------------

class TestDecodeSimResponse:
    def test_extracts_resource_fee(self):
        sim = _sim_response(resource_fee=9999)
        result = m._decode_sim_response(sim)
        assert result["resource_fee"] == 9999

    def test_extracts_cpu_and_mem(self):
        sim = _sim_response(cpu_insns="3000000", mem_bytes="1024000")
        result = m._decode_sim_response(sim)
        assert result["cpu_insns"] == 3000000
        assert result["mem_bytes"] == 1024000

    def test_sim_error_propagated(self):
        sim = _sim_response(error="some error")
        result = m._decode_sim_response(sim)
        assert result["sim_error"] == "some error"

    def test_no_results_means_no_simulated_result(self):
        sim = _sim_response(results=[])
        result = m._decode_sim_response(sim)
        assert result["simulated_result"] is None
        assert result["auth_entries"] == []


# ---------------------------------------------------------------------------
# Unit tests — _parse_param
# ---------------------------------------------------------------------------

class TestParseParam:
    def test_u32(self):
        from stellar_sdk import scval
        assert m._parse_param("u32:42") == scval.to_uint32(42)

    def test_u64(self):
        from stellar_sdk import scval
        assert m._parse_param("u64:99999999") == scval.to_uint64(99999999)

    def test_i32(self):
        from stellar_sdk import scval
        assert m._parse_param("i32:-5") == scval.to_int32(-5)

    def test_bool_true(self):
        from stellar_sdk import scval
        assert m._parse_param("bool:true") == scval.to_bool(True)

    def test_bool_false(self):
        from stellar_sdk import scval
        assert m._parse_param("bool:false") == scval.to_bool(False)

    def test_sym(self):
        from stellar_sdk import scval
        assert m._parse_param("sym:transfer") == scval.to_symbol("transfer")

    def test_str_prefix(self):
        from stellar_sdk import scval
        assert m._parse_param("str:hello") == scval.to_string("hello")

    def test_default_falls_back_to_string(self):
        from stellar_sdk import scval
        assert m._parse_param("plain") == scval.to_string("plain")

    def test_bytes(self):
        from stellar_sdk import scval
        assert m._parse_param("bytes:deadbeef") == scval.to_bytes(bytes.fromhex("deadbeef"))


# ---------------------------------------------------------------------------
# Unit tests — _fee_summary
# ---------------------------------------------------------------------------

class TestFeeSummary:
    def test_total_is_base_plus_resource(self):
        result = m._fee_summary(5000)
        assert result["base_fee"] == 100
        assert result["resource_fee"] == 5000
        assert result["total_stroops"] == 5100

    def test_xlm_conversion(self):
        result = m._fee_summary(0)
        assert result["xlm"] == "0.0000100"

    def test_zero_resource_fee(self):
        result = m._fee_summary(0)
        assert result["total_stroops"] == 100
