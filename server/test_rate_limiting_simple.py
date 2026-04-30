"""
Simple test script to verify rate limiting implementation
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from middleware.rate_limiter import (
    MemoryRateLimiter, validate_stellar_address, 
    validate_function_name, validate_parameters
)

def test_basic_functionality():
    """Test basic rate limiting and validation functions"""
    print("Testing basic rate limiting functionality...")
    
    # Test rate limiter
    limiter = MemoryRateLimiter()
    
    # Test basic rate limiting
    key = "test_key"
    limit = 3
    
    print(f"Testing rate limit with limit={limit}")
    
    # Should allow first few requests
    for i in range(limit):
        allowed, retry_after = limiter.is_allowed(key, limit, 60)
        assert allowed is True, f"Request {i+1} should be allowed"
        print(f"Request {i+1}: Allowed")
    
    # Should block when limit exceeded
    allowed, retry_after = limiter.is_allowed(key, limit, 60)
    assert allowed is False, "Request should be blocked when limit exceeded"
    print(f"Request {limit+1}: Blocked (retry_after={retry_after})")
    
    print("Rate limiting test passed!")
    
    # Test Stellar address validation
    print("\nTesting Stellar address validation...")
    
    # Valid addresses (56 characters total: 1 prefix + 55 alphanumeric)
    valid_cases = [
        ("GABCDEF123456789ABCDEF123456789ABCDEF123456789ABCDEF1234", "public_key"),
        ("CABCDEF123456789ABCDEF123456789ABCDEF123456789ABCDEF1234", "contract_id"),
        ("SABCDEF123456789ABCDEF123456789ABCDEF123456789ABCDEF1234", "secret_key")
    ]
    
    for address, address_type in valid_cases:
        print(f"Testing {address_type}: {address} (length: {len(address)})")
        is_valid, error = validate_stellar_address(address, address_type)
        print(f"Result: {is_valid}, Error: {error}")
        assert is_valid is True, f"Valid {address_type} should pass validation"
        print(f"Valid {address_type}: Passed")
    
    # Invalid addresses
    invalid_cases = [
        ("INVALID", "public_key"),
        ("", "contract_id"),
        ("G123", "secret_key")
    ]
    
    for address, address_type in invalid_cases:
        is_valid, error = validate_stellar_address(address, address_type)
        assert is_valid is False, f"Invalid {address_type} should fail validation"
        print(f"Invalid {address_type}: Failed as expected")
    
    print("Stellar address validation test passed!")
    
    # Test function name validation
    print("\nTesting function name validation...")
    
    valid_functions = ["init", "transfer", "get_balance", "my_function"]
    for func in valid_functions:
        is_valid, error = validate_function_name(func)
        assert is_valid is True, f"Valid function name '{func}' should pass"
        print(f"Function '{func}': Passed")
    
    invalid_functions = ["", "123invalid", "invalid-name", "a" * 65]
    for func in invalid_functions:
        is_valid, error = validate_function_name(func)
        assert is_valid is False, f"Invalid function name should fail"
        print(f"Function '{func}': Failed as expected")
    
    print("Function name validation test passed!")
    
    # Test parameter validation
    print("\nTesting parameter validation...")
    
    valid_params = ["u32:42", "address:GABC123...", "str:hello", "bool:true"]
    is_valid, error = validate_parameters(valid_params)
    assert is_valid is True, "Valid parameters should pass"
    print("Valid parameters: Passed")
    
    invalid_params = "not a list"
    is_valid, error = validate_parameters(invalid_params)
    assert is_valid is False, "Invalid parameters should fail"
    print("Invalid parameters: Failed as expected")
    
    print("Parameter validation test passed!")

def test_friendbot_limits():
    """Test Friendbot usage limits"""
    print("\nTesting Friendbot limits...")
    
    limiter = MemoryRateLimiter()
    account_key = "friendbot:account:GABC123..."
    ip_key = "friendbot:ip:192.168.1.1"
    
    # Should allow first few requests
    for i in range(3):
        allowed, usage = limiter.check_friendbot_limit(account_key, ip_key)
        assert allowed is True, f"Friendbot request {i+1} should be allowed"
        print(f"Friendbot request {i+1}: Allowed (account_requests={usage['account_requests']})")
    
    # Should block account limit
    allowed, usage = limiter.check_friendbot_limit(account_key, ip_key)
    assert allowed is False, "Friendbot request should be blocked when account limit exceeded"
    print(f"Friendbot request 4: Blocked (account_requests={usage['account_requests']}, limit={usage['account_limit']})")
    
    print("Friendbot limits test passed!")

if __name__ == "__main__":
    try:
        test_basic_functionality()
        test_friendbot_limits()
        print("\n" + "="*50)
        print("All tests passed! Rate limiting implementation is working correctly.")
        print("="*50)
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        sys.exit(1)
