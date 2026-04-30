#!/usr/bin/env python3
"""
Security Implementation Verification Script
Verifies that all security components are working correctly
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_rate_limiter():
    """Test rate limiting functionality"""
    print("Testing Rate Limiter...")
    
    try:
        from middleware.rate_limiter import MemoryRateLimiter, RATE_LIMITS
        
        # Test basic functionality
        limiter = MemoryRateLimiter()
        allowed, retry_after = limiter.is_allowed('test_key', 5, 60)
        assert allowed == True
        assert retry_after == 0
        
        # Test rate limit configuration
        assert 'soroban_invoke' in RATE_LIMITS
        assert 'soroban_deploy' in RATE_LIMITS
        assert 'friendbot' in RATE_LIMITS
        
        print("  Rate Limiter: PASSED")
        return True
    except Exception as e:
        print(f"  Rate Limiter: FAILED - {e}")
        return False

def test_validation():
    """Test input validation functionality"""
    print("Testing Input Validation...")
    
    try:
        from middleware.rate_limiter import (
            validate_stellar_address, validate_function_name, 
            validate_parameters, validate_session_id
        )
        
        # Test Stellar address validation
        valid_key = 'G' + 'A' * 55
        valid, error = validate_stellar_address(valid_key, 'public_key')
        assert valid == True
        assert error == ""
        
        # Test function name validation
        valid, error = validate_function_name('test_function')
        assert valid == True
        assert error == ""
        
        # Test parameter validation
        valid, error = validate_parameters(['u32:42', 'str:hello'])
        assert valid == True
        assert error == ""
        
        # Test session ID validation
        valid, error = validate_session_id(123)
        assert valid == True
        assert error == ""
        
        print("  Input Validation: PASSED")
        return True
    except Exception as e:
        print(f"  Input Validation: FAILED - {e}")
        return False

def test_friendbot_limits():
    """Test Friendbot limit functionality"""
    print("Testing Friendbot Limits...")
    
    try:
        from middleware.rate_limiter import MemoryRateLimiter
        
        limiter = MemoryRateLimiter()
        allowed, usage = limiter.check_friendbot_limit(
            'test_account', 'test_ip', account_limit=3, ip_limit=10
        )
        assert allowed == True
        assert usage['account_requests'] == 1
        assert usage['ip_requests'] == 1
        
        print("  Friendbot Limits: PASSED")
        return True
    except Exception as e:
        print(f"  Friendbot Limits: FAILED - {e}")
        return False

def test_error_handlers():
    """Test error handling functionality"""
    print("Testing Error Handlers...")
    
    try:
        # Try importing error handlers
        from utils.error_handlers import (
            SecurityError, RateLimitError, ValidationError,
            sanitize_error_message, create_error_response
        )
        
        # Test error classes
        error = SecurityError("Test error", "TEST_ERROR", 400)
        assert error.message == "Test error"
        assert error.error_code == "TEST_ERROR"
        
        rate_error = RateLimitError("Rate limit exceeded", 60)
        assert rate_error.retry_after == 60
        
        validation_error = ValidationError("Invalid input", "field", "value")
        assert validation_error.field == "field"
        
        # Test utility functions
        sanitized = sanitize_error_message("password=secret123")
        assert "[REDACTED]" in sanitized
        assert "secret123" not in sanitized
        
        response, status = create_error_response("TEST_ERROR", "Test message", 400)
        assert status == 400
        
        print("  Error Handlers: PASSED")
        return True
    except Exception as e:
        print(f"  Error Handlers: FAILED - {e}")
        return False

def test_decorators():
    """Test security decorators"""
    print("Testing Security Decorators...")
    
    try:
        from middleware.rate_limiter import (
            rate_limit, validate_soroban_request, check_friendbot_limits
        )
        
        # Test that decorators are callable
        assert callable(rate_limit)
        assert callable(validate_soroban_request)
        assert callable(check_friendbot_limits)
        
        print("  Security Decorators: PASSED")
        return True
    except Exception as e:
        print(f"  Security Decorators: FAILED - {e}")
        return False

def test_breach_detection():
    """Test breach detection functionality"""
    print("Testing Breach Detection...")
    
    try:
        from utils.error_handlers import RateLimitBreachDetector
        
        detector = RateLimitBreachDetector(threshold=3, window_minutes=1)
        
        # Test recording attempts
        result = detector.record_attempt("user1", "192.168.1.1")
        assert result == False  # Should not trigger breach initially
        
        # Add more attempts
        detector.record_attempt("user1", "192.168.1.1")
        detector.record_attempt("user1", "192.168.1.1")
        
        # Should trigger breach on threshold
        result = detector.record_attempt("user1", "192.168.1.1")
        assert result == True
        
        print("  Breach Detection: PASSED")
        return True
    except Exception as e:
        print(f"  Breach Detection: FAILED - {e}")
        return False

def main():
    """Run all security tests"""
    print("=" * 60)
    print("SECURITY IMPLEMENTATION VERIFICATION")
    print("=" * 60)
    
    tests = [
        test_rate_limiter,
        test_validation,
        test_friendbot_limits,
        test_error_handlers,
        test_decorators,
        test_breach_detection
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 60)
    print(f"VERIFICATION RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("ALL SECURITY COMPONENTS ARE FUNCTIONAL!")
        print("DoS protection, input validation, and monitoring are ACTIVE.")
    else:
        print("Some components may need attention.")
    
    print("=" * 60)
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
