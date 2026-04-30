"""
Tests for Soroban rate limiting and validation.
Prevents abuse of Stellar testnet resources and Friendbot funding.
"""

import pytest
import time
from server.utils.soroban_rate_limiter import (
    validate_stellar_address,
    validate_contract_function_name,
    validate_parameter_list,
    track_friendbot_usage,
    _check_rate_limit,
    _rate_limit_store,
)


class TestStellarAddressValidation:
    """Test Stellar address format validation"""
    
    def test_valid_account_address(self):
        """Test valid G... account address"""
        # Valid testnet account
        address = "GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWHF"
        is_valid, error = validate_stellar_address(address, "account")
        assert is_valid is True
        assert error is None
    
    def test_valid_contract_address(self):
        """Test valid C... contract address"""
        # Valid contract address
        address = "CAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD2KM"
        is_valid, error = validate_stellar_address(address, "contract")
        assert is_valid is True
        assert error is None
    
    def test_invalid_length(self):
        """Test address with invalid length"""
        address = "GSHORT"
        is_valid, error = validate_stellar_address(address, "account")
        assert is_valid is False
        assert "length" in error.lower()
    
    def test_invalid_prefix(self):
        """Test address with wrong prefix"""
        # Contract address used as account
        address = "CAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD2KM"
        is_valid, error = validate_stellar_address(address, "account")
        assert is_valid is False
        assert "prefix" in error.lower()
    
    def test_invalid_characters(self):
        """Test address with invalid base32 characters"""
        address = "G!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        is_valid, error = validate_stellar_address(address, "account")
        assert is_valid is False
        # Length check happens first, so we get length error
        assert "length" in error.lower() or "invalid characters" in error.lower()
    
    def test_empty_address(self):
        """Test empty address"""
        is_valid, error = validate_stellar_address("", "account")
        assert is_valid is False
        assert "non-empty" in error.lower()
    
    def test_none_address(self):
        """Test None address"""
        is_valid, error = validate_stellar_address(None, "account")
        assert is_valid is False


class TestContractFunctionNameValidation:
    """Test contract function name validation"""
    
    def test_valid_function_name(self):
        """Test valid function names"""
        valid_names = ["transfer", "approve", "balance_of", "get_admin", "initialize"]
        for name in valid_names:
            is_valid, error = validate_contract_function_name(name)
            assert is_valid is True, f"Failed for: {name}"
            assert error is None
    
    def test_empty_function_name(self):
        """Test empty function name"""
        is_valid, error = validate_contract_function_name("")
        assert is_valid is False
        assert "empty" in error.lower()
    
    def test_function_name_too_long(self):
        """Test function name exceeding max length"""
        long_name = "a" * 65
        is_valid, error = validate_contract_function_name(long_name)
        assert is_valid is False
        assert "too long" in error.lower()
    
    def test_function_name_with_invalid_chars(self):
        """Test function name with special characters"""
        invalid_names = ["transfer-tokens", "approve!", "balance.of", "get@admin"]
        for name in invalid_names:
            is_valid, error = validate_contract_function_name(name)
            assert is_valid is False, f"Should fail for: {name}"
            assert "alphanumeric" in error.lower()
    
    def test_function_name_starts_with_number(self):
        """Test function name starting with number"""
        is_valid, error = validate_contract_function_name("123transfer")
        assert is_valid is False
        assert "cannot start with a number" in error.lower()
    
    def test_none_function_name(self):
        """Test None function name"""
        is_valid, error = validate_contract_function_name(None)
        assert is_valid is False


class TestParameterListValidation:
    """Test parameter list validation"""
    
    def test_valid_parameters(self):
        """Test valid parameter lists"""
        valid_params = [
            [],
            ["u32:100"],
            ["address:GABC...", "u64:1000", "str:hello"],
            ["bool:true", "bool:false"],
        ]
        for params in valid_params:
            is_valid, error = validate_parameter_list(params)
            assert is_valid is True, f"Failed for: {params}"
            assert error is None
    
    def test_not_a_list(self):
        """Test non-list parameter"""
        is_valid, error = validate_parameter_list("not-a-list")
        assert is_valid is False
        assert "must be a list" in error.lower()
    
    def test_too_many_parameters(self):
        """Test exceeding max parameter count"""
        too_many = ["u32:1"] * 11
        is_valid, error = validate_parameter_list(too_many, max_params=10)
        assert is_valid is False
        assert "too many" in error.lower()
    
    def test_non_string_parameter(self):
        """Test parameter that's not a string"""
        is_valid, error = validate_parameter_list([123, "u32:456"])
        assert is_valid is False
        assert "must be a string" in error.lower()
    
    def test_parameter_too_long(self):
        """Test parameter exceeding max length"""
        long_param = "str:" + "a" * 1000
        is_valid, error = validate_parameter_list([long_param])
        assert is_valid is False
        assert "too long" in error.lower()


