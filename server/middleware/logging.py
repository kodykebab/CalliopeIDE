"""
Flask Middleware for Request/Response Logging
Integrates with structured logging system
"""

import time
from flask import Flask, request, g
from functools import wraps
from typing import Callable, Any
from server.logger import get_loggers


def init_logging_middleware(app: Flask) -> None:
    """Initialize logging middleware for Flask app"""
    loggers = get_loggers()
    request_logger = loggers["request"]

    @app.before_request
    def before_request() -> None:
        """Log incoming requests"""
        g.start_time = time.time()
        
        request_logger.log_request(
            method=request.method,
            path=request.path,
            remote_addr=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            content_length=request.content_length,
        )

    @app.after_request
    def after_request(response: Any) -> Any:
        """Log outgoing responses"""
        if hasattr(g, "start_time"):
            response_time_ms = (time.time() - g.start_time) * 1000
        else:
            response_time_ms = 0

        request_logger.log_response(
            status_code=response.status_code,
            response_time_ms=response_time_ms,
            path=request.path,
            method=request.method,
            content_length=response.content_length,
        )

        return response

    @app.errorhandler(Exception)
    def handle_error(error: Exception) -> tuple:
        """Log unhandled errors"""
        request_logger.log_error(
            error=error,
            path=request.path,
            method=request.method,
            remote_addr=request.remote_addr,
        )
        
        return {"error": "Internal server error"}, 500


def log_operation(operation_type: str = "operation") -> Callable:
    """Decorator to log specific operations"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            loggers = get_loggers()
            app_logger = loggers["app"]
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                app_logger.info(
                    f"{operation_type} completed",
                    extra={
                        "type": operation_type,
                        "function": func.__name__,
                        "duration_ms": duration_ms,
                        "status": "success",
                    }
                )
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                app_logger.error(
                    f"{operation_type} failed: {e}",
                    extra={
                        "type": operation_type,
                        "function": func.__name__,
                        "duration_ms": duration_ms,
                        "status": "error",
                        "error": str(e),
                    },
                    exc_info=True
                )
                raise
        
        return wrapper
    return decorator
