"""Tests for server/routes/file_routes.py — autosave & file persistence"""

import os
import sys
import functools
from unittest.mock import MagicMock

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

import server.routes.file_routes as m
files_bp = m.files_bp

for mod in ["server.utils.auth_utils", "server.models", "server.utils.monitoring"]:
    sys.modules.pop(mod, None)

import pytest
from flask import Flask


@pytest.fixture
def app():
    a = Flask(__name__)
    a.config["TESTING"] = True
    a.register_blueprint(files_bp)
    return a

@pytest.fixture
def client(app): return app.test_client()

def yes_session(instance_dir):
    s = MagicMock(); s.id = 1; s.user_id = 1; s.is_active = True
    s.instance_dir = instance_dir
    x = MagicMock(); x.query.filter_by.return_value.first.return_value = s
    return x

def no_session():
    x = MagicMock(); x.query.filter_by.return_value.first.return_value = None
    return x

def bad_workspace():
    s = MagicMock(); s.id = 1; s.user_id = 1; s.is_active = True
    s.instance_dir = "/nonexistent/path"
    x = MagicMock(); x.query.filter_by.return_value.first.return_value = s
    return x


# ── _safe_path ────────────────────────────────────────────────────────────────

class TestSafePath:
    def test_valid_relative_path(self, tmp_path):
        result = m._safe_path("src/main.rs", str(tmp_path))
        assert result == str(tmp_path / "src" / "main.rs")

    def test_blocks_parent_traversal(self, tmp_path):
        result = m._safe_path("../../etc/passwd", str(tmp_path))
        assert result is None

    def test_blocks_absolute_path(self, tmp_path):
        result = m._safe_path("/etc/passwd", str(tmp_path))
        # os.path.join with absolute path replaces base — safe_path should catch it
        assert result is None or not result.startswith(str(tmp_path))

    def test_nested_path_valid(self, tmp_path):
        result = m._safe_path("a/b/c/file.txt", str(tmp_path))
        assert result is not None
        assert result.startswith(str(tmp_path))


# ── _validate_filename ────────────────────────────────────────────────────────

class TestValidateFilename:
    def test_valid_filename(self):
        assert m._validate_filename("src/lib.rs") is True

    def test_blocks_null_byte(self):
        assert m._validate_filename("file\x00name") is False

    def test_blocks_absolute_path(self):
        assert m._validate_filename("/etc/passwd") is False

    def test_blocks_hidden_root(self):
        assert m._validate_filename(".env") is False

    def test_allows_nested_hidden(self):
        # Files in non-root hidden dirs are allowed (e.g. src/.gitkeep)
        assert m._validate_filename("src/.gitkeep") is True


# ── POST /api/files/save ──────────────────────────────────────────────────────

