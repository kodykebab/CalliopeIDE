"""
Comprehensive error handling utilities for Soroban endpoints
Addresses HIGH PRIORITY security issue #100 - Enhanced error handling and logging
"""

import logging
import traceback
import json
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from flask import jsonify, request
from functools import wraps

logger = logging.getLogger(__name__)

class SecurityError(Exception):
    """Base class for security-related errors"""
    def __init__(self, message: str, error_code: str = "SECURITY_ERROR", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.timestamp = datetime.now(timezone.utc).isoformat()

class RateLimitError(SecurityError):
    """Rate limiting related errors"""
    def __init__(self, message: str, retry_after: int = 60, usage_info: Optional[Dict] = None):
        super().__init__(message, "RATE_LIMIT_EXCEEDED", 429)
        self.retry_after = retry_after
        self.usage_info = usage_info or {}

class ValidationError(SecurityError):
    """Input validation related errors"""
    def __init__(self, message: str, field: str = None, value: Any = None):
        super().__init__(message, "VALIDATION_ERROR", 400)
        self.field = field
        self.value = value

class StellarAddressError(ValidationError):
    """Stellar address validation errors"""
    def __init__(self, message: str, address_type: str = None, address: str = None):
        super().__init__(message, f"stellar_{address_type}", address)
        self.error_code = f"STELLAR_{address_type.upper()}_INVALID"

class FriendbotLimitError(SecurityError):
    """Friendbot usage limit errors"""
    def __init__(self, message: str, usage_info: Dict = None):
        super().__init__(message, "FRIENDBOT_LIMIT_EXCEEDED", 429)
        self.usage_info = usage_info or {}

class SecurityLogger:
    """Enhanced security logging for monitoring and incident response"""
    
    @staticmethod
    def log_rate_limit_violation(user_id: str, ip_address: str, endpoint: str, 
                                limit_type: str, retry_after: int):
        """Log rate limit violations for security monitoring"""
        logger.warning(
            "RATE_LIMIT_VIOLATION: user=%s, ip=%s, endpoint=%s, limit_type=%s, retry_after=%s",
            user_id, ip_address, endpoint, limit_type, retry_after,
            extra={
                'event_type': 'rate_limit_violation',
                'user_id': user_id,
                'ip_address': ip_address,
                'endpoint': endpoint,
                'limit_type': limit_type,
                'retry_after': retry_after,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'user_agent': request.headers.get('User-Agent', ''),
                'request_path': request.path
            }
        )
    
    @staticmethod
    def log_validation_error(user_id: str, ip_address: str, field: str, value: str, error: str):
        """Log validation errors for security monitoring"""
        logger.warning(
            "VALIDATION_ERROR: user=%s, ip=%s, field=%s, error=%s",
            user_id, ip_address, field, error,
            extra={
                'event_type': 'validation_error',
                'user_id': user_id,
                'ip_address': ip_address,
                'field': field,
                'value': value[:100] if value else '',  # Limit value length for logging
                'error': error,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'request_path': request.path
            }
        )
    
    @staticmethod
    def log_friendbot_abuse(user_id: str, ip_address: str, account: str, usage_info: Dict):
        """Log Friendbot abuse attempts"""
        logger.warning(
            "FRIENDBOT_ABUSE: user=%s, ip=%s, account=%s, usage=%s",
            user_id, ip_address, account, usage_info,
            extra={
                'event_type': 'friendbot_abuse',
                'user_id': user_id,
                'ip_address': ip_address,
                'account': account,
                'usage_info': usage_info,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'request_path': request.path
            }
        )
    
    @staticmethod
    def log_security_incident(user_id: str, ip_address: str, incident_type: str, 
                             details: Dict, severity: str = 'medium'):
        """Log general security incidents"""
        logger.error(
            "SECURITY_INCIDENT: user=%s, ip=%s, type=%s, severity=%s",
            user_id, ip_address, incident_type, severity,
            extra={
                'event_type': 'security_incident',
                'user_id': user_id,
                'ip_address': ip_address,
                'incident_type': incident_type,
                'severity': severity,
                'details': details,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'request_path': request.path,
                'user_agent': request.headers.get('User-Agent', '')
            }
        )

def handle_security_errors(f):
    """
    Decorator for handling security-related errors consistently
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except RateLimitError as e:
            SecurityLogger.log_rate_limit_violation(
                getattr(request, 'user_id', 'anonymous'),
                request.remote_addr,
                request.endpoint,
                'unknown',
                e.retry_after
            )
            return jsonify({
                "success": False,
                "error": e.message,
                "error_code": e.error_code,
                "retry_after": e.retry_after,
                "timestamp": e.timestamp,
                **({"usage": e.usage_info} if e.usage_info else {})
            }), e.status_code
            
        except ValidationError as e:
            SecurityLogger.log_validation_error(
                getattr(request, 'user_id', 'anonymous'),
                request.remote_addr,
                e.field or 'unknown',
                str(e.value) if e.value else '',
                e.message
            )
            return jsonify({
                "success": False,
                "error": e.message,
                "error_code": e.error_code,
                "field": e.field,
                "timestamp": e.timestamp
            }), e.status_code
            
        except StellarAddressError as e:
            SecurityLogger.log_validation_error(
                getattr(request, 'user_id', 'anonymous'),
                request.remote_addr,
                e.field,
                str(e.value) if e.value else '',
                e.message
            )
            return jsonify({
                "success": False,
                "error": e.message,
                "error_code": e.error_code,
                "field": e.field,
                "timestamp": e.timestamp
            }), e.status_code
            
        except FriendbotLimitError as e:
            SecurityLogger.log_friendbot_abuse(
                getattr(request, 'user_id', 'anonymous'),
                request.remote_addr,
                'unknown_account',
                e.usage_info
            )
            return jsonify({
                "success": False,
                "error": e.message,
                "error_code": e.error_code,
                "usage": e.usage_info,
                "timestamp": e.timestamp
            }), e.status_code
            
        except SecurityError as e:
            SecurityLogger.log_security_incident(
                getattr(request, 'user_id', 'anonymous'),
                request.remote_addr,
                e.error_code,
                {'message': e.message},
                'medium'
            )
            return jsonify({
                "success": False,
                "error": e.message,
                "error_code": e.error_code,
                "timestamp": e.timestamp
            }), e.status_code
            
        except Exception as e:
            # Log unexpected errors with full context
            logger.exception(
                "UNEXPECTED_ERROR in %s: %s",
                request.endpoint if request else 'unknown',
                str(e),
                extra={
                    'event_type': 'unexpected_error',
                    'endpoint': request.endpoint if request else 'unknown',
                    'path': request.path if request else 'unknown',
                    'method': request.method if request else 'unknown',
                    'user_id': getattr(request, 'user_id', 'anonymous'),
                    'ip_address': request.remote_addr if request else 'unknown',
                    'traceback': traceback.format_exc(),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            )
            return jsonify({
                "success": False,
                "error": "An unexpected error occurred. Please try again later.",
                "error_code": "INTERNAL_ERROR",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }), 500
    
    return decorated_function

def sanitize_error_message(error: str, max_length: int = 200) -> str:
    """
    Sanitize error messages to prevent information disclosure
    """
    if not error:
        return "Unknown error occurred"
    
    # Remove potentially sensitive information
    sanitized = error
    sensitive_patterns = [
        r'password\s*[:=]\s*\S+',
        r'secret\s*[:=]\s*\S+',
        r'key\s*[:=]\s*\S+',
        r'token\s*[:=]\s*\S+',
        r'authorization\s*[:=]\s*\S+',
        r'private\s*key',
        r'seed\s*phrase',
    ]
    
    import re
    for pattern in sensitive_patterns:
        sanitized = re.sub(pattern, '[REDACTED]', sanitized, flags=re.IGNORECASE)
    
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length-3] + "..."
    
    return sanitized

def create_error_response(error_code: str, message: str, status_code: int = 400, 
                         additional_data: Dict = None) -> tuple:
    """
    Create a standardized error response
    """
    response_data = {
        "success": False,
        "error": sanitize_error_message(message),
        "error_code": error_code,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    if additional_data:
        response_data.update(additional_data)
    
    return jsonify(response_data), status_code

def log_request_context(user_id: str = None, additional_context: Dict = None):
    """
    Log request context for debugging and monitoring
    """
    context = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'path': request.path,
        'method': request.method,
        'ip_address': request.remote_addr,
        'user_agent': request.headers.get('User-Agent', ''),
        'content_type': request.headers.get('Content-Type', ''),
    }
    
    if user_id:
        context['user_id'] = user_id
    
    if additional_context:
        context.update(additional_context)
    
    logger.debug("REQUEST_CONTEXT: %s", json.dumps(context, default=str))

# Rate limit breach detection
class RateLimitBreachDetector:
    """Detect potential rate limit breach attempts"""
    
    def __init__(self, threshold: int = 100, window_minutes: int = 5):
        self.threshold = threshold
        self.window_minutes = window_minutes
        self.breach_attempts: Dict[str, list] = {}
    
    def record_attempt(self, user_id: str, ip_address: str):
        """Record a rate limit violation attempt"""
        key = f"{user_id}:{ip_address}"
        now = datetime.now(timezone.utc)
        
        if key not in self.breach_attempts:
            self.breach_attempts[key] = []
        
        # Clean old attempts
        cutoff = now - timezone.timedelta(minutes=self.window_minutes)
        self.breach_attempts[key] = [
            attempt for attempt in self.breach_attempts[key] 
            if attempt > cutoff
        ]
        
        # Add current attempt
        self.breach_attempts[key].append(now)
        
        # Check for breach pattern
        if len(self.breach_attempts[key]) >= self.threshold:
            SecurityLogger.log_security_incident(
                user_id, ip_address, 'rate_limit_breach_pattern',
                {
                    'attempts': len(self.breach_attempts[key]),
                    'window_minutes': self.window_minutes,
                    'threshold': self.threshold
                },
                'high'
            )
            return True
        
        return False

# Global breach detector instance
breach_detector = RateLimitBreachDetector()
