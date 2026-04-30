"""
Monitoring utilities with structured logging
Provides comprehensive observability with structured JSON logging and performance monitoring
"""
import logging
from typing import Any, Dict, Optional
from flask import Flask, g
from server.utils.structured_logger import get_structured_logger, setup_structured_logging


def setup_logging(name: str = 'calliope-ide'):
    """Setup structured logging - returns StructuredLogger instance"""
    return get_structured_logger(name)


def init_sentry(app: Flask):
    """Stub - Sentry integration removed"""
    pass


def monitor_endpoint(func):
    """Decorator to monitor endpoint performance with structured logging"""
    from server.utils.structured_logger import log_performance
    return log_performance(func)


def get_monitoring_stats() -> Dict[str, Any]:
    """Return monitoring system status"""
    return {
        'enabled': True,
        'logging_type': 'structured_json',
        'request_tracing': True,
        'performance_monitoring': True,
        'error_tracking': True
    }


def track_error(error: Exception, context: Optional[Dict[str, Any]] = None):
    """Track error with structured logging and context"""
    logger = get_structured_logger()
    
    # Add request context if available
    error_context = context.copy() if context else {}
    if hasattr(g, 'request_id'):
        error_context['request_id'] = g.request_id
    if hasattr(g, 'user_id'):
        error_context['user_id'] = g.user_id
    if hasattr(g, 'session_id'):
        error_context['session_id'] = g.session_id
    
    logger.log_error_with_context(error, error_context)


def capture_exception(error: Exception, context: Optional[Dict[str, Any]] = None):
    """Alias for track_error for backward compatibility"""
    track_error(error, context)


def log_api_metrics(method: str, endpoint: str, status_code: int, 
                   duration_ms: float, user_id: Optional[int] = None):
    """Log API metrics for monitoring"""
    logger = get_structured_logger()
    logger.info(
        f"API metrics: {method} {endpoint} -> {status_code}",
        event_type='api_metrics',
        method=method,
        endpoint=endpoint,
        status_code=status_code,
        duration_ms=duration_ms,
        user_id=user_id
    )


def log_system_event(event: str, **kwargs):
    """Log system-level events"""
    logger = get_structured_logger()
    logger.info(
        f"System event: {event}",
        event_type='system_event',
        system_event=event,
        **kwargs
    )


def log_security_event(event: str, severity: str = 'info', **kwargs):
    """Log security-related events"""
    logger = get_structured_logger()
    level_method = getattr(logger, severity.lower(), logger.info)
    level_method(
        f"Security event: {event}",
        event_type='security_event',
        security_event=event,
        severity=severity,
        **kwargs
    )
