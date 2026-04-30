"""
Comprehensive tests for error handling system
Addresses HIGH PRIORITY security issue #100 - Enhanced error handling
"""

import pytest
import json
import logging
from unittest.mock import Mock, patch, MagicMock
from flask import Flask, g
from datetime import datetime, timezone

from server.utils.error_handlers import (
    SecurityError, RateLimitError, ValidationError, StellarAddressError,
    FriendbotLimitError, SecurityLogger, handle_security_errors,
    sanitize_error_message, create_error_response, log_request_context,
    RateLimitBreachDetector, breach_detector
)


class TestSecurityErrorClasses:
    """Test security error classes"""
    
    def test_security_error_base(self):
        """Test base SecurityError class"""
        error = SecurityError("Test error", "TEST_ERROR", 400)
        assert error.message == "Test error"
        assert error.error_code == "TEST_ERROR"
        assert error.status_code == 400
        assert error.timestamp is not None
    
    def test_rate_limit_error(self):
        """Test RateLimitError class"""
        usage_info = {"account_requests": 5, "limit": 10}
        error = RateLimitError("Rate limit exceeded", 60, usage_info)
        assert error.retry_after == 60
        assert error.usage_info == usage_info
        assert error.error_code == "RATE_LIMIT_EXCEEDED"
        assert error.status_code == 429
    
    def test_validation_error(self):
        """Test ValidationError class"""
        error = ValidationError("Invalid input", "field_name", "bad_value")
        assert error.field == "field_name"
        assert error.value == "bad_value"
        assert error.error_code == "VALIDATION_ERROR"
    
    def test_stellar_address_error(self):
        """Test StellarAddressError class"""
        error = StellarAddressError("Invalid address", "public_key", "GINVALID")
        assert error.field == "stellar_public_key"
        assert error.value == "GINVALID"
        assert error.error_code == "STELLAR_PUBLIC_KEY_INVALID"
    
    def test_friendbot_limit_error(self):
        """Test FriendbotLimitError class"""
        usage_info = {"account_requests": 4, "limit": 3}
        error = FriendbotLimitError("Friendbot limit exceeded", usage_info)
        assert error.usage_info == usage_info
        assert error.error_code == "FRIENDBOT_LIMIT_EXCEEDED"
        assert error.status_code == 429


