"""Tests for server/utils/soroban_prompts.py and /api/prompts/soroban routes"""

import sys
import functools
from unittest.mock import MagicMock, patch

# Stub deps
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
sys.modules["server.utils.db_utils"] = MagicMock()

import server.utils.soroban_prompts as sp
import server.routes.soroban_prompt_routes as r
prompts_bp = r.soroban_prompts_bp

for mod in ["server.utils.auth_utils","server.models","server.utils.monitoring","server.utils.db_utils"]:
    sys.modules.pop(mod, None)

import pytest
from flask import Flask


@pytest.fixture
def app():
    a = Flask(__name__)
    a.config["TESTING"] = True
    a.register_blueprint(prompts_bp)
    return a

@pytest.fixture
def client(app): return app.test_client()

def yes_session():
    s = MagicMock(); s.id=1; s.user_id=1; s.is_active=True
    x = MagicMock(); x.query.filter_by.return_value.first.return_value = s
    return x

def no_session():
    x = MagicMock(); x.query.filter_by.return_value.first.return_value = None
    return x


# ── list_prompt_templates ─────────────────────────────────────────────────────

class TestListPromptTemplates:
    def test_returns_4_templates(self):
        templates = sp.list_prompt_templates()
        assert len(templates) == 4

    def test_all_have_required_fields(self):
        for t in sp.list_prompt_templates():
            assert "id" in t
            assert "name" in t
            assert "description" in t
            assert "category" in t
            assert "requires_code" in t
            assert "placeholder" in t

    def test_includes_all_prompt_ids(self):
        ids = [t["id"] for t in sp.list_prompt_templates()]
        assert "generate_contract" in ids
        assert "explain_contract" in ids
        assert "generate_tests" in ids
        assert "security_review" in ids


# ── get_prompt_template ───────────────────────────────────────────────────────

class TestGetPromptTemplate:
    def test_returns_template_for_valid_id(self):
        t = sp.get_prompt_template("generate_contract")
        assert t is not None
        assert t["id"] == "generate_contract"

    def test_returns_none_for_invalid_id(self):
        assert sp.get_prompt_template("nonexistent") is None

    def test_generate_contract_does_not_require_code(self):
        t = sp.get_prompt_template("generate_contract")
        assert t["requires_code"] is False

    def test_explain_contract_requires_code(self):
        t = sp.get_prompt_template("explain_contract")
        assert t["requires_code"] is True

    def test_security_review_requires_code(self):
        t = sp.get_prompt_template("security_review")
        assert t["requires_code"] is True


# ── build_soroban_prompt ──────────────────────────────────────────────────────

class TestBuildSorobanPrompt:
    def test_generate_contract_contains_description(self):
        prompt = sp.build_soroban_prompt("generate_contract", "A vesting contract")
        assert "A vesting contract" in prompt

    def test_generate_contract_mentions_soroban(self):
        prompt = sp.build_soroban_prompt("generate_contract", "token contract")
        assert "Soroban" in prompt or "soroban" in prompt

    def test_explain_contract_includes_code(self):
        code = "pub struct MyContract;"
        prompt = sp.build_soroban_prompt("explain_contract", "", code)
        assert code in prompt

    def test_generate_tests_mentions_test_suite(self):
        prompt = sp.build_soroban_prompt("generate_tests", "my contract", "// code")
        assert "test" in prompt.lower()

    def test_security_review_mentions_audit(self):
        prompt = sp.build_soroban_prompt("security_review", "", "// code")
        assert "security" in prompt.lower() or "audit" in prompt.lower()

    def test_raises_for_unknown_prompt_id(self):
        with pytest.raises(ValueError, match="Unknown prompt"):
            sp.build_soroban_prompt("nonexistent", "desc")

    def test_prompt_is_non_empty(self):
        for pid in ["generate_contract", "explain_contract", "generate_tests", "security_review"]:
            prompt = sp.build_soroban_prompt(pid, "test description", "// code")
            assert len(prompt) > 100


# ── GET /api/prompts/soroban ──────────────────────────────────────────────────

