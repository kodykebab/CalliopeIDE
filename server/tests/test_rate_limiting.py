"""
Comprehensive tests for rate limiting and validation middleware
Addresses HIGH PRIORITY security issue #100
"""

import pytest
import time
import json
from unittest.mock import Mock, patch, MagicMock
from flask import Flask, g
from server.middleware.rate_limiter import (
    MemoryRateLimiter, rate_limit, validate_soroban_request,
    check_friendbot_limits, validate_stellar_address,
    validate_function_name, validate_parameters, validate_session_id,
    get_client_ip, get_rate_limit_status, RATE_LIMITS
)
from server.models import User


class TestMemoryRateLimiter:
    """Test the in-memory rate limiter implementation"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.limiter = MemoryRateLimiter()
    
    def test_is_allowed_basic(self):
        """Test basic rate limiting functionality"""
        key = "test_key"
        limit = 5
        window = 60
        
        # Should allow first request
        allowed, retry_after = self.limiter.is_allowed(key, limit, window)
        assert allowed is True
        assert retry_after == 0
        
        # Should allow up to limit
        for i in range(limit - 1):
            allowed, retry_after = self.limiter.is_allowed(key, limit, window)
            assert allowed is True
            assert retry_after == 0
        
        # Should block when limit exceeded
        allowed, retry_after = self.limiter.is_allowed(key, limit, window)
        assert allowed is False
        assert retry_after > 0
    
    def test_window_reset(self):
        """Test that rate limit window resets properly"""
        key = "test_key"
        limit = 3
        window = 1  # 1 second window
        
        # Use up limit
        for i in range(limit):
            allowed, retry_after = self.limiter.is_allowed(key, limit, window)
            assert allowed is True
        
        # Should be blocked
        allowed, retry_after = self.limiter.is_allowed(key, limit, window)
        assert allowed is False
        
        # Wait for window to reset
        time.sleep(1.1)
        
        # Should be allowed again
        allowed, retry_after = self.limiter.is_allowed(key, limit, window)
        assert allowed is True
    
    def test_friendbot_limits(self):
        """Test Friendbot usage limits"""
        account_key = "friendbot:account:GABC123..."
        ip_key = "friendbot:ip:192.168.1.1"
        
        # Should allow first few requests
        for i in range(3):
            allowed, usage = self.limiter.check_friendbot_limit(account_key, ip_key)
            assert allowed is True
            assert usage['account_requests'] == i + 1
            assert usage['ip_requests'] == i + 1
        
        # Should block account limit
        allowed, usage = self.limiter.check_friendbot_limit(account_key, ip_key)
        assert allowed is False
        assert usage['account_requests'] == 3
        assert usage['account_limit'] == 3


class TestValidationFunctions:
    """Test input validation functions"""
    
    def test_validate_stellar_address(self):
        """Test Stellar address validation"""
        # Valid public key
        is_valid, error = validate_stellar_address("GABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890", "public_key")
        assert is_valid is True
        assert error == ""
        
        # Invalid public key format
        is_valid, error = validate_stellar_address("INVALID", "public_key")
        assert is_valid is False
        assert "Invalid public_key format" in error
        
        # Empty address
        is_valid, error = validate_stellar_address("", "public_key")
        assert is_valid is False
        assert "public_key is required" in error
        
        # Valid contract ID
        is_valid, error = validate_stellar_address("CABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890", "contract_id")
        assert is_valid is True
        
        # Valid secret key
        is_valid, error = validate_stellar_address("SABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890", "secret_key")
        assert is_valid is True
    
    def test_validate_function_name(self):
        """Test function name validation"""
        # Valid function names
        valid_names = ["init", "transfer", "get_balance", "my_function", "_private"]
        for name in valid_names:
            is_valid, error = validate_function_name(name)
            assert is_valid is True
            assert error == ""
        
        # Invalid function names
        invalid_cases = [
            ("", "function_name cannot be empty"),
            ("123invalid", "must start with a letter or underscore"),
            ("invalid-name", "must contain only letters, numbers, and underscores"),
            ("a" * 65, "must be 64 characters or less"),
            (None, "must be a string")
        ]
        
        for name, expected_error in invalid_cases:
            is_valid, error = validate_function_name(name)
            assert is_valid is False
            assert expected_error in error
    
    def test_validate_parameters(self):
        """Test parameter validation"""
        # Valid parameters
        valid_params = ["u32:42", "address:GABC123...", "str:hello", "bool:true"]
        is_valid, error = validate_parameters(valid_params)
        assert is_valid is True
        
        # Invalid parameters
        invalid_cases = [
            ("not a list", "must be a list"),
            (["param"] * 21, "Too many parameters"),
            ([""], "Parameter 0 must be a string"),
            (["x" * 1001], "Parameter 0 is too long")
        ]
        
        for params, expected_error in invalid_cases:
            is_valid, error = validate_parameters(params)
            assert is_valid is False
            assert expected_error in error
    
    def test_validate_session_id(self):
        """Test session ID validation"""
        # Valid session IDs
        valid_ids = [1, 42, "123", 999]
        for session_id in valid_ids:
            is_valid, error = validate_session_id(session_id)
            assert is_valid is True
        
        # Invalid session IDs
        invalid_cases = [
            (None, "session_id is required"),
            (0, "must be a positive integer"),
            (-1, "must be a positive integer"),
            ("abc", "must be a valid integer"),
            ("", "session_id is required")
        ]
        
        for session_id, expected_error in invalid_cases:
            is_valid, error = validate_session_id(session_id)
            assert is_valid is False
            assert expected_error in error


class TestRateLimitingDecorators:
    """Test rate limiting decorators"""
    
    def setup_method(self):
        """Set up Flask app for testing decorators"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Mock user for testing
        self.mock_user = Mock()
        self.mock_user.id = 123
        self.mock_user.username = "testuser"
    
    @patch('server.middleware.rate_limiter.get_client_ip')
    @patch('server.middleware.rate_limiter.rate_limiter')
    def test_rate_limit_decorator_allowed(self, mock_limiter, mock_get_ip):
        """Test rate limit decorator when request is allowed"""
        mock_limiter.is_allowed.return_value = (True, 0)
        mock_get_ip.return_value = "127.0.0.1"
        
        @self.app.route('/test')
        @rate_limit('soroban_invoke')
        def test_route():
            return jsonify({"success": True})
        
        with self.app.test_request_context():
            # Set up mock user in g
            g.current_user = self.mock_user
            
            response = self.client.get('/test')
            assert response.status_code == 200
    
    @patch('server.middleware.rate_limiter.get_client_ip')
    @patch('server.middleware.rate_limiter.rate_limiter')
    def test_rate_limit_decorator_blocked(self, mock_limiter, mock_get_ip):
        """Test rate limit decorator when request is blocked"""
        mock_limiter.is_allowed.return_value = (False, 30)
        mock_get_ip.return_value = "127.0.0.1"
        
        @self.app.route('/test')
        @rate_limit('soroban_invoke')
        def test_route():
            return jsonify({"success": True})
        
        with self.app.test_request_context():
            g.current_user = self.mock_user
            
            response = self.client.get('/test')
            assert response.status_code == 429
            
            data = json.loads(response.data)
            assert data['success'] is False
            assert 'Rate limit exceeded' in data['error']
            assert data['retry_after'] == 30
    
    def test_validate_soroban_request_decorator(self):
        """Test request validation decorator"""
        @self.app.route('/test', methods=['POST'])
        @validate_soroban_request(
            require_contract_id=True,
            require_function_name=True,
            require_secret_key=True,
            require_parameters=True
        )
        def test_route():
            return jsonify({"success": True})
        
        # Valid request
        valid_data = {
            "session_id": 123,
            "contract_id": "CABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890",
            "function_name": "test_function",
            "invoker_secret": "SABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890",
            "parameters": ["u32:42", "str:hello"]
        }
        
        response = self.client.post('/test', json=valid_data)
        assert response.status_code == 200
        
        # Invalid request - missing fields
        invalid_data = {"session_id": 123}
        response = self.client.post('/test', json=invalid_data)
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert data['success'] is False
    
    @patch('server.middleware.rate_limiter.rate_limiter')
    @patch('server.middleware.rate_limiter.get_client_ip')
    def test_friendbot_limits_decorator(self, mock_get_ip, mock_limiter):
        """Test Friendbot limits decorator"""
        mock_limiter.check_friendbot_limit.return_value = (True, {
            'account_requests': 1,
            'ip_requests': 1,
            'account_limit': 3,
            'ip_limit': 10
        })
        mock_get_ip.return_value = "127.0.0.1"
        
        @self.app.route('/test', methods=['POST'])
        @check_friendbot_limits()
        def test_route():
            return jsonify({"success": True})
        
        # Request with fund_account=True should trigger friendbot check
        data = {
            "session_id": 123,
            "fund_account": True,
            "invoker_secret": "SABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890"
        }
        
        with self.app.test_request_context():
            g.current_user = self.mock_user
            
            response = self.client.post('/test', json=data)
            assert response.status_code == 200
            
            # Verify friendbot limit was checked
            mock_limiter.check_friendbot_limit.assert_called_once()


