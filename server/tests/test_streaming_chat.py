"""Tests for server/routes/streaming_chat_routes.py"""
import json
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
sys.modules["server.middleware.database"] = MagicMock()
sys.modules["server.utils.db_utils"] = MagicMock()
sys.modules["server.utils.monitoring"] = MagicMock()

import server.routes.streaming_chat_routes as m
streaming_bp = m.streaming_chat_bp

for mod in ["server.utils.auth_utils","server.models","server.middleware.database",
            "server.utils.db_utils","server.utils.monitoring"]:
    sys.modules.pop(mod, None)

import pytest
from flask import Flask


@pytest.fixture
def app():
    a = Flask(__name__)
    a.config["TESTING"] = True
    a.register_blueprint(streaming_bp)
    return a

@pytest.fixture
def client(app): return app.test_client()

def yes_session(d=None):
    s = MagicMock(); s.id=1; s.user_id=1; s.is_active=True
    x = MagicMock(); x.query.filter_by.return_value.first.return_value = s
    return x

def no_session():
    x = MagicMock(); x.query.filter_by.return_value.first.return_value = None
    return x


# ── SSE helper ────────────────────────────────────────────────────────────────

class TestSseHelper:
    def test_sse_bytes_returns_bytes(self):
        result = m._sse_bytes("token", {"text": "hello"})
        assert isinstance(result, bytes)

    def test_sse_bytes_contains_event_type(self):
        result = m._sse_bytes("stream_start", {"stream_id": "abc"}).decode()
        data = json.loads(result.replace("data: ", "").strip())
        assert data["type"] == "stream_start"
        assert data["stream_id"] == "abc"

    def test_sse_format_ends_with_double_newline(self):
        result = m._sse("token", {"text": "hi"})
        assert result.endswith("\n\n")


# ── Stream registry ───────────────────────────────────────────────────────────

class TestStreamRegistry:
    def test_register_returns_event(self):
        import threading
        event = m._register_stream("test-id-1")
        assert isinstance(event, threading.Event)
        m._deregister_stream("test-id-1")

    def test_deregister_removes_stream(self):
        m._register_stream("test-id-2")
        m._deregister_stream("test-id-2")
        with m._streams_lock:
            assert "test-id-2" not in m._active_streams

    def test_deregister_nonexistent_is_safe(self):
        m._deregister_stream("nonexistent-id")  # Should not raise


# ── POST /api/chat/stream ─────────────────────────────────────────────────────

class TestStreamRoute:
    def test_missing_session_id(self, client):
        resp = client.post("/api/chat/stream", json={"message": "hello"})
        assert resp.status_code == 400

    def test_missing_message(self, client):
        resp = client.post("/api/chat/stream", json={"session_id": 1})
        assert resp.status_code == 400

    def test_empty_message(self, client):
        resp = client.post("/api/chat/stream", json={"session_id": 1, "message": "  "})
        assert resp.status_code == 400

    def test_no_json_body(self, client):
        resp = client.post("/api/chat/stream")
        assert resp.status_code == 400

    def test_session_not_found(self, client):
        m.Session = no_session()
        resp = client.post("/api/chat/stream", json={
            "session_id": 99, "message": "hello"
        })
        assert resp.status_code == 404

    def test_successful_stream_returns_event_stream(self, client, tmp_path):
        m.Session = yes_session()
        m.add_chat_message = MagicMock()

        mock_chunk = MagicMock()
        mock_chunk.text = "Hello world"
        mock_response = MagicMock()
        mock_response.__iter__ = MagicMock(return_value=iter([mock_chunk]))

        mock_chat = MagicMock()
        mock_chat.send_message.return_value = mock_response

        mock_model = MagicMock()
        mock_model.start_chat.return_value = mock_chat

        with patch.dict("sys.modules", {
            "google.generativeai": MagicMock(
                GenerativeModel=MagicMock(return_value=mock_model),
                configure=MagicMock(),
            )
        }), patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            resp = client.post("/api/chat/stream", json={
                "session_id": 1,
                "message": "Hello",
                "history": [],
            })

        assert resp.status_code == 200
        assert "text/event-stream" in resp.content_type

    def test_stream_response_has_no_cache_headers(self, client):
        m.Session = yes_session()
        m.add_chat_message = MagicMock()

        mock_response = MagicMock()
        mock_response.__iter__ = MagicMock(return_value=iter([]))
        mock_chat = MagicMock()
        mock_chat.send_message.return_value = mock_response
        mock_model = MagicMock()
        mock_model.start_chat.return_value = mock_chat

        with patch.dict("sys.modules", {
            "google.generativeai": MagicMock(
                GenerativeModel=MagicMock(return_value=mock_model),
                configure=MagicMock(),
            )
        }), patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            resp = client.post("/api/chat/stream", json={
                "session_id": 1,
                "message": "Hello",
            })

        assert resp.status_code == 200
        assert "no-cache" in resp.headers.get("Cache-Control", "")


# ── POST /api/chat/stream/stop ────────────────────────────────────────────────

class TestStopStreamRoute:
    def test_missing_stream_id(self, client):
        resp = client.post("/api/chat/stream/stop", json={})
        assert resp.status_code == 400

    def test_stop_nonexistent_stream(self, client):
        resp = client.post("/api/chat/stream/stop", json={"stream_id": "nonexistent"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["stopped"] is False

    def test_stop_active_stream(self, client):
        event = m._register_stream("test-stop-id")
        resp = client.post("/api/chat/stream/stop", json={"stream_id": "test-stop-id"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["stopped"] is True
        assert event.is_set()


# ── GET /api/chat/stream/active ───────────────────────────────────────────────

class TestActiveStreamsRoute:
    def test_returns_active_streams(self, client):
        m._register_stream("active-test-1")
        resp = client.get("/api/chat/stream/active")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "active_streams" in data
        m._deregister_stream("active-test-1")

    def test_returns_count(self, client):
        resp = client.get("/api/chat/stream/active")
        data = resp.get_json()
        assert "count" in data
        assert isinstance(data["count"], int)
