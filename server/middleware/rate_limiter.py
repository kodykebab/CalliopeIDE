"""
Rate limiting and input validation middleware for Soroban endpoints
Addresses HIGH PRIORITY security issue #100 - Missing rate limiting and validation
"""

import time
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from functools import wraps
from flask import request, jsonify, g
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

# In-memory storage for rate limiting (Redis-ready for production)
class MemoryRateLimiter:
    """In-memory rate limiter that can be easily replaced with Redis"""
    
    def __init__(self):
        # Structure: {key: deque of timestamps}
        self.requests: Dict[str, deque] = defaultdict(deque)
        # Structure: {key: count} for friendbot tracking
        self.friendbot_usage: Dict[str, Dict[str, int]] = defaultdict(lambda: {
            'account_requests': 0,
            'ip_requests': 0,
            'last_reset': datetime.now()
        })
    
    def is_allowed(self, key: str, limit: int, window: int) -> Tuple[bool, int]:
        """
        Check if request is allowed based on rate limit
        
        Args:
            key: Rate limit key (user_id, IP, etc.)
            limit: Maximum requests allowed
            window: Time window in seconds
            
        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        now = time.time()
        cutoff = now - window
        
        # Clean old requests
        while self.requests[key] and self.requests[key][0] <= cutoff:
            self.requests[key].popleft()
        
        current_count = len(self.requests[key])
        
        if current_count >= limit:
            # Calculate when the oldest request will expire
            oldest_request = self.requests[key][0] if self.requests[key] else now
            retry_after = int(oldest_request + window - now)
            return False, max(1, retry_after)
        
        # Add current request
        self.requests[key].append(now)
        return True, 0
    
    def check_friendbot_limit(self, account_key: str, ip_key: str, 
                            account_limit: int = 3, ip_limit: int = 10) -> Tuple[bool, Dict[str, int]]:
        """
        Check Friendbot usage limits with hourly reset
        
        Args:
            account_key: Account identifier
            ip_key: IP address identifier  
            account_limit: Max requests per account per hour
            ip_limit: Max requests per IP per hour
            
        Returns:
            Tuple of (allowed, usage_info)
        """
        now = datetime.now()
        
        # Reset counters if hour has passed
        for key in [account_key, ip_key]:
            last_reset = self.friendbot_usage[key]['last_reset']
            if now - last_reset > timedelta(hours=1):
                self.friendbot_usage[key] = {
                    'account_requests': 0,
                    'ip_requests': 0,
                    'last_reset': now
                }
        
        # Check account limit
        account_requests = self.friendbot_usage[account_key]['account_requests']
        ip_requests = self.friendbot_usage[ip_key]['ip_requests']
        
        if account_requests >= account_limit:
            return False, {
                'account_requests': account_requests,
                'ip_requests': ip_requests,
                'account_limit': account_limit,
                'ip_limit': ip_limit,
                'reset_time': self.friendbot_usage[account_key]['last_reset'] + timedelta(hours=1)
            }
        
        if ip_requests >= ip_limit:
            return False, {
                'account_requests': account_requests,
                'ip_requests': ip_requests,
                'account_limit': account_limit,
                'ip_limit': ip_limit,
                'reset_time': self.friendbot_usage[ip_key]['last_reset'] + timedelta(hours=1)
            }
        
        # Increment counters
        self.friendbot_usage[account_key]['account_requests'] += 1
        self.friendbot_usage[ip_key]['ip_requests'] += 1
        
        return True, {
            'account_requests': self.friendbot_usage[account_key]['account_requests'],
            'ip_requests': self.friendbot_usage[ip_key]['ip_requests'],
            'account_limit': account_limit,
            'ip_limit': ip_limit,
            'reset_time': self.friendbot_usage[account_key]['last_reset'] + timedelta(hours=1)
        }

# Global rate limiter instance
rate_limiter = MemoryRateLimiter()

# Rate limit configurations
RATE_LIMITS = {
    'soroban_invoke': {
        'per_minute': 10,
        'per_hour': 100,
        'description': 'Contract invocation'
    },
    'soroban_deploy': {
        'per_minute': 5,
        'per_hour': 20,
        'description': 'Contract deployment'
    },
    'soroban_compile': {
        'per_minute': 15,
        'per_hour': 150,
        'description': 'Contract compilation'
    },
    'soroban_state': {
        'per_minute': 30,
        'per_hour': 300,
        'description': 'State queries'
    },
    'friendbot': {
        'per_account_hour': 3,
        'per_ip_hour': 10,
        'description': 'Friendbot funding'
    }
}

# Stellar address validation patterns
STELLAR_PATTERNS = {
    'public_key': re.compile(r'^G[A-Z0-9]{55}$'),
    'secret_key': re.compile(r'^S[A-Z0-9]{55}$'),
    'contract_id': re.compile(r'^C[A-Z0-9]{55}$'),
    'function_name': re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]{0,63}$'),
    'session_id': re.compile(r'^\d+$')
}

def validate_stellar_address(address: str, address_type: str) -> Tuple[bool, str]:
    """
    Validate Stellar address format
    
    Args:
        address: Address to validate
        address_type: Type of address (public_key, secret_key, contract_id)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not address or not isinstance(address, str):
        return False, f"{address_type} is required and must be a string"
    
    pattern = STELLAR_PATTERNS.get(address_type)
    if not pattern:
        return False, f"Unknown address type: {address_type}"
    
    if not pattern.match(address.strip()):
        return False, f"Invalid {address_type} format. Expected format: {address_type.upper()}[A-Z0-9]{{55}}"
    
    return True, ""