class TestIntegration:
    """Integration tests for the complete rate limiting system"""
    
    def setup_method(self):
        """Set up integration test environment"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        # Initialize rate limiter
        from server.middleware.rate_limiter import rate_limiter
        rate_limiter.requests.clear()
        rate_limiter.friendbot_usage.clear()
    
    def test_rate_limit_status_endpoint(self):
        """Test rate limit status endpoint"""
        @self.app.route('/api/rate-limits')
        def mock_rate_limits_status():
            mock_user = Mock()
            mock_user.id = 123
            return get_rate_limit_status(str(mock_user.id), "127.0.0.1", "soroban_invoke")
        
        with self.app.test_client() as client:
            response = client.get('/api/rate-limits')
            assert response.status_code == 200
            
            data = json.loads(response.data)
            assert 'endpoint_type' in data
            assert 'description' in data
            assert 'current_usage' in data
            assert 'limits' in data
            assert 'remaining' in data
    
    def test_multiple_rate_limits(self):
        """Test that different endpoints have independent rate limits"""
        from server.middleware.rate_limiter import rate_limiter
        
        # Make requests to different endpoints
        user_id = "test_user"
        ip = "127.0.0.1"
        
        # Use up invoke limit
        for i in range(10):  # soroban_invoke limit is 10/min
            key = f"soroban_invoke:minute:{user_id}:{ip}"
            allowed, _ = rate_limiter.is_allowed(key, 10, 60)
            assert allowed is True
        
        # Should be blocked for invoke but not for deploy
        invoke_key = f"soroban_invoke:minute:{user_id}:{ip}"
        deploy_key = f"soroban_deploy:minute:{user_id}:{ip}"
        
        invoke_allowed, _ = rate_limiter.is_allowed(invoke_key, 10, 60)
        deploy_allowed, _ = rate_limiter.is_allowed(deploy_key, 5, 60)
        
        assert invoke_allowed is False
        assert deploy_allowed is True
    
    def test_rate_limit_configurations(self):
        """Test that rate limit configurations are properly set"""
        expected_endpoints = ['soroban_invoke', 'soroban_deploy', 'soroban_compile', 'soroban_state', 'friendbot']
        
        for endpoint in expected_endpoints:
            assert endpoint in RATE_LIMITS
            limits = RATE_LIMITS[endpoint]
            
            if endpoint == 'friendbot':
                assert 'per_account_hour' in limits
                assert 'per_ip_hour' in limits
            else:
                assert 'per_minute' in limits
                assert 'per_hour' in limits
                assert limits['per_minute'] > 0
                assert limits['per_hour'] > 0


class TestSecurityFeatures:
    """Test security-specific features"""
    
    def test_ip_address_extraction(self):
        """Test IP address extraction from various sources"""
        # Test with X-Forwarded-For header
        with patch('server.middleware.rate_limiter.request') as mock_request:
            mock_request.headers = {'X-Forwarded-For': '192.168.1.1, 10.0.0.1'}
            mock_request.remote_addr = '127.0.0.1'
            
            ip = get_client_ip()
            assert ip == '192.168.1.1'
        
        # Test with X-Real-IP header
        with patch('server.middleware.rate_limiter.request') as mock_request:
            mock_request.headers = {'X-Real-IP': '192.168.1.2'}
            mock_request.remote_addr = '127.0.0.1'
            mock_request.headers.get.side_effect = lambda key, default=None: mock_request.headers.get(key, default)
            
            ip = get_client_ip()
            assert ip == '192.168.1.2'
        
        # Test fallback to remote_addr
        with patch('server.middleware.rate_limiter.request') as mock_request:
            mock_request.headers = {}
            mock_request.remote_addr = '127.0.0.1'
            mock_request.headers.get.side_effect = lambda key, default=None: mock_request.headers.get(key, default)
            
            ip = get_client_ip()
            assert ip == '127.0.0.1'
    
    def test_input_sanitization(self):
        """Test that inputs are properly sanitized"""
        # Test SQL injection attempts in function names
        dangerous_names = [
            "'; DROP TABLE users; --",
            "'; UPDATE users SET password='hacked'; --",
            "<script>alert('xss')</script>",
            "../../etc/passwd"
        ]
        
        for name in dangerous_names:
            is_valid, error = validate_function_name(name)
            assert is_valid is False
            assert error != ""
        
        # Test extremely long inputs
        long_string = "a" * 10000
        is_valid, error = validate_parameters([long_string])
        assert is_valid is False
        assert "too long" in error.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
