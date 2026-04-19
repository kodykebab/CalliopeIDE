"""Tests for server/utils/logging_config.py"""

import json
import logging
import sys
import time
from unittest.mock import MagicMock, patch

# Stub deps
sys.modules["server.utils.monitoring"] = MagicMock()

import server.utils.logging_config as lc

for mod in ["server.utils.monitoring"]:
    sys.modules.pop(mod, None)

import pytest
from flask import Flask


@pytest.fixture
def app():
    a = Flask(__name__)
    a.config["TESTING"] = True
    lc.register_request_logging(a)
    return a

@pytest.fixture
def client(app): return app.test_client()


# ── get/set request_id ────────────────────────────────────────────────────────

class TestRequestId:
    def test_default_is_empty_string(self):
        assert lc.get_request_id() == ""

    def test_set_and_get(self):
        lc.set_request_id("test-id-123")
        assert lc.get_request_id() == "test-id-123"
        lc.set_request_id("")  # reset

    def test_set_uuid(self):
        import uuid
        rid = str(uuid.uuid4())
        lc.set_request_id(rid)
        assert lc.get_request_id() == rid
        lc.set_request_id("")  # reset


# ── JsonFormatter ─────────────────────────────────────────────────────────────

class TestJsonFormatter:
    @pytest.fixture
    def formatter(self):
        return lc.JsonFormatter()

    @pytest.fixture
    def record(self):
        return logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Hello world",
            args=(),
            exc_info=None,
        )

    def test_output_is_valid_json(self, formatter, record):
        output = formatter.format(record)
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_contains_required_fields(self, formatter, record):
        data = json.loads(formatter.format(record))
        assert "timestamp" in data
        assert "level" in data
        assert "logger" in data
        assert "message" in data
        assert "request_id" in data

    def test_message_content(self, formatter, record):
        data = json.loads(formatter.format(record))
        assert data["message"] == "Hello world"

    def test_level_is_info(self, formatter, record):
        data = json.loads(formatter.format(record))
        assert data["level"] == "INFO"

    def test_logger_name(self, formatter, record):
        data = json.loads(formatter.format(record))
        assert data["logger"] == "test.logger"

    def test_timestamp_is_iso_format(self, formatter, record):
        data = json.loads(formatter.format(record))
        # Should be parseable as ISO datetime
        from datetime import datetime
        dt = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        assert dt is not None

    def test_includes_request_id_when_set(self, formatter, record):
        lc.set_request_id("req-abc-123")
        data = json.loads(formatter.format(record))
        assert data["request_id"] == "req-abc-123"
        lc.set_request_id("")

    def test_extra_fields_included(self, formatter):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test", args=(), exc_info=None,
        )
        record.user_id = 42
        record.duration_ms = 150.5
        data = json.loads(formatter.format(record))
        assert data["user_id"] == 42
        assert data["duration_ms"] == 150.5

    def test_exception_info_included(self, formatter):
        try:
            raise ValueError("test error")
        except ValueError:
            record = logging.LogRecord(
                name="test", level=logging.ERROR, pathname="", lineno=0,
                msg="error occurred", args=(), exc_info=sys.exc_info(),
            )
        data = json.loads(formatter.format(record))
        assert "exception" in data
        assert "ValueError" in data["exception"]

    def test_single_line_output(self, formatter, record):
        output = formatter.format(record)
        assert "\n" not in output


# ── configure_logging ─────────────────────────────────────────────────────────

class TestConfigureLogging:
    def test_sets_root_level_to_info(self):
        lc.configure_logging(level="INFO", json_output=False)
        assert logging.getLogger().level == logging.INFO

    def test_sets_root_level_to_debug(self):
        lc.configure_logging(level="DEBUG", json_output=False)
        assert logging.getLogger().level == logging.DEBUG
        lc.configure_logging(level="INFO", json_output=False)  # reset

    def test_json_output_uses_json_formatter(self):
        lc.configure_logging(level="INFO", json_output=True)
        root = logging.getLogger()
        assert any(isinstance(h.formatter, lc.JsonFormatter) for h in root.handlers)

    def test_plain_output_uses_plain_formatter(self):
        lc.configure_logging(level="INFO", json_output=False)
        root = logging.getLogger()
        assert not any(isinstance(h.formatter, lc.JsonFormatter) for h in root.handlers)


# ── Flask middleware ──────────────────────────────────────────────────────────

class TestRequestLoggingMiddleware:
    def test_response_has_request_id_header(self, app, client):
        @app.route("/test-header")
        def test_view():
            return "ok"
        resp = client.get("/test-header")
        assert "X-Request-ID" in resp.headers

    def test_request_id_header_is_uuid(self, app, client):
        @app.route("/test-uuid")
        def test_view2():
            return "ok"
        resp = client.get("/test-uuid")
        rid = resp.headers.get("X-Request-ID", "")
        assert len(rid) == 36  # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

    def test_custom_request_id_propagated(self, app, client):
        @app.route("/test-custom-id")
        def test_view3():
            return "ok"
        resp = client.get("/test-custom-id", headers={"X-Request-ID": "my-custom-id"})
        assert resp.headers.get("X-Request-ID") == "my-custom-id"

    def test_returns_200_for_valid_request(self, app, client):
        @app.route("/test-200")
        def test_view4():
            return "ok", 200
        resp = client.get("/test-200")
        assert resp.status_code == 200
