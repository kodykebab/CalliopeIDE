"""
Structured logging and system observability for Calliope IDE.
Addresses issue #60.

Provides:
- JSON-structured log output for machine-parseable logs
- Request ID injection for end-to-end tracing
- Per-request context (method, path, status, duration)
- Consistent log levels across all modules
- Flask middleware for automatic request/response logging
"""

import json
import logging
import time
import uuid
from typing import Any, Dict, Optional
from contextvars import ContextVar
from flask import Flask, request, g

# ── Context variable for request-scoped trace ID ──────────────────────────────
_request_id: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Return the current request's trace ID, or empty string outside a request."""
    return _request_id.get("")


# ── JSON log formatter ────────────────────────────────────────────────────────

class JSONFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects.

    Each log line includes:
      timestamp, level, logger, message, request_id (if in a request context),
      and any extra fields passed via the `extra` kwarg.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Attach request ID when available
        rid = get_request_id()
        if rid:
            log_obj["request_id"] = rid

        # Attach any extra fields the caller passed
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            } and not key.startswith("_"):
                log_obj[key] = value

        # Attach exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)


# ── Logger factory ────────────────────────────────────────────────────────────

def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Return a named logger configured with JSONFormatter.

    Safe to call multiple times — handlers are not duplicated.

    Args:
        name:  Logger name (use __name__ in each module).
        level: Log level (default: INFO).

    Returns:
        Configured Logger instance.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Already configured

    logger.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


# ── Root logger setup ─────────────────────────────────────────────────────────

def setup_logging(
    app_name: str = "calliope-ide",
    level: int = logging.INFO,
) -> logging.Logger:
    """
    Configure the root application logger with JSON output.

    Call once at application startup (in start.py).

    Args:
        app_name: Name used as the root logger identifier.
        level:    Minimum log level (default: INFO).

    Returns:
        Root application Logger.
    """
    # Configure root logger so third-party libs also emit JSON
    root = logging.getLogger()
    if not any(isinstance(h.formatter, JSONFormatter) for h in root.handlers):
        root.setLevel(level)
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        root.addHandler(handler)

    return get_logger(app_name, level)


# ── Flask request logging middleware ─────────────────────────────────────────

def init_request_logging(app: Flask) -> None:
    """
    Register before/after request hooks on the Flask app.

    Before each request:
      - Generates a unique request_id (UUID4) and stores it in Flask g
        and the contextvars ContextVar for thread/async safety.
      - Logs incoming request (method, path, remote_addr).

    After each request:
      - Logs response (status_code, duration_ms).
      - Adds X-Request-ID header to the response.

    Args:
        app: Flask application instance.
    """
    logger = get_logger("calliope-ide.requests")

    @app.before_request
    def before_request():
        # Generate and store request ID
        rid = str(uuid.uuid4())
        g.request_id = rid
        g.start_time = time.monotonic()
        token = _request_id.set(rid)
        g._request_id_token = token  # Store token for cleanup

        logger.info(
            "request_started",
            extra={
                "event": "request_started",
                "method": request.method,
                "path": request.path,
                "remote_addr": request.remote_addr,
                "content_length": request.content_length,
            },
        )

    @app.after_request
    def after_request(response):
        # Calculate duration
        duration_ms = round(
            (time.monotonic() - getattr(g, "start_time", time.monotonic())) * 1000, 2
        )
        rid = getattr(g, "request_id", "")

        # Add request ID to response headers for client-side tracing
        if rid:
            response.headers["X-Request-ID"] = rid

        logger.info(
            "request_completed",
            extra={
                "event": "request_completed",
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        # Clean up contextvars token
        token = getattr(g, "_request_id_token", None)
        if token is not None:
            _request_id.reset(token)

        return response

    @app.teardown_request
    def teardown_request(exc):
        if exc is not None:
            logger = get_logger("calliope-ide.errors")
            logger.error(
                "request_error",
                extra={
                    "event": "request_error",
                    "method": request.method,
                    "path": request.path,
                    "error": str(exc),
                },
                exc_info=exc,
            )