class TestSaveFile:
    def test_missing_session_id(self, client):
        resp = client.post("/api/files/save", json={"path": "x.txt", "content": "hi"})
        assert resp.status_code == 400

    def test_missing_path(self, client):
        resp = client.post("/api/files/save", json={"session_id": 1, "content": "hi"})
        assert resp.status_code == 400

    def test_no_json_body(self, client):
        resp = client.post("/api/files/save")
        assert resp.status_code == 400

    def test_session_not_found(self, client):
        m.Session = no_session()
        resp = client.post("/api/files/save", json={"session_id": 99, "path": "x.txt", "content": "hi"})
        assert resp.status_code == 404

    def test_path_traversal_blocked(self, client, tmp_path):
        m.Session = yes_session(str(tmp_path))
        resp = client.post("/api/files/save", json={
            "session_id": 1, "path": "../../etc/passwd", "content": "evil"
        })
        assert resp.status_code == 400

    def test_blocked_extension(self, client, tmp_path):
        m.Session = yes_session(str(tmp_path))
        resp = client.post("/api/files/save", json={
            "session_id": 1, "path": "malware.exe", "content": "x"
        })
        assert resp.status_code == 400

    def test_saves_file_successfully(self, client, tmp_path):
        m.Session = yes_session(str(tmp_path))
        resp = client.post("/api/files/save", json={
            "session_id": 1, "path": "hello.txt", "content": "Hello World"
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["created"] is True
        assert (tmp_path / "hello.txt").read_text() == "Hello World"

    def test_overwrites_existing_file(self, client, tmp_path):
        (tmp_path / "existing.txt").write_text("old content")
        m.Session = yes_session(str(tmp_path))
        resp = client.post("/api/files/save", json={
            "session_id": 1, "path": "existing.txt", "content": "new content"
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["created"] is False
        assert (tmp_path / "existing.txt").read_text() == "new content"

    def test_creates_parent_directories(self, client, tmp_path):
        m.Session = yes_session(str(tmp_path))
        resp = client.post("/api/files/save", json={
            "session_id": 1, "path": "src/contracts/lib.rs", "content": "// code"
        })
        assert resp.status_code == 200
        assert (tmp_path / "src" / "contracts" / "lib.rs").exists()

    def test_returns_file_size(self, client, tmp_path):
        m.Session = yes_session(str(tmp_path))
        resp = client.post("/api/files/save", json={
            "session_id": 1, "path": "size.txt", "content": "hello"
        })
        data = resp.get_json()
        assert data["size"] == 5


# ── GET /api/files/load ───────────────────────────────────────────────────────

class TestLoadFile:
    def test_missing_session_id(self, client):
        resp = client.get("/api/files/load?path=x.txt")
        assert resp.status_code == 400

    def test_missing_path(self, client):
        resp = client.get("/api/files/load?session_id=1")
        assert resp.status_code == 400

    def test_session_not_found(self, client):
        m.Session = no_session()
        resp = client.get("/api/files/load?session_id=99&path=x.txt")
        assert resp.status_code == 404

    def test_file_not_found(self, client, tmp_path):
        m.Session = yes_session(str(tmp_path))
        resp = client.get("/api/files/load?session_id=1&path=nonexistent.txt")
        assert resp.status_code == 404

    def test_path_traversal_blocked(self, client, tmp_path):
        m.Session = yes_session(str(tmp_path))
        resp = client.get("/api/files/load?session_id=1&path=../../etc/passwd")
        assert resp.status_code == 400

    def test_loads_file_successfully(self, client, tmp_path):
        (tmp_path / "hello.txt").write_text("Hello World")
        m.Session = yes_session(str(tmp_path))
        resp = client.get("/api/files/load?session_id=1&path=hello.txt")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["content"] == "Hello World"
        assert data["size"] == 11


# ── GET /api/files/list ───────────────────────────────────────────────────────

class TestListFiles:
    def test_missing_session_id(self, client):
        resp = client.get("/api/files/list")
        assert resp.status_code == 400

    def test_session_not_found(self, client):
        m.Session = no_session()
        resp = client.get("/api/files/list?session_id=99")
        assert resp.status_code == 404

    def test_lists_files(self, client, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        m.Session = yes_session(str(tmp_path))
        resp = client.get("/api/files/list?session_id=1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        paths = [f["path"] for f in data["files"]]
        assert "a.txt" in paths
        assert "b.txt" in paths

    def test_excludes_hidden_files(self, client, tmp_path):
        (tmp_path / ".env").write_text("SECRET=x")
        (tmp_path / "visible.txt").write_text("ok")
        m.Session = yes_session(str(tmp_path))
        resp = client.get("/api/files/list?session_id=1")
        data = resp.get_json()
        paths = [f["path"] for f in data["files"]]
        assert ".env" not in paths
        assert "visible.txt" in paths

    def test_returns_total_count(self, client, tmp_path):
        (tmp_path / "x.txt").write_text("x")
        m.Session = yes_session(str(tmp_path))
        resp = client.get("/api/files/list?session_id=1")
        data = resp.get_json()
        assert "total" in data


# ── DELETE /api/files/delete ──────────────────────────────────────────────────

class TestDeleteFile:
    def test_missing_session_id(self, client):
        resp = client.delete("/api/files/delete", json={"path": "x.txt"})
        assert resp.status_code == 400

    def test_file_not_found(self, client, tmp_path):
        m.Session = yes_session(str(tmp_path))
        resp = client.delete("/api/files/delete", json={"session_id": 1, "path": "nope.txt"})
        assert resp.status_code == 404

    def test_deletes_file(self, client, tmp_path):
        (tmp_path / "del.txt").write_text("bye")
        m.Session = yes_session(str(tmp_path))
        resp = client.delete("/api/files/delete", json={"session_id": 1, "path": "del.txt"})
        assert resp.status_code == 200
        assert not (tmp_path / "del.txt").exists()

    def test_path_traversal_blocked(self, client, tmp_path):
        m.Session = yes_session(str(tmp_path))
        resp = client.delete("/api/files/delete", json={"session_id": 1, "path": "../../etc/hosts"})
        assert resp.status_code == 400


# ── POST /api/files/mkdir ─────────────────────────────────────────────────────

class TestMkdir:
    def test_missing_session_id(self, client):
        resp = client.post("/api/files/mkdir", json={"path": "src"})
        assert resp.status_code == 400

    def test_creates_directory(self, client, tmp_path):
        m.Session = yes_session(str(tmp_path))
        resp = client.post("/api/files/mkdir", json={"session_id": 1, "path": "src/contracts"})
        assert resp.status_code == 200
        assert (tmp_path / "src" / "contracts").is_dir()

    def test_idempotent_existing_dir(self, client, tmp_path):
        (tmp_path / "existing").mkdir()
        m.Session = yes_session(str(tmp_path))
        resp = client.post("/api/files/mkdir", json={"session_id": 1, "path": "existing"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["created"] is False