def validate_function_name(name: str) -> Tuple[bool, str]:
    """Validate contract function name"""
    if not name or not isinstance(name, str):
        return False, "function_name is required and must be a string"
    
    name = name.strip()
    if not name:
        return False, "function_name cannot be empty"
    
    if len(name) > 64:
        return False, "function_name must be 64 characters or less"
    
    if not STELLAR_PATTERNS['function_name'].match(name):
        return False, "function_name must contain only letters, numbers, and underscores, and start with a letter or underscore"
    
    return True, ""

def validate_parameters(params: list) -> Tuple[bool, str]:
    """Validate contract function parameters"""
    if not isinstance(params, list):
        return False, "parameters must be a list"
    
    if len(params) > 20:  # Reasonable limit to prevent abuse
        return False, "Too many parameters (max 20 allowed)"
    
    for i, param in enumerate(params):
        if not isinstance(param, str):
            return False, f"Parameter {i} must be a string"
        
        if len(param) > 1000:  # Prevent extremely long parameters
            return False, f"Parameter {i} is too long (max 1000 characters)"
        
        # Basic validation for parameter format (type:value)
        if ':' in param:
            parts = param.split(':', 1)
            if len(parts) != 2 or not parts[1]:
                return False, f"Parameter {i} has invalid format"
    
    return True, ""

def validate_session_id(session_id) -> Tuple[bool, str]:
    """Validate session ID format"""
    if session_id is None:
        return False, "session_id is required"
    
    try:
        session_id = int(session_id)
        if session_id <= 0:
            return False, "session_id must be a positive integer"
        return True, ""
    except (ValueError, TypeError):
        return False, "session_id must be a valid integer"

