"""
Structured Logging Module for Calliope IDE Backend
Provides JSON logging with request/response tracking and error monitoring
"""

import json
import logging
import logging.handlers
import os
import sys
import time
import traceback
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

# Ensure logs directory exists
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs logs in JSON format"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Add extra fields if present
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_data.update(record.extra)

        return json.dumps(log_data)


class RequestLogger:
    """Logger for HTTP requests and responses"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def log_request(
        self,
        method: str,
        path: str,
        remote_addr: str,
        **kwargs: Any,
    ) -> None:
        """Log incoming HTTP request"""
        extra = {
            "type": "http_request",
            "method": method,
            "path": path,
            "remote_addr": remote_addr,
            "timestamp": time.time(),
        }
        extra.update(kwargs)

        self.logger.info(f"{method} {path}", extra=extra)

    def log_response(
        self,
        status_code: int,
        response_time_ms: float,
        path: str,
        method: str,
        **kwargs: Any,
    ) -> None:
        """Log HTTP response"""
        extra = {
            "type": "http_response",
            "status_code": status_code,
            "response_time_ms": response_time_ms,
            "path": path,
            "method": method,
        }
        extra.update(kwargs)

        level = (
            logging.ERROR
            if status_code >= 500
            else logging.WARNING
            if status_code >= 400
            else logging.INFO
        )
        self.logger.log(level, f"{method} {path} {status_code}", extra=extra)

    def log_error(
        self,
        error: Exception,
        path: str,
        method: str,
        status_code: int = 500,
        **kwargs: Any,
    ) -> None:
        """Log error during request processing"""
        extra = {
            "type": "http_error",
            "error_type": type(error).__name__,
            "error_message": str(error),
            "path": path,
            "method": method,
            "status_code": status_code,
        }
        extra.update(kwargs)

        self.logger.error(f"Error processing {method} {path}: {error}", extra=extra, exc_info=True)


class DatabaseLogger:
    """Logger for database operations"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def log_query(
        self,
        query: str,
        params: Optional[Dict] = None,
        execution_time_ms: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        """Log database query"""
        extra = {
            "type": "database_query",
            "query": query,
            "params": params,
            "execution_time_ms": execution_time_ms,
        }
        extra.update(kwargs)

        self.logger.debug(f"Query: {query}", extra=extra)

    def log_connection(self, status: str, **kwargs: Any) -> None:
        """Log database connection events"""
        extra = {
            "type": "database_connection",
            "status": status,
        }
        extra.update(kwargs)

        self.logger.info(f"Database connection: {status}", extra=extra)

    def log_error(self, error: Exception, query: str = "", **kwargs: Any) -> None:
        """Log database errors"""
        extra = {
            "type": "database_error",
            "error_type": type(error).__name__,
            "error_message": str(error),
            "query": query,
        }
        extra.update(kwargs)

        self.logger.error(f"Database error: {error}", extra=extra, exc_info=True)


class AuthLogger:
    """Logger for authentication events"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def log_login(self, user_id: str, method: str = "password", **kwargs: Any) -> None:
        """Log user login"""
        extra = {
            "type": "auth_login",
            "user_id": user_id,
            "method": method,
        }
        extra.update(kwargs)

        self.logger.info(f"User login: {user_id} ({method})", extra=extra)

    def log_logout(self, user_id: str, **kwargs: Any) -> None:
        """Log user logout"""
        extra = {
            "type": "auth_logout",
            "user_id": user_id,
        }
        extra.update(kwargs)

        self.logger.info(f"User logout: {user_id}", extra=extra)

    def log_auth_failure(
        self,
        reason: str,
        user_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Log authentication failure"""
        extra = {
            "type": "auth_failure",
            "reason": reason,
            "user_id": user_id,
        }
        extra.update(kwargs)

        self.logger.warning(f"Authentication failure: {reason}", extra=extra)

    def log_token_refresh(self, user_id: str, **kwargs: Any) -> None:
        """Log token refresh"""
        extra = {
            "type": "auth_token_refresh",
            "user_id": user_id,
        }
        extra.update(kwargs)

        self.logger.debug(f"Token refreshed for user: {user_id}", extra=extra)


def setup_logging(
    app_name: str = "calliope",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
) -> Dict[str, logging.Logger]:
    """
    Setup logging infrastructure with JSON formatting
    
    Args:
        app_name: Application name for logging
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file (uses LOGS_DIR if None)
    
    Returns:
        Dictionary with loggers for different components
    """
    # Create main logger
    main_logger = logging.getLogger(app_name)
    main_logger.setLevel(level)

    # Remove existing handlers
    main_logger.handlers = []

    # Create formatters
    json_formatter = JSONFormatter()
    console_formatter = logging.Formatter("%(levelname)s - %(message)s")

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)
    main_logger.addHandler(console_handler)

    # File handler (JSON logs)
    if log_file is None:
        log_file = LOGS_DIR / f"{app_name}.log"
    else:
        log_file = Path(log_file)

    log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.handlers.RotatingFileHandler(
        str(log_file),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(json_formatter)
    main_logger.addHandler(file_handler)

    # Create component loggers
    return {
        "app": main_logger,
        "http": logging.getLogger(f"{app_name}.http"),
        "database": logging.getLogger(f"{app_name}.database"),
        "auth": logging.getLogger(f"{app_name}.auth"),
        "request": RequestLogger(logging.getLogger(f"{app_name}.request")),
        "database_ops": DatabaseLogger(logging.getLogger(f"{app_name}.database_ops")),
        "auth_ops": AuthLogger(logging.getLogger(f"{app_name}.auth_ops")),
    }


# Global loggers instance
_loggers: Optional[Dict[str, Any]] = None


def get_loggers() -> Dict[str, Any]:
    """Get or initialize loggers"""
    global _loggers
    if _loggers is None:
        log_level = logging.DEBUG if os.getenv("DEBUG") else logging.INFO
        _loggers = setup_logging(level=log_level)
    return _loggers


def get_logger(name: str) -> logging.Logger:
    """Get logger by name"""
    return logging.getLogger(name)