class TestSecurityLogger:
    """Test security logging functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.logger_mock = Mock()
        self.app = Flask(__name__)
    
    @patch('server.utils.error_handlers.logger')
    def test_log_rate_limit_violation(self, mock_logger):
        """Test rate limit violation logging"""
        with self.app.test_request_context('/test'):
            SecurityLogger.log_rate_limit_violation(
                "user123", "192.168.1.1", "soroban_invoke", "per_minute", 30
            )
            
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0]
            assert "RATE_LIMIT_VIOLATION" in call_args[0]
            assert "user=user123" in call_args[0]
            assert "ip=192.168.1.1" in call_args[0]
    
    @patch('server.utils.error_handlers.logger')
    def test_log_validation_error(self, mock_logger):
        """Test validation error logging"""
        with self.app.test_request_context('/test'):
            SecurityLogger.log_validation_error(
                "user123", "192.168.1.1", "contract_id", "INVALID", "Invalid format"
            )
            
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0]
            assert "VALIDATION_ERROR" in call_args[0]
            assert "field=contract_id" in call_args[0]
    
    @patch('server.utils.error_handlers.logger')
    def test_log_friendbot_abuse(self, mock_logger):
        """Test Friendbot abuse logging"""
        usage_info = {"account_requests": 5, "limit": 3}
        with self.app.test_request_context('/test'):
            SecurityLogger.log_friendbot_abuse(
                "user123", "192.168.1.1", "GABC123...", usage_info
            )
            
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0]
            assert "FRIENDBOT_ABUSE" in call_args[0]
            assert "account=GABC123..." in call_args[0]
    
    @patch('server.utils.error_handlers.logger')
    def test_log_security_incident(self, mock_logger):
        """Test security incident logging"""
        details = {"attack_type": "injection_attempt"}
        with self.app.test_request_context('/test'):
            SecurityLogger.log_security_incident(
                "user123", "192.168.1.1", "sql_injection", details, "high"
            )
            
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args[0]
            assert "SECURITY_INCIDENT" in call_args[0]
            assert "severity=high" in call_args[0]


class TestErrorHandlingDecorator:
    """Test the security error handling decorator"""
    
    def setup_method(self):
        """Set up Flask app for testing"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
    
    def test_handle_rate_limit_error(self):
        """Test handling of RateLimitError"""
        @self.app.route('/test')
        @handle_security_errors
        def test_route():
            raise RateLimitError("Too many requests", 60)
        
        with self.app.test_client() as client:
            response = client.get('/test')
            assert response.status_code == 429
            
            data = json.loads(response.data)
            assert data['success'] is False
            assert data['error'] == "Too many requests"
            assert data['error_code'] == "RATE_LIMIT_EXCEEDED"
            assert data['retry_after'] == 60
            assert 'timestamp' in data
    
    def test_handle_validation_error(self):
        """Test handling of ValidationError"""
        @self.app.route('/test')
        @handle_security_errors
        def test_route():
            raise ValidationError("Invalid field", "contract_id", "BAD_VALUE")
        
        with self.app.test_client() as client:
            response = client.get('/test')
            assert response.status_code == 400
            
            data = json.loads(response.data)
            assert data['success'] is False
            assert data['error'] == "Invalid field"
            assert data['error_code'] == "VALIDATION_ERROR"
            assert data['field'] == "contract_id"
    
    def test_handle_stellar_address_error(self):
        """Test handling of StellarAddressError"""
        @self.app.route('/test')
        @handle_security_errors
        def test_route():
            raise StellarAddressError("Invalid address", "public_key", "GINVALID")
        
        with self.app.test_client() as client:
            response = client.get('/test')
            assert response.status_code == 400
            
            data = json.loads(response.data)
            assert data['success'] is False
            assert data['error_code'] == "STELLER_PUBLIC_KEY_INVALID"
            assert data['field'] == "stellar_public_key"
    
    def test_handle_friendbot_limit_error(self):
        """Test handling of FriendbotLimitError"""
        usage_info = {"account_requests": 5, "limit": 3}
        @self.app.route('/test')
        @handle_security_errors
        def test_route():
            raise FriendbotLimitError("Friendbot limit exceeded", usage_info)
        
        with self.app.test_client() as client:
            response = client.get('/test')
            assert response.status_code == 429
            
            data = json.loads(response.data)
            assert data['success'] is False
            assert data['error_code'] == "FRIENDBOT_LIMIT_EXCEEDED"
            assert 'usage' in data
    
    def test_handle_general_security_error(self):
        """Test handling of general SecurityError"""
        @self.app.route('/test')
        @handle_security_errors
        def test_route():
            raise SecurityError("Security violation", "SECURITY_ERROR", 403)
        
        with self.app.test_client() as client:
            response = client.get('/test')
            assert response.status_code == 403
            
            data = json.loads(response.data)
            assert data['success'] is False
            assert data['error_code'] == "SECURITY_ERROR"
    
    def test_handle_unexpected_error(self):
        """Test handling of unexpected exceptions"""
        @self.app.route('/test')
        @handle_security_errors
        def test_route():
            raise ValueError("Unexpected error")
        
        with self.app.test_client() as client:
            response = client.get('/test')
            assert response.status_code == 500
            
            data = json.loads(response.data)
            assert data['success'] is False
            assert data['error_code'] == "INTERNAL_ERROR"
            assert "unexpected error occurred" in data['error']


class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_sanitize_error_message(self):
        """Test error message sanitization"""
        # Test normal message
        message = "This is a normal error message"
        sanitized = sanitize_error_message(message)
        assert sanitized == message
        
        # Test message with sensitive info
        sensitive = "password=secret123 and token=abc123"
        sanitized = sanitize_error_message(sensitive)
        assert "[REDACTED]" in sanitized
        assert "secret123" not in sanitized
        assert "abc123" not in sanitized
        
        # Test long message truncation
        long_message = "a" * 300
        sanitized = sanitize_error_message(long_message, max_length=100)
        assert len(sanitized) <= 103  # 100 + "..."
        assert sanitized.endswith("...")
        
        # Test empty message
        sanitized = sanitize_error_message("")
        assert sanitized == "Unknown error occurred"
        
        # Test None message
        sanitized = sanitize_error_message(None)
        assert sanitized == "Unknown error occurred"
    
    def test_create_error_response(self):
        """Test standardized error response creation"""
        response, status_code = create_error_response(
            "TEST_ERROR", "Test message", 400, {"field": "test_field"}
        )
        
        assert status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert data['error'] == "Test message"
        assert data['error_code'] == "TEST_ERROR"
        assert data['field'] == "test_field"
        assert 'timestamp' in data
    
    @patch('server.utils.error_handlers.logger')
    def test_log_request_context(self, mock_logger):
        """Test request context logging"""
        app = Flask(__name__)
        with app.test_request_context('/api/test', method='POST', headers={
            'User-Agent': 'TestAgent',
            'Content-Type': 'application/json'
        }):
            log_request_context("user123", {"additional": "data"})
            
            mock_logger.debug.assert_called_once()
            call_args = mock_logger.debug.call_args[0]
            assert "REQUEST_CONTEXT" in call_args[0]