def get_client_ip() -> str:
    """Get client IP address, considering proxies"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr or 'unknown'

def rate_limit(endpoint_type: str):
    """
    Decorator for rate limiting Soroban endpoints
    
    Args:
        endpoint_type: Type of endpoint for rate limiting rules
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get user and IP for rate limiting
            current_user = getattr(g, 'current_user', None)
            user_id = current_user.id if current_user else 'anonymous'
            ip_address = get_client_ip()
            
            # Get rate limit configuration
            limits = RATE_LIMITS.get(endpoint_type, {})
            per_minute = limits.get('per_minute', 60)
            per_hour = limits.get('per_hour', 1000)
            
            # Check per-minute limit
            minute_key = f"{endpoint_type}:minute:{user_id}:{ip_address}"
            allowed, retry_after = rate_limiter.is_allowed(minute_key, per_minute, 60)
            if not allowed:
                logger.warning(f"Rate limit exceeded (per-minute) for {endpoint_type}: user={user_id}, ip={ip_address}")
                return jsonify({
                    "success": False,
                    "error": f"Rate limit exceeded for {limits.get('description', endpoint_type)}",
                    "retry_after": retry_after,
                    "limit_type": "per_minute",
                    "limit": per_minute
                }), 429
            
            # Check per-hour limit
            hour_key = f"{endpoint_type}:hour:{user_id}:{ip_address}"
            allowed, retry_after = rate_limiter.is_allowed(hour_key, per_hour, 3600)
            if not allowed:
                logger.warning(f"Rate limit exceeded (per-hour) for {endpoint_type}: user={user_id}, ip={ip_address}")
                return jsonify({
                    "success": False,
                    "error": f"Rate limit exceeded for {limits.get('description', endpoint_type)}",
                    "retry_after": retry_after,
                    "limit_type": "per_hour", 
                    "limit": per_hour
                }), 429
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_soroban_request(require_contract_id=True, require_function_name=False, 
                           require_secret_key=False, require_parameters=False):
    """
    Decorator for validating Soroban request inputs
    
    Args:
        require_contract_id: Whether contract_id is required
        require_function_name: Whether function_name is required
        require_secret_key: Whether secret_key is required
        require_parameters: Whether parameters validation is required
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                data = request.get_json()
                if not data:
                    return jsonify({
                        "success": False,
                        "error": "Request body must be JSON"
                    }), 400
                
                # Validate session_id (always required)
                session_id = data.get('session_id')
                is_valid, error = validate_session_id(session_id)
                if not is_valid:
                    return jsonify({
                        "success": False,
                        "error": error
                    }), 400
                
                # Validate contract_id if required
                if require_contract_id:
                    contract_id = data.get('contract_id')
                    is_valid, error = validate_stellar_address(contract_id, 'contract_id')
                    if not is_valid:
                        return jsonify({
                            "success": False,
                            "error": error
                        }), 400
                
                # Validate function_name if required
                if require_function_name:
                    function_name = data.get('function_name')
                    is_valid, error = validate_function_name(function_name)
                    if not is_valid:
                        return jsonify({
                            "success": False,
                            "error": error
                        }), 400
                
                # Validate secret_key if required
                if require_secret_key:
                    secret_key = data.get('deployer_secret') or data.get('invoker_secret')
                    is_valid, error = validate_stellar_address(secret_key, 'secret_key')
                    if not is_valid:
                        return jsonify({
                            "success": False,
                            "error": error
                        }), 400
                
                # Validate parameters if required
                if require_parameters:
                    parameters = data.get('parameters', [])
                    is_valid, error = validate_parameters(parameters)
                    if not is_valid:
                        return jsonify({
                            "success": False,
                            "error": error
                        }), 400
                
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Validation error: {str(e)}")
                return jsonify({
                    "success": False,
                    "error": "Request validation failed"
                }), 400
        return decorated_function
    return decorator

def check_friendbot_limits():
    """
    Decorator for checking Friendbot usage limits
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                data = request.get_json()
                if not data or not data.get('fund_account', True):
                    # Friendbot not requested, proceed normally
                    return f(*args, **kwargs)
                
                # Extract account information for tracking
                secret_key = data.get('deployer_secret') or data.get('invoker_secret')
                if not secret_key:
                    return f(*args, **kwargs)  # No secret key, will fail later
                
                # Get public key from secret for account tracking
                try:
                    from stellar_sdk import Keypair
                    keypair = Keypair.from_secret(secret_key)
                    account_key = f"friendbot:account:{keypair.public_key}"
                except Exception:
                    # Invalid secret key, will fail later in validation
                    return f(*args, **kwargs)
                
                ip_address = get_client_ip()
                ip_key = f"friendbot:ip:{ip_address}"
                
                # Check limits
                allowed, usage_info = rate_limiter.check_friendbot_limit(
                    account_key, ip_key,
                    account_limit=RATE_LIMITS['friendbot']['per_account_hour'],
                    ip_limit=RATE_LIMITS['friendbot']['per_ip_hour']
                )
                
                if not allowed:
                    logger.warning(f"Friendbot limit exceeded: account={account_key}, ip={ip_key}")
                    reset_time = usage_info['reset_time']
                    retry_after = int((reset_time - datetime.now()).total_seconds())
                    
                    return jsonify({
                        "success": False,
                        "error": "Friendbot funding limit exceeded",
                        "usage": {
                            "account_requests": usage_info['account_requests'],
                            "ip_requests": usage_info['ip_requests'],
                            "account_limit": usage_info['account_limit'],
                            "ip_limit": usage_info['ip_limit'],
                            "reset_time": reset_time.isoformat(),
                            "retry_after": retry_after
                        }
                    }), 429
                
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Friendbot limit check error: {str(e)}")
                return f(*args, **kwargs)  # Don't block on errors
        return decorated_function
    return decorator

# Utility functions for getting rate limit status
def get_rate_limit_status(user_id: str, ip_address: str, endpoint_type: str) -> Dict:
    """Get current rate limit status for a user"""
    minute_key = f"{endpoint_type}:minute:{user_id}:{ip_address}"
    hour_key = f"{endpoint_type}:hour:{user_id}:{ip_address}"
    
    limits = RATE_LIMITS.get(endpoint_type, {})
    
    # Count current requests
    now = time.time()
    minute_cutoff = now - 60
    hour_cutoff = now - 3600
    
    minute_requests = len([ts for ts in rate_limiter.requests[minute_key] if ts > minute_cutoff])
    hour_requests = len([ts for ts in rate_limiter.requests[hour_key] if ts > hour_cutoff])
    
    return {
        'endpoint_type': endpoint_type,
        'description': limits.get('description', endpoint_type),
        'current_usage': {
            'per_minute': minute_requests,
            'per_hour': hour_requests
        },
        'limits': {
            'per_minute': limits.get('per_minute', 60),
            'per_hour': limits.get('per_hour', 1000)
        },
        'remaining': {
            'per_minute': max(0, limits.get('per_minute', 60) - minute_requests),
            'per_hour': max(0, limits.get('per_hour', 1000) - hour_requests)
        }
    }
