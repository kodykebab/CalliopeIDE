"""
Structured JSON logging implementation for CalliopeIDE
Provides consistent, structured logging with request tracing and performance monitoring
"""
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from functools import wraps
from flask import Flask, request, g


class StructuredLogger:
    """Structured JSON logger with request tracing and performance monitoring"""
    
    def __init__(self, name: str, level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Remove existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Create structured JSON formatter
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(handler)
        
        # Add request context tracking
        self._request_context = {}
    
    def _build_log_record(self, level: str, message: str, **kwargs) -> Dict[str, Any]:
        """Build structured log record with context"""
        record = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': level.upper(),
            'logger': self.logger.name,
            'message': message,
            'service': 'calliope-ide',
        }
        
        # Add request context if available
        if hasattr(g, 'request_id'):
            record['request_id'] = g.request_id
        if hasattr(g, 'user_id'):
            record['user_id'] = g.user_id
        if hasattr(g, 'session_id'):
            record['session_id'] = g.session_id
        
        # Add any additional context
        record.update(kwargs)
        
        return record
    
    def info(self, message: str, **kwargs):
        """Log info level message"""
        record = self._build_log_record('info', message, **kwargs)
        self.logger.info(json.dumps(record))
    
    def warning(self, message: str, **kwargs):
        """Log warning level message"""
        record = self._build_log_record('warning', message, **kwargs)
        self.logger.warning(json.dumps(record))
    
    def error(self, message: str, **kwargs):
        """Log error level message"""
        record = self._build_log_record('error', message, **kwargs)
        self.logger.error(json.dumps(record))
    
    def debug(self, message: str, **kwargs):
        """Log debug level message"""
        record = self._build_log_record('debug', message, **kwargs)
        self.logger.debug(json.dumps(record))
    
    def log_api_request(self, method: str, endpoint: str, user_id: Optional[int] = None, **kwargs):
        """Log API request with structured data"""
        self.info(
            f"API request: {method} {endpoint}",
            event_type='api_request',
            method=method,
            endpoint=endpoint,
            user_id=user_id,
            **kwargs
        )
    
    def log_api_response(self, method: str, endpoint: str, status_code: int, 
                        duration_ms: Optional[float] = None, **kwargs):
        """Log API response with structured data"""
        self.info(
            f"API response: {method} {endpoint} -> {status_code}",
            event_type='api_response',
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            duration_ms=duration_ms,
            **kwargs
        )
    
    def log_execution_start(self, command: str, user_id: Optional[int] = None, **kwargs):
        """Log code execution start"""
        self.info(
            f"Code execution started: {command[:100]}{'...' if len(command) > 100 else ''}",
            event_type='execution_start',
            command=command,
            user_id=user_id,
            **kwargs
        )
    
    def log_execution_complete(self, command: str, status: str, duration_ms: float,
                              user_id: Optional[int] = None, **kwargs):
        """Log code execution completion"""
        self.info(
            f"Code execution completed: {status} in {duration_ms:.2f}ms",
            event_type='execution_complete',
            command=command,
            status=status,
            duration_ms=duration_ms,
            user_id=user_id,
            **kwargs
        )
    
    def log_session_event(self, event: str, session_id: str, user_id: Optional[int] = None, **kwargs):
        """Log session-related events"""
        self.info(
            f"Session event: {event}",
            event_type='session_event',
            session_event=event,
            session_id=session_id,
            user_id=user_id,
            **kwargs
        )
    
    def log_auth_event(self, event: str, user_id: Optional[int] = None, **kwargs):
        """Log authentication events"""
        self.info(
            f"Auth event: {event}",
            event_type='auth_event',
            auth_event=event,
            user_id=user_id,
            **kwargs
        )
    
    def log_error_with_context(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """Log error with full context and traceback"""
        error_context = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'event_type': 'error',
        }
        
        if context:
            error_context.update(context)
        
        self.error(f"Error occurred: {type(error).__name__}: {str(error)}", **error_context)


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging"""
    
    def format(self, record):
        # If the record already contains JSON (from our StructuredLogger), pass it through
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            try:
                # Try to parse as JSON to see if it's already structured
                json.loads(record.msg)
                return record.msg
            except (json.JSONDecodeError, ValueError):
                pass
        
        # For non-structured logs, format them as JSON
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'service': 'calliope-ide',
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


# Global logger instance
_structured_logger: Optional[StructuredLogger] = None


def get_structured_logger(name: str = 'calliope-ide') -> StructuredLogger:
    """Get or create structured logger instance"""
    global _structured_logger
    if _structured_logger is None:
        _structured_logger = StructuredLogger(name)
    return _structured_logger


def setup_structured_logging(app: Flask) -> StructuredLogger:
    """Setup structured logging for Flask app with request context"""
    logger = get_structured_logger()
    
    @app.before_request
    def before_request():
        """Set up request context before each request"""
        g.request_id = str(uuid.uuid4())
        g.start_time = time.time()
        
        # Try to get user info from token if available
        try:
            from server.utils.auth_utils import decode_token
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
                payload = decode_token(token)
                if payload:
                    g.user_id = payload.get('user_id')
        except Exception:
            pass  # Silently fail auth extraction for non-auth endpoints
    
    @app.after_request
    def after_request(response):
        """Log request completion"""
        if hasattr(g, 'start_time'):
            duration_ms = (time.time() - g.start_time) * 1000
            
            logger.log_api_response(
                method=request.method,
                endpoint=request.endpoint or request.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                user_agent=request.headers.get('User-Agent'),
                ip_address=request.remote_addr
            )
        
        return response
    
    return logger


def log_performance(func):
    """Decorator to log function performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000
            
            logger = get_structured_logger()
            logger.info(
                f"Function completed: {func.__name__}",
                event_type='function_performance',
                function=func.__name__,
                duration_ms=duration_ms,
                success=True
            )
            
            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            logger = get_structured_logger()
            logger.error(
                f"Function failed: {func.__name__}",
                event_type='function_performance',
                function=func.__name__,
                duration_ms=duration_ms,
                success=False,
                error_type=type(e).__name__,
                error_message=str(e)
            )
            
            raise
    
    return wrapper


def log_api_call(endpoint_name: str):
    """Decorator to log API calls with structured data"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_structured_logger()
            
            # Extract request info
            method = request.method if request else 'UNKNOWN'
            endpoint = request.endpoint or endpoint_name
            
            logger.log_api_request(
                method=method,
                endpoint=endpoint,
                user_id=getattr(g, 'user_id', None),
                args_count=len(args),
                kwargs_keys=list(kwargs.keys()) if kwargs else []
            )
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # Determine status code from result if it's a Flask response tuple
                status_code = 200
                if isinstance(result, tuple) and len(result) > 1:
                    status_code = result[1]
                
                logger.log_api_response(
                    method=method,
                    endpoint=endpoint,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    user_id=getattr(g, 'user_id', None)
                )
                
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                logger.log_api_response(
                    method=method,
                    endpoint=endpoint,
                    status_code=500,
                    duration_ms=duration_ms,
                    user_id=getattr(g, 'user_id', None),
                    error=type(e).__name__,
                    error_message=str(e)
                )
                
                raise
        
        return wrapper
    return decorator
