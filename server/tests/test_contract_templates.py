"""Tests for server/utils/contract_templates.py and /api/templates routes."""

import pytest
import os
import sys
import functools
from unittest.mock import MagicMock, patch

# Stub deps before import
def _passthrough(f):
    @functools.wraps(f)
    def inner(*args, **kwargs):
        u = MagicMock(); u.id = 1; u.username = "testuser"
        return f(u, *args, **kwargs)
    return inner

_auth_stub = MagicMock()
_auth_stub.token_required = _passthrough
with patch.dict("sys.modules", {
    "server.utils.auth_utils": _auth_stub,
    "server.models": MagicMock(),
    "server.utils.monitoring": MagicMock()
}):
    import server.utils.contract_templates as ct
    import server.routes.template_routes as tr
    template_bp = tr.templates_bp

from flask import Flask


@pytest.fixture
def app():
    a = Flask(__name__)
    a.config["TESTING"] = True
    a.register_blueprint(template_bp)
    return a

@pytest.fixture
def client(app): return app.test_client()

def yes_session(d):
    s = MagicMock(); s.id = 1; s.user_id = 1; s.is_active = True; s.instance_dir = d
    x = MagicMock(); x.query.filter_by.return_value.first.return_value = s
    return x

def no_session():
    x = MagicMock(); x.query.filter_by.return_value.first.return_value = None
    return x


# ── list_templates ────────────────────────────────────────────────────────────

class TestListTemplates:
    def test_returns_4_templates(self):
        templates = ct.list_templates()
        assert len(templates) == 4

    def test_all_have_required_fields(self):
        for t in ct.list_templates():
            assert "id" in t
            assert "name" in t
            assert "description" in t
            assert "difficulty" in t
            assert "tags" in t

    def test_includes_expected_ids(self):
        ids = [t["id"] for t in ct.list_templates()]
        assert "hello_world" in ids
        assert "token" in ids
        assert "nft" in ids
        assert "governance" in ids


# ── get_template ──────────────────────────────────────────────────────────────

class TestGetTemplate:
    def test_returns_template_for_valid_id(self):
        t = ct.get_template("hello_world")
        assert t is not None
        assert t["id"] == "hello_world"

    def test_returns_none_for_invalid_id(self):
        assert ct.get_template("nonexistent") is None

    def test_all_templates_retrievable(self):
        for t in ct.list_templates():
            result = ct.get_template(t["id"])
            assert result is not None


# ── generate_template ─────────────────────────────────────────────────────────

class TestGenerateTemplate:
    def test_generates_hello_world(self, tmp_path):
        target = str(tmp_path / "my_hello")
        result = ct.generate_template("hello_world", target)
        assert result["success"] is True
        assert os.path.isfile(os.path.join(target, "Cargo.toml"))
        assert os.path.isfile(os.path.join(target, "src", "lib.rs"))
        assert os.path.isfile(os.path.join(target, "README.md"))

    def test_generates_all_templates(self, tmp_path):
        for t in ct.list_templates():
            target = str(tmp_path / t["id"])
            result = ct.generate_template(t["id"], target)
            assert result["success"] is True

    def test_cargo_toml_has_package_name(self, tmp_path):
        target = str(tmp_path / "my_token")
        ct.generate_template("token", target, project_name="my_token")
        content = open(os.path.join(target, "Cargo.toml")).read()
        assert 'name = "my_token"' in content

    def test_lib_rs_has_soroban_sdk(self, tmp_path):
        target = str(tmp_path / "my_nft")
        ct.generate_template("nft", target)
        content = open(os.path.join(target, "src", "lib.rs")).read()
        assert "soroban_sdk" in content

    def test_readme_mentions_template_name(self, tmp_path):
        target = str(tmp_path / "my_gov")
        ct.generate_template("governance", target)
        content = open(os.path.join(target, "README.md")).read()
        assert "DAO Governance" in content or "Governance" in content

    def test_raises_for_unknown_template(self, tmp_path):
        with pytest.raises(ValueError, match="Unknown template"):
            ct.generate_template("unknown_template", str(tmp_path / "x"))

    def test_raises_if_path_exists(self, tmp_path):
        target = str(tmp_path / "existing")
        os.makedirs(target)
        with pytest.raises(ValueError, match="already exists"):
            ct.generate_template("hello_world", target)

    def test_files_created_list(self, tmp_path):
        target = str(tmp_path / "my_project")
        result = ct.generate_template("token", target)
        assert "Cargo.toml" in result["files_created"]
        assert "src/lib.rs" in result["files_created"]
        assert "README.md" in result["files_created"]