class TestListPromptsRoute:
    def test_returns_200(self, client):
        resp = client.get("/api/prompts/soroban")
        assert resp.status_code == 200

    def test_returns_4_prompts(self, client):
        data = client.get("/api/prompts/soroban").get_json()
        assert data["success"] is True
        assert data["total"] == 4

    def test_prompt_has_required_fields(self, client):
        data = client.get("/api/prompts/soroban").get_json()
        for p in data["prompts"]:
            assert "id" in p
            assert "name" in p
            assert "category" in p


# ── GET /api/prompts/soroban/<id> ─────────────────────────────────────────────

class TestGetPromptRoute:
    def test_returns_200_for_valid_id(self, client):
        resp = client.get("/api/prompts/soroban/generate_contract")
        assert resp.status_code == 200

    def test_returns_404_for_unknown_id(self, client):
        resp = client.get("/api/prompts/soroban/nonexistent")
        assert resp.status_code == 404

    def test_returns_available_list_on_404(self, client):
        data = client.get("/api/prompts/soroban/nonexistent").get_json()
        assert "available" in data


# ── POST /api/prompts/soroban/build ──────────────────────────────────────────

class TestBuildPromptRoute:
    def test_missing_prompt_id(self, client):
        resp = client.post("/api/prompts/soroban/build", json={"description": "hi"})
        assert resp.status_code == 400

    def test_unknown_prompt_id(self, client):
        resp = client.post("/api/prompts/soroban/build", json={"prompt_id": "bad"})
        assert resp.status_code == 404

    def test_requires_code_without_code_or_desc(self, client):
        resp = client.post("/api/prompts/soroban/build", json={
            "prompt_id": "explain_contract"
        })
        assert resp.status_code == 400

    def test_builds_prompt_successfully(self, client):
        resp = client.post("/api/prompts/soroban/build", json={
            "prompt_id": "generate_contract",
            "description": "A simple counter contract",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "prompt_text" in data
        assert "A simple counter contract" in data["prompt_text"]
        assert "char_count" in data

    def test_includes_context_code_in_prompt(self, client):
        resp = client.post("/api/prompts/soroban/build", json={
            "prompt_id": "explain_contract",
            "description": "explain this",
            "context_code": "pub struct MyContract;",
        })
        data = resp.get_json()
        assert "pub struct MyContract;" in data["prompt_text"]


# ── POST /api/prompts/soroban/execute ─────────────────────────────────────────

class TestExecutePromptRoute:
    def test_missing_session_id(self, client):
        resp = client.post("/api/prompts/soroban/execute", json={
            "prompt_id": "generate_contract", "description": "hi"
        })
        assert resp.status_code == 400

    def test_missing_prompt_id(self, client):
        resp = client.post("/api/prompts/soroban/execute", json={
            "session_id": 1, "description": "hi"
        })
        assert resp.status_code == 400

    def test_session_not_found(self, client):
        r.Session = no_session()
        resp = client.post("/api/prompts/soroban/execute", json={
            "session_id": 99, "prompt_id": "generate_contract", "description": "hi"
        })
        assert resp.status_code == 404

    def test_unknown_prompt_returns_404(self, client):
        r.Session = yes_session()
        resp = client.post("/api/prompts/soroban/execute", json={
            "session_id": 1, "prompt_id": "nonexistent", "description": "hi"
        })
        assert resp.status_code == 404

    def test_successful_execution(self, client):
        r.Session = yes_session()
        r.add_chat_message = MagicMock()

        mock_response = MagicMock()
        mock_response.text = "Generated contract code here"
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response

        with patch.dict("sys.modules", {
            "google.generativeai": MagicMock(
                GenerativeModel=MagicMock(return_value=mock_model),
                configure=MagicMock(),
            )
        }), patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            resp = client.post("/api/prompts/soroban/execute", json={
                "session_id": 1,
                "prompt_id": "generate_contract",
                "description": "A simple counter contract",
            })

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["result"] == "Generated contract code here"
        assert data["prompt_id"] == "generate_contract"