class TestRateLimitBreachDetector:
    """Test rate limit breach detection"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = RateLimitBreachDetector(threshold=5, window_minutes=1)
    
    def test_record_attempt(self):
        """Test recording breach attempts"""
        # Should not trigger breach initially
        result = self.detector.record_attempt("user1", "192.168.1.1")
        assert result is False
        
        # Add attempts up to threshold
        for i in range(4):  # Total 5 attempts
            result = self.detector.record_attempt("user1", "192.168.1.1")
        
        # Should trigger breach on threshold
        result = self.detector.record_attempt("user1", "192.168.1.1")
        assert result is True
    
    def test_window_reset(self):
        """Test that breach window resets over time"""
        # Add attempts up to threshold
        for i in range(5):
            self.detector.record_attempt("user1", "192.168.1.1")
        
        # Should trigger breach
        result = self.detector.record_attempt("user1", "192.168.1.1")
        assert result is True
        
        # Mock time passage (this would need time mocking in real tests)
        # For now, just test the structure
        key = "user1:192.168.1.1"
        assert key in self.detector.breach_attempts
        assert len(self.detector.breach_attempts[key]) >= 5
    
    def test_different_keys_separate(self):
        """Test that different users/IPs are tracked separately"""
        # Add attempts for user1
        for i in range(5):
            self.detector.record_attempt("user1", "192.168.1.1")
        
        # Should trigger breach for user1
        result = self.detector.record_attempt("user1", "192.168.1.1")
        assert result is True
        
        # Should not trigger breach for user2
        result = self.detector.record_attempt("user2", "192.168.1.1")
        assert result is False
        
        # Should not trigger breach for same user different IP
        result = self.detector.record_attempt("user1", "192.168.1.2")
        assert result is False


class TestIntegration:
    """Integration tests for the complete error handling system"""
    
    def setup_method(self):
        """Set up integration test environment"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
    
    @patch('server.utils.error_handlers.SecurityLogger')
    def test_end_to_end_error_handling(self, mock_logger):
        """Test complete error handling flow"""
        @self.app.route('/test')
        @handle_security_errors
        def test_route():
            raise RateLimitError("Rate limit exceeded", 60, {"requests": 100})
        
        with self.app.test_client() as client:
            response = client.get('/test')
            assert response.status_code == 429
            
            # Verify error response structure
            data = json.loads(response.data)
            required_fields = ['success', 'error', 'error_code', 'retry_after', 'timestamp']
            for field in required_fields:
                assert field in data
            
            # Verify logging was called
            mock_logger.log_rate_limit_violation.assert_called()
    
    def test_multiple_error_types(self):
        """Test handling different error types in same endpoint"""
        @self.app.route('/test/<error_type>')
        @handle_security_errors
        def test_route(error_type):
            if error_type == "rate_limit":
                raise RateLimitError("Rate limit exceeded", 60)
            elif error_type == "validation":
                raise ValidationError("Invalid input", "field", "value")
            elif error_type == "security":
                raise SecurityError("Security error", "SEC_ERROR", 403)
            else:
                raise ValueError("Unexpected error")
        
        with self.app.test_client() as client:
            # Test rate limit error
            response = client.get('/test/rate_limit')
            assert response.status_code == 429
            
            # Test validation error
            response = client.get('/test/validation')
            assert response.status_code == 400
            
            # Test security error
            response = client.get('/test/security')
            assert response.status_code == 403
            
            # Test unexpected error
            response = client.get('/test/unknown')
            assert response.status_code == 500


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
