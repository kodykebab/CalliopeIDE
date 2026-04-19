"""
Structured JSON logging configuration for Calliope IDE.
Addresses issue #60.

Sets up:
  - JSON-formatted log output for all loggers
  - Request ID injection per Flask request
  - Standard log fields: timestamp, level, logger, message, request_id
  - Performance logging for slow requests (>500ms)
  - Consistent log levels across all modules
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

# Per-request correlation ID stored in a ContextVar so it's thread-safe
_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Return the current request's correlation ID, or empty string if outside request context."""
    return _request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set the current request's correlation ID."""
    _request_id_var.set(request_id)


# ── JSON Formatter ─────────────────────────────────────────────────────────────

class JsonFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects.

    Every record includes:
        timestamp   ISO-8601 UTC
        level       DEBUG / INFO / WARNING / ERROR / CRITICAL
        logger      Logger name (typically module path)
        message     Log message
        request_id  Per-request UUID (empty outside request context)

    Records with exc_info also include:
        exception   Formatted traceback string
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }

        # Include any extra fields passed via logger.info("msg", extra={...})
        _STANDARD_ATTRS = {
            "args", "asctime", "created", "exc_info", "exc_text", "filename",
            "funcName", "levelname", "levelno", "lineno", "message", "module",
            "msecs", "msg", "name", "pathname", "process", "processName",
            "relativeCreated", "stack_info", "thread", "threadName",
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                try:
                    json.dumps(value)  # Only include JSON-serializable values
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = str(value)

        # Include formatted traceback if present
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


# ── Logging setup ─────────────────────────────────────────────────────────────

def configure_logging(
    level: str = "INFO",
    json_output: bool = True,
) -> None:
    """
    Configure structured logging for the entire application.

    Call once at application startup (in server/start.py).

    Args:
        level:       Root log level string. Defaults to INFO.
        json_output: If True, use JSON formatter. If False, use plain text
                     (useful for local development).
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    handler = logging.StreamHandler()

    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
        ))

    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicate output
    root.handlers.clear()
    root.addHandler(handler)

    # Silence noisy third-party loggers
    for noisy in ("werkzeug", "sqlalchemy.engine", "urllib3", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Structured logging configured",
        extra={"log_level": level, "json_output": json_output},
    )


# ── Flask middleware ──────────────────────────────────────────────────────────

def register_request_logging(app) -> None:
    """
    Register before/after request hooks on a Flask app to:
      1. Generate a unique request_id for each incoming request
      2. Log request start (method, path, remote_addr)
      3. Log request completion (status, duration_ms)
      4. Log slow requests (>500ms) at WARNING level
      5. Add X-Request-ID header to all responses

    Usage:
        from server.utils.logging_config import register_request_logging
        register_request_logging(app)
    """
    logger = logging.getLogger("calliope.request")
    _SLOW_REQUEST_MS = 500

    @app.before_request
    def _before_request():
        from flask import request, g
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)
        g.request_id = request_id
        g.request_start = time.monotonic()

        logger.info(
            "Request started",
            extra={
                "method": request.method,
                "path": request.path,
                "remote_addr": request.remote_addr,
                "content_length": request.content_length or 0,
            },
        )

    @app.after_request
    def _after_request(response):
        from flask import request, g
        duration_ms = round((time.monotonic() - g.get("request_start", time.monotonic())) * 1000, 1)
        status_code = response.status_code

        log_fn = logger.warning if duration_ms > _SLOW_REQUEST_MS else logger.info
        log_fn(
            "Request completed",
            extra={
                "method": request.method,
                "path": request.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )

        response.headers["X-Request-ID"] = get_request_id()
        return response

    @app.errorhandler(Exception)
    def _unhandled_exception(exc):
        from flask import request, jsonify
        logger.error(
            "Unhandled exception",
            extra={
                "method": request.method,
                "path": request.path,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
            exc_info=True,
        )
        return jsonify({"success": False, "error": "Internal server error"}), 500
