"""
Rate limiting and request validation for Soroban RPC endpoints.

Prevents abuse of Stellar testnet resources and Friendbot funding.
Implements per-user and per-IP rate limits with Redis-backed storage.
"""

import logging
import time
from functools import wraps
from typing import Optional, Tuple
from flask import request, jsonify
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Rate limit configuration
RATE_LIMITS = {
    "invoke": {
        "per_user_per_minute": 10,
        "per_user_per_hour": 100,
        "per_ip_per_minute": 20,
        "per_ip_per_hour": 200,
    },
    "deploy": {
        "per_user_per_minute": 5,
        "per_user_per_hour": 20,
        "per_ip_per_minute": 10,
        "per_ip_per_hour": 50,
    },
    "friendbot": {
        "per_account_per_hour": 3,  # Prevent Friendbot abuse
        "per_ip_per_hour": 10,
    },
    "state_query": {
        "per_user_per_minute": 30,
        "per_ip_per_minute": 60,
    }
}

# In-memory rate limit storage (use Redis in production)
_rate_limit_store = {}


def _get_client_ip() -> str:
    """Extract client IP address from request, considering proxies."""
    try:
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        elif request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        return request.remote_addr or 'unknown'
    except RuntimeError:
        # Outside request context (e.g., in tests)
        return 'test-ip'


def _get_rate_limit_key(prefix: str, identifier: str, window: str) -> str:
    """Generate a rate limit key for storage."""
    return f"ratelimit:{prefix}:{identifier}:{window}"


def _check_rate_limit(key: str, limit: int, window_seconds: int) -> Tuple[bool, Optional[int]]:
    """
    Check if a rate limit has been exceeded.
    
    Returns:
        (allowed, retry_after_seconds)
    """
    now = time.time()
    window_start = now - window_seconds
    
    # Clean up old entries
    if key in _rate_limit_store:
        _rate_limit_store[key] = [
            timestamp for timestamp in _rate_limit_store[key]
            if timestamp > window_start
        ]
    else:
        _rate_limit_store[key] = []
    
    # Check limit
    current_count = len(_rate_limit_store[key])
    if current_count >= limit:
        # Calculate retry-after
        oldest_timestamp = min(_rate_limit_store[key])
        retry_after = int(oldest_timestamp + window_seconds - now) + 1
        return False, retry_after
    
    # Record this request
    _rate_limit_store[key].append(now)
    return True, None


def rate_limit(operation: str):
    """
    Decorator to apply rate limiting to Soroban endpoints.
    
    Args:
        operation: One of 'invoke', 'deploy', 'friendbot', 'state_query'
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if operation not in RATE_LIMITS:
                logger.warning(f"Unknown rate limit operation: {operation}")
                return f(*args, **kwargs)
            
            limits = RATE_LIMITS[operation]
            client_ip = _get_client_ip()
            
            # Extract user_id from kwargs (injected by @token_required)
            current_user = kwargs.get('current_user')
            user_id = current_user.id if current_user else None
            
            # Check per-IP limits
            if "per_ip_per_minute" in limits:
                key = _get_rate_limit_key(operation, f"ip:{client_ip}", "minute")
                allowed, retry_after = _check_rate_limit(
                    key, limits["per_ip_per_minute"], 60
                )
                if not allowed:
                    logger.warning(
                        f"Rate limit exceeded for IP {client_ip} on {operation} "
                        f"(per-minute limit)"
                    )
                    return jsonify({
                        "success": False,
                        "error": "Rate limit exceeded. Please try again later.",
                        "retry_after": retry_after
                    }), 429
            
            if "per_ip_per_hour" in limits:
                key = _get_rate_limit_key(operation, f"ip:{client_ip}", "hour")
                allowed, retry_after = _check_rate_limit(
                    key, limits["per_ip_per_hour"], 3600
                )
                if not allowed:
                    logger.warning(
                        f"Rate limit exceeded for IP {client_ip} on {operation} "
                        f"(per-hour limit)"
                    )
                    return jsonify({
                        "success": False,
                        "error": "Hourly rate limit exceeded. Please try again later.",
                        "retry_after": retry_after
                    }), 429
            
            # Check per-user limits
            if user_id:
                if "per_user_per_minute" in limits:
                    key = _get_rate_limit_key(operation, f"user:{user_id}", "minute")
                    allowed, retry_after = _check_rate_limit(
                        key, limits["per_user_per_minute"], 60
                    )
                    if not allowed:
                        logger.warning(
                            f"Rate limit exceeded for user {user_id} on {operation} "
                            f"(per-minute limit)"
                        )
                        return jsonify({
                            "success": False,
                            "error": "Rate limit exceeded. Please try again later.",
                            "retry_after": retry_after
                        }), 429
                
                if "per_user_per_hour" in limits:
                    key = _get_rate_limit_key(operation, f"user:{user_id}", "hour")
                    allowed, retry_after = _check_rate_limit(
                        key, limits["per_user_per_hour"], 3600
                    )
                    if not allowed:
                        logger.warning(
                            f"Rate limit exceeded for user {user_id} on {operation} "
                            f"(per-hour limit)"
                        )
                        return jsonify({
                            "success": False,
                            "error": "Hourly rate limit exceeded. Please try again later.",
                            "retry_after": retry_after
                        }), 429
            
            return f(*args, **kwargs)
        
        return wrapped
    return decorator


def validate_stellar_address(address: str, address_type: str = "account") -> Tuple[bool, Optional[str]]:
    """
    Validate a Stellar address format.
    
    Args:
        address: The address to validate
        address_type: 'account' (G...), 'contract' (C...), or 'muxed' (M...)
    
    Returns:
        (is_valid, error_message)
    """
    if not address or not isinstance(address, str):
        return False, "Address must be a non-empty string"
    
    address = address.strip()
    
    # Check length (Stellar addresses are 56 characters)
    if len(address) != 56:
        return False, f"Invalid address length: expected 56, got {len(address)}"
    
    # Check prefix
    valid_prefixes = {
        "account": "G",
        "contract": "C",
        "muxed": "M",
    }
    
    expected_prefix = valid_prefixes.get(address_type)
    if expected_prefix and not address.startswith(expected_prefix):
        return False, f"Invalid address prefix: expected '{expected_prefix}', got '{address[0]}'"
    
    # Check character set (base32)
    valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")
    if not all(c in valid_chars for c in address):
        return False, "Address contains invalid characters (must be base32)"
    
    # Additional validation using stellar-sdk if available
    try:
        from stellar_sdk import StrKey
        
        if address_type == "account":
            if not StrKey.is_valid_ed25519_public_key(address):
                return False, "Invalid account address (checksum failed)"
        elif address_type == "contract":
            if not StrKey.is_valid_contract(address):
                return False, "Invalid contract address (checksum failed)"
        elif address_type == "muxed":
            if not StrKey.is_valid_muxed_account(address):
                return False, "Invalid muxed address (checksum failed)"
    
    except ImportError:
        # stellar-sdk not available, basic validation only
        logger.debug("stellar-sdk not available for address validation")
    except Exception as e:
        return False, f"Address validation error: {str(e)}"
    
    return True, None


def validate_contract_function_name(function_name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a Soroban contract function name.
    
    Returns:
        (is_valid, error_message)
    """
    if not function_name or not isinstance(function_name, str):
        return False, "Function name must be a non-empty string"
    
    function_name = function_name.strip()
    
    # Check length
    if len(function_name) == 0:
        return False, "Function name cannot be empty"
    
    if len(function_name) > 64:
        return False, f"Function name too long: max 64 characters, got {len(function_name)}"
    
    # Check character set (alphanumeric + underscore)
    if not function_name.replace('_', '').isalnum():
        return False, "Function name must contain only alphanumeric characters and underscores"
    
    # Check doesn't start with number
    if function_name[0].isdigit():
        return False, "Function name cannot start with a number"
    
    return True, None