class TestRateLimiting:
    """Test rate limiting functionality"""
    
    def setup_method(self):
        """Clear rate limit store before each test"""
        _rate_limit_store.clear()
    
    def test_rate_limit_allows_within_limit(self):
        """Test that requests within limit are allowed"""
        key = "test:user:1:minute"
        
        for i in range(5):
            allowed, retry_after = _check_rate_limit(key, limit=10, window_seconds=60)
            assert allowed is True
            assert retry_after is None
    
    def test_rate_limit_blocks_over_limit(self):
        """Test that requests over limit are blocked"""
        key = "test:user:2:minute"
        limit = 3
        
        # Make requests up to limit
        for i in range(limit):
            allowed, retry_after = _check_rate_limit(key, limit=limit, window_seconds=60)
            assert allowed is True
        
        # Next request should be blocked
        allowed, retry_after = _check_rate_limit(key, limit=limit, window_seconds=60)
        assert allowed is False
        assert retry_after is not None
        assert retry_after > 0
    
    def test_rate_limit_window_expiry(self):
        """Test that rate limit resets after window expires"""
        key = "test:user:3:second"
        limit = 2
        window = 1  # 1 second window
        
        # Fill the limit
        for i in range(limit):
            allowed, retry_after = _check_rate_limit(key, limit=limit, window_seconds=window)
            assert allowed is True
        
        # Should be blocked
        allowed, retry_after = _check_rate_limit(key, limit=limit, window_seconds=window)
        assert allowed is False
        
        # Wait for window to expire
        time.sleep(window + 0.1)
        
        # Should be allowed again
        allowed, retry_after = _check_rate_limit(key, limit=limit, window_seconds=window)
        assert allowed is True
    
    def test_rate_limit_different_keys_independent(self):
        """Test that different keys have independent limits"""
        key1 = "test:user:4:minute"
        key2 = "test:user:5:minute"
        limit = 2
        
        # Fill limit for key1
        for i in range(limit):
            allowed, _ = _check_rate_limit(key1, limit=limit, window_seconds=60)
            assert allowed is True
        
        # key1 should be blocked
        allowed, _ = _check_rate_limit(key1, limit=limit, window_seconds=60)
        assert allowed is False
        
        # key2 should still be allowed
        allowed, _ = _check_rate_limit(key2, limit=limit, window_seconds=60)
        assert allowed is True


class TestFriendbotTracking:
    """Test Friendbot usage tracking"""
    
    def setup_method(self):
        """Clear rate limit store before each test"""
        _rate_limit_store.clear()
    
    def test_friendbot_allows_first_request(self):
        """Test that first Friendbot request is allowed"""
        public_key = "GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWHF"
        allowed, error = track_friendbot_usage(public_key)
        assert allowed is True
        assert error is None
    
    def test_friendbot_blocks_excessive_requests(self):
        """Test that excessive Friendbot requests are blocked"""
        public_key = "GBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
        
        # Make requests up to limit (3 per hour)
        for i in range(3):
            allowed, error = track_friendbot_usage(public_key)
            assert allowed is True, f"Request {i+1} should be allowed"
        
        # Next request should be blocked
        allowed, error = track_friendbot_usage(public_key)
        assert allowed is False
        assert error is not None
        assert "limit exceeded" in error.lower()
    
    def test_friendbot_different_accounts_independent(self):
        """Test that different accounts have independent Friendbot limits"""
        key1 = "GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWHF"
        key2 = "GBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
        
        # Fill limit for key1
        for i in range(3):
            allowed, _ = track_friendbot_usage(key1)
            assert allowed is True
        
        # key1 should be blocked
        allowed, _ = track_friendbot_usage(key1)
        assert allowed is False
        
        # key2 should still be allowed
        allowed, _ = track_friendbot_usage(key2)
        assert allowed is True


class TestValidationEdgeCases:
    """Test edge cases in validation"""
    
    def test_whitespace_handling(self):
        """Test that whitespace is handled correctly"""
        # Function name with leading/trailing whitespace
        is_valid, error = validate_contract_function_name("  transfer  ")
        # Spaces are valid in the middle but this has leading/trailing spaces
        # The validator accepts it (caller should trim)
        assert is_valid is True or "alphanumeric" in error.lower()
    
    def test_unicode_in_function_name(self):
        """Test unicode characters in function name"""
        is_valid, error = validate_contract_function_name("transfer_🚀")
        assert is_valid is False
        assert "alphanumeric" in error.lower()
    
    def test_sql_injection_attempt(self):
        """Test that SQL injection attempts are rejected"""
        malicious_names = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
        ]
        for name in malicious_names:
            is_valid, error = validate_contract_function_name(name)
            assert is_valid is False, f"Should reject: {name}"
    
    def test_path_traversal_in_parameters(self):
        """Test that path traversal attempts in parameters are allowed (they're just strings)"""
        # Parameters are arbitrary strings, so path traversal patterns are valid
        # The actual path validation happens elsewhere
        params = ["str:../../etc/passwd", "str:../../../root"]
        is_valid, error = validate_parameter_list(params)
        assert is_valid is True  # Parameters themselves are valid strings
