"""Tests for server/utils/structured_logging.py"""

import json
import logging
import pytest
import sys
from unittest.mock import MagicMock, patch

# Stub server deps before import
for mod in ["server.utils.auth_utils", "server.models", "server.utils.monitoring"]:
    sys.modules.setdefault(mod, MagicMock())

from server.utils.structured_logging import (
    JSONFormatter,
    get_logger,
    get_request_id,
    setup_logging,
    init_request_logging,
    _request_id,
)

for mod in ["server.utils.auth_utils", "server.models", "server.utils.monitoring"]:
    sys.modules.pop(mod, None)

from flask import Flask


# ── JSONFormatter ─────────────────────────────────────────────────────────────

class TestJSONFormatter:
    def _make_record(self, msg="test", level=logging.INFO, **extra):
        record = logging.LogRecord(
            name="test", level=level, pathname="", lineno=0,
            msg=msg, args=(), exc_info=None,
        )
        for k, v in extra.items():
            setattr(record, k, v)
        return record

    def test_output_is_valid_json(self):
        formatter = JSONFormatter()
        record = self._make_record("hello world")
        output = formatter.format(record)
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_required_fields_present(self):
        formatter = JSONFormatter()
        record = self._make_record("test message")
        data = json.loads(formatter.format(record))
        assert "timestamp" in data
        assert "level" in data
        assert "logger" in data
        assert "message" in data
        assert data["message"] == "test message"
        assert data["level"] == "INFO"

    def test_extra_fields_included(self):
        formatter = JSONFormatter()
        record = self._make_record("msg", event="request_started", status_code=200)
        data = json.loads(formatter.format(record))
        assert data["event"] == "request_started"
        assert data["status_code"] == 200

    def test_request_id_included_when_set(self):
        formatter = JSONFormatter()
        token = _request_id.set("test-req-id-123")
        try:
            record = self._make_record("msg")
            data = json.loads(formatter.format(record))
            assert data["request_id"] == "test-req-id-123"
        finally:
            _request_id.reset(token)

    def test_request_id_omitted_when_not_set(self):
        formatter = JSONFormatter()
        _request_id.set("")
        record = self._make_record("msg")
        data = json.loads(formatter.format(record))
        assert "request_id" not in data

    def test_exception_info_included(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        record = self._make_record("error msg")
        record.exc_info = exc_info
        data = json.loads(formatter.format(record))
        assert "exception" in data
        assert "ValueError" in data["exception"]

    def test_log_levels(self):
        formatter = JSONFormatter()
        for level_name, level in [("DEBUG", logging.DEBUG), ("WARNING", logging.WARNING), ("ERROR", logging.ERROR)]:
            record = self._make_record("msg", level=level)
            data = json.loads(formatter.format(record))
            assert data["level"] == level_name


# ── get_logger ────────────────────────────────────────────────────────────────

class TestGetLogger:
    def test_returns_logger(self):
        logger = get_logger("test.module.a")
        assert isinstance(logger, logging.Logger)

    def test_has_json_formatter(self):
        logger = get_logger("test.module.b")
        assert any(isinstance(h.formatter, JSONFormatter) for h in logger.handlers)

    def test_no_duplicate_handlers(self):
        logger = get_logger("test.module.c")
        handler_count = len(logger.handlers)
        get_logger("test.module.c")  # Call again
        assert len(logger.handlers) == handler_count

    def test_does_not_propagate(self):
        logger = get_logger("test.module.d")
        assert logger.propagate is False


# ── get_request_id ────────────────────────────────────────────────────────────

class TestGetRequestId:
    def test_returns_empty_outside_request(self):
        _request_id.set("")
        assert get_request_id() == ""

    def test_returns_set_value(self):
        token = _request_id.set("my-request-id")
        try:
            assert get_request_id() == "my-request-id"
        finally:
            _request_id.reset(token)


# ── init_request_logging ──────────────────────────────────────────────────────

class TestInitRequestLogging:
    @pytest.fixture
    def app(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        init_request_logging(app)
        return app

    @pytest.fixture
    def client(self, app):
        @app.route("/test")
        def test_route():
            from flask import jsonify
            return jsonify({"ok": True})
        return app.test_client()

    def test_request_id_header_added(self, client):
        resp = client.get("/test")
        assert "X-Request-ID" in resp.headers

    def test_request_id_is_uuid_format(self, client):
        import re
        resp = client.get("/test")
        rid = resp.headers.get("X-Request-ID", "")
        assert re.match(
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            rid
        ), f"Not a valid UUID4: {rid}"

    def test_unique_request_ids(self, client):
        rid1 = client.get("/test").headers.get("X-Request-ID")
        rid2 = client.get("/test").headers.get("X-Request-ID")
        assert rid1 != rid2

    def test_response_status_preserved(self, client):
        resp = client.get("/test")
        assert resp.status_code == 200