# ── GET /api/templates ────────────────────────────────────────────────────────

class TestListTemplatesRoute:
    def test_returns_200(self, client):
        resp = client.get("/api/templates")
        assert resp.status_code == 200

    def test_returns_4_templates(self, client):
        data = client.get("/api/templates").get_json()
        assert data["success"] is True
        assert data["total"] == 4

    def test_template_has_required_fields(self, client):
        data = client.get("/api/templates").get_json()
        for t in data["templates"]:
            assert "id" in t
            assert "name" in t
            assert "difficulty" in t


# ── GET /api/templates/<id> ───────────────────────────────────────────────────

class TestGetTemplateRoute:
    def test_returns_200_for_valid_id(self, client):
        resp = client.get("/api/templates/hello_world")
        assert resp.status_code == 200

    def test_returns_404_for_unknown_id(self, client):
        resp = client.get("/api/templates/nonexistent")
        assert resp.status_code == 404

    def test_returns_available_list_on_404(self, client):
        data = client.get("/api/templates/nonexistent").get_json()
        assert "available" in data


# ── POST /api/templates/generate ─────────────────────────────────────────────

class TestGenerateRoute:
    def test_missing_session_id(self, client):
        resp = client.post("/api/templates/generate", json={"template_id": "hello_world", "project_name": "x"})
        assert resp.status_code == 400
        assert b"session_id" in resp.data

    def test_missing_template_id(self, client):
        resp = client.post("/api/templates/generate", json={"session_id": 1, "project_name": "x"})
        assert resp.status_code == 400
        assert b"template_id" in resp.data

    def test_missing_project_name(self, client):
        resp = client.post("/api/templates/generate", json={"session_id": 1, "template_id": "hello_world"})
        assert resp.status_code == 400
        assert b"project_name" in resp.data

    def test_session_not_found(self, client):
        tr.Session = no_session()
        resp = client.post("/api/templates/generate", json={
            "session_id": 99, "template_id": "hello_world", "project_name": "x"
        })
        assert resp.status_code == 404

    def test_path_traversal_blocked(self, client, tmp_path):
        d = str(tmp_path / "inst"); os.makedirs(d)
        tr.Session = yes_session(d)
        resp = client.post("/api/templates/generate", json={
            "session_id": 1, "template_id": "hello_world", "project_name": "../../etc"
        })
        # Either caught by project_name regex validation (400) or path traversal check (400)
        assert resp.status_code == 400

    def test_invalid_project_name_starts_with_digit(self, client, tmp_path):
        d = str(tmp_path / "inst"); os.makedirs(d)
        tr.Session = yes_session(d)
        resp = client.post("/api/templates/generate", json={
            "session_id": 1, "template_id": "hello_world", "project_name": "1invalid"
        })
        assert resp.status_code == 400

    def test_unknown_template_returns_404(self, client, tmp_path):
        d = str(tmp_path / "inst"); os.makedirs(d)
        tr.Session = yes_session(d)
        resp = client.post("/api/templates/generate", json={
            "session_id": 1, "template_id": "nonexistent", "project_name": "myproject"
        })
        assert resp.status_code == 404

    def test_successful_generation(self, client, tmp_path):
        d = str(tmp_path / "inst"); os.makedirs(d)
        tr.Session = yes_session(d)
        resp = client.post("/api/templates/generate", json={
            "session_id": 1, "template_id": "hello_world", "project_name": "myproject"
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["success"] is True
        assert data["template_id"] == "hello_world"
        assert "files_created" in data
        assert os.path.isfile(os.path.join(d, "myproject", "Cargo.toml"))