def validate_parameter_list(parameters: list, max_params: int = 10) -> Tuple[bool, Optional[str]]:
    """
    Validate a list of contract function parameters.
    
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(parameters, list):
        return False, "Parameters must be a list"
    
    if len(parameters) > max_params:
        return False, f"Too many parameters: max {max_params}, got {len(parameters)}"
    
    for i, param in enumerate(parameters):
        if not isinstance(param, str):
            return False, f"Parameter {i} must be a string"
        
        if len(param) > 1000:
            return False, f"Parameter {i} too long: max 1000 characters"
    
    return True, None


def track_friendbot_usage(public_key: str) -> Tuple[bool, Optional[str]]:
    """
    Track and limit Friendbot funding requests per account.
    
    Returns:
        (allowed, error_message)
    """
    limits = RATE_LIMITS["friendbot"]
    client_ip = _get_client_ip()
    
    # Check per-account limit
    key = _get_rate_limit_key("friendbot", f"account:{public_key}", "hour")
    allowed, retry_after = _check_rate_limit(
        key, limits["per_account_per_hour"], 3600
    )
    if not allowed:
        return False, f"Friendbot limit exceeded for this account. Retry in {retry_after}s."
    
    # Check per-IP limit
    key = _get_rate_limit_key("friendbot", f"ip:{client_ip}", "hour")
    allowed, retry_after = _check_rate_limit(
        key, limits["per_ip_per_hour"], 3600
    )
    if not allowed:
        return False, f"Friendbot limit exceeded for your IP. Retry in {retry_after}s."
    
    return True, None


def get_rate_limit_stats(operation: str, user_id: Optional[int] = None) -> dict:
    """
    Get current rate limit statistics for monitoring.
    
    Returns:
        Dictionary with current usage and limits
    """
    if operation not in RATE_LIMITS:
        return {}
    
    limits = RATE_LIMITS[operation]
    client_ip = _get_client_ip()
    stats = {
        "operation": operation,
        "limits": limits,
        "current_usage": {}
    }
    
    # Get IP usage
    if "per_ip_per_minute" in limits:
        key = _get_rate_limit_key(operation, f"ip:{client_ip}", "minute")
        count = len(_rate_limit_store.get(key, []))
        stats["current_usage"]["ip_per_minute"] = {
            "count": count,
            "limit": limits["per_ip_per_minute"],
            "remaining": max(0, limits["per_ip_per_minute"] - count)
        }
    
    # Get user usage
    if user_id and "per_user_per_minute" in limits:
        key = _get_rate_limit_key(operation, f"user:{user_id}", "minute")
        count = len(_rate_limit_store.get(key, []))
        stats["current_usage"]["user_per_minute"] = {
            "count": count,
            "limit": limits["per_user_per_minute"],
            "remaining": max(0, limits["per_user_per_minute"] - count)
        }
    
    return stats
