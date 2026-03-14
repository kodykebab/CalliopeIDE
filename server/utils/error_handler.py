"""
Enhanced Error Handler for Calliope IDE
Provides comprehensive error handling, logging, and user-friendly error responses
"""

import logging
import traceback
from functools import wraps
from flask import jsonify
from typing import Callable, Any


class CalliopeError(Exception):
    """Base exception class for Calliope IDE"""
    def __init__(self, message: str, status_code: int = 500, details: dict = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ValidationError(CalliopeError):
    """Raised when input validation fails"""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, status_code=400, details=details)


class AuthenticationError(CalliopeError):
    """Raised when authentication fails"""
    def __init__(self, message: str = "Authentication failed", details: dict = None):
        super().__init__(message, status_code=401, details=details)


class AuthorizationError(CalliopeError):
    """Raised when user lacks required permissions"""
    def __init__(self, message: str = "Insufficient permissions", details: dict = None):
        super().__init__(message, status_code=403, details=details)


class ResourceNotFoundError(CalliopeError):
    """Raised when a requested resource is not found"""
    def __init__(self, resource: str, details: dict = None):
        message = f"{resource} not found"
        super().__init__(message, status_code=404, details=details)


class AIServiceError(CalliopeError):
    """Raised when AI service encounters an error"""
    def __init__(self, message: str = "AI service error", details: dict = None):
        super().__init__(message, status_code=503, details=details)


class RateLimitError(CalliopeError):
    """Raised when rate limit is exceeded"""
    def __init__(self, message: str = "Rate limit exceeded", details: dict = None):
        super().__init__(message, status_code=429, details=details)


def setup_error_logging(app):
    """
    Configure error logging for the application
    
    Args:
        app: Flask application instance
    """
    # Create logger
    logger = logging.getLogger('calliope_ide')
    logger.setLevel(logging.INFO)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Create file handler for errors
    error_handler = logging.FileHandler('error.log')
    error_handler.setLevel(logging.ERROR)
    
    # Create formatter
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )
    console_handler.setFormatter(formatter)
    error_handler.setFormatter(formatter)
    
    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(error_handler)
    
    return logger


def handle_error(error):
    """
    Convert exceptions to JSON responses
    
    Args:
        error: Exception instance
        
    Returns:
        JSON response with error details
    """
    logger = logging.getLogger('calliope_ide')
    
    # Handle Calliope custom errors
    if isinstance(error, CalliopeError):
        logger.warning(f"{error.__class__.__name__}: {error.message}")
        response = {
            'success': False,
            'error': error.message,
            'details': error.details
        }
        return jsonify(response), error.status_code
    
    # Handle generic exceptions
    logger.error(f"Unhandled exception: {str(error)}")
    logger.error(traceback.format_exc())
    
    response = {
        'success': False,
        'error': 'An unexpected error occurred',
        'details': {}
    }
    
    # Include error details in development mode
    if hasattr(error, '__dict__'):
        response['details'] = {'type': error.__class__.__name__}
    
    return jsonify(response), 500


def error_handler(func: Callable) -> Callable:
    """
    Decorator to handle errors in route handlers
    
    Args:
        func: Route handler function
        
    Returns:
        Wrapped function with error handling
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except CalliopeError as e:
            return handle_error(e)
        except Exception as e:
            return handle_error(e)
    
    return wrapper


def validate_request_data(data: dict, required_fields: list) -> None:
    """
    Validate that required fields are present in request data
    
    Args:
        data: Request data dictionary
        required_fields: List of required field names
        
    Raises:
        ValidationError: If validation fails
    """
    if not data:
        raise ValidationError("Request body is required")
    
    missing_fields = [field for field in required_fields if field not in data]
    
    if missing_fields:
        raise ValidationError(
            "Missing required fields",
            details={'missing_fields': missing_fields}
        )
    
    empty_fields = [
        field for field in required_fields 
        if field in data and not data[field]
    ]
    
    if empty_fields:
        raise ValidationError(
            "Empty values not allowed",
            details={'empty_fields': empty_fields}
        )


def log_request(logger, request, user_id=None):
    """
    Log incoming request details
    
    Args:
        logger: Logger instance
        request: Flask request object
        user_id: Optional user ID
    """
    logger.info(
        f"Request: {request.method} {request.path} "
        f"from {request.remote_addr} "
        f"(User: {user_id or 'Anonymous'})"
    )


def log_response(logger, response, duration=None):
    """
    Log response details
    
    Args:
        logger: Logger instance
        response: Response object
        duration: Optional request duration in ms
    """
    duration_str = f" ({duration}ms)" if duration else ""
    logger.info(f"Response: {response.status_code}{duration_str}")
