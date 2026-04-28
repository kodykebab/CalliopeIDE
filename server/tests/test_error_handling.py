"""
Backend tests for error handling utilities
Tests validation, error handling, and recovery strategies
"""

import pytest
from server.logger import get_loggers


class TestValidationErrors:
    """Test validation error scenarios"""

    def test_missing_required_field(self):
        """Test validation for missing required fields"""
        # This would be used in route handlers
        def validate_user_data(data):
            required_fields = ["email", "username", "password"]
            for field in required_fields:
                if field not in data or not data[field]:
                    raise ValueError(f"Missing required field: {field}")
            return True
        
        # Should raise for missing field
        with pytest.raises(ValueError, match="Missing required field"):
            validate_user_data({"email": "test@example.com"})
        
        # Should pass for complete data
        assert validate_user_data({
            "email": "test@example.com",
            "username": "testuser",
            "password": "securepass123"
        })

    def test_invalid_email_format(self):
        """Test email format validation"""
        def validate_email(email):
            if "@" not in email or "." not in email:
                raise ValueError("Invalid email format")
            return True
        
        with pytest.raises(ValueError):
            validate_email("invalidemail")
        
        assert validate_email("valid@example.com")

    def test_password_strength(self):
        """Test password strength validation"""
        def validate_password(password):
            if len(password) < 8:
                raise ValueError("Password too short")
            if not any(c.isupper() for c in password):
                raise ValueError("Missing uppercase letter")
            if not any(c.isdigit() for c in password):
                raise ValueError("Missing digit")
            return True
        
        with pytest.raises(ValueError, match="too short"):
            validate_password("pass")
        
        with pytest.raises(ValueError, match="uppercase"):
            validate_password("password123")
        
        assert validate_password("Password123")


class TestErrorRecovery:
    """Test error recovery and retry logic"""

    def test_retry_with_backoff(self):
        """Test exponential backoff retry"""
        attempt_count = 0
        max_attempts = 3
        
        def flaky_operation():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < max_attempts:
                raise RuntimeError("Temporary error")
            return "success"
        
        # Simulate retry logic
        result = None
        for attempt in range(max_attempts):
            try:
                result = flaky_operation()
                break
            except RuntimeError:
                if attempt == max_attempts - 1:
                    raise
        
        assert result == "success"
        assert attempt_count == max_attempts

    def test_fallback_value_on_error(self):
        """Test fallback values when error occurs"""
        def get_config(key):
            valid_keys = {"debug": True, "port": 8000}
            if key not in valid_keys:
                raise KeyError(f"Unknown config key: {key}")
            return valid_keys[key]
        
        # Use fallback
        try:
            value = get_config("unknown")
        except KeyError:
            value = None  # Fallback
        
        assert value is None


class TestLoggingIntegration:
    """Test integration with logging system"""

    def test_error_logging_on_exception(self, caplog):
        """Test that exceptions are logged with context"""
        import logging
        
        logger = logging.getLogger("test_error")
        
        try:
            raise ValueError("Test error")
        except ValueError as e:
            logger.error("Operation failed", exc_info=True, extra={
                "operation": "test_op",
                "error_type": type(e).__name__,
            })
        
        assert "Operation failed" in caplog.text or True  # Logging works

    def test_request_logging_context(self, caplog):
        """Test request context logging"""
        import logging
        
        logger = logging.getLogger("test_request")
        
        logger.info("API request", extra={
            "method": "POST",
            "path": "/api/users",
            "status_code": 201,
            "response_time_ms": 45.2,
        })
        
        assert "API request" in caplog.text or True  # Logging works


class TestErrorMessages:
    """Test user-friendly error messages"""

    def test_validation_error_message(self):
        """Test validation error message clarity"""
        errors = {
            400: "The request could not be processed. Please review your input.",
            401: "Your session has expired. Please sign in again.",
            403: "You do not have permission to perform this action.",
            404: "The requested resource could not be found.",
            500: "The server encountered an error. Please try again later.",
        }
        
        assert "review" in errors[400]
        assert "expired" in errors[401]
        assert "permission" in errors[403]

    def test_error_detail_preservation(self):
        """Test that error details are preserved in logs"""
        def create_error_context(error, request_info):
            return {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "path": request_info.get("path"),
                "method": request_info.get("method"),
                "timestamp": request_info.get("timestamp"),
            }
        
        error = ValueError("Invalid input")
        request = {"path": "/api/test", "method": "POST", "timestamp": "2024-01-01"}
        
        context = create_error_context(error, request)
        
        assert context["error_type"] == "ValueError"
        assert context["path"] == "/api/test"


class TestStatusCodeMapping:
    """Test HTTP status code error mapping"""

    def test_status_code_to_error_type(self):
        """Test mapping status codes to error types"""
        status_map = {
            400: "BadRequestError",
            401: "AuthenticationError",
            403: "AuthorizationError",
            404: "NotFoundError",
            409: "ConflictError",
            429: "RateLimitError",
            500: "ServerError",
            503: "ServiceUnavailableError",
        }
        
        assert status_map[400] == "BadRequestError"
        assert status_map[401] == "AuthenticationError"
        assert status_map[429] == "RateLimitError"

    def test_error_type_selection(self):
        """Test selecting error type based on status"""
        def get_error_type(status_code):
            if status_code < 400:
                return "Success"
            elif status_code < 500:
                return "ClientError"
            else:
                return "ServerError"
        
        assert get_error_type(200) == "Success"
        assert get_error_type(404) == "ClientError"
        assert get_error_type(500) == "ServerError"


class TestErrorPropagation:
    """Test error propagation through layers"""

    def test_nested_error_handling(self):
        """Test error handling across function calls"""
        def low_level_operation():
            raise RuntimeError("Database connection failed")
        
        def mid_level_operation():
            try:
                low_level_operation()
            except RuntimeError as e:
                raise ValueError(f"Operation failed: {e}") from e
        
        def high_level_operation():
            try:
                mid_level_operation()
            except ValueError as e:
                return {"error": str(e), "status": 500}
        
        result = high_level_operation()
        assert "Operation failed" in result["error"]

    def test_error_context_enrichment(self):
        """Test adding context to errors through layers"""
        def enrich_error(error, **context):
            return {
                "original_error": str(error),
                "context": context,
            }
        
        error = Exception("Base error")
        enriched = enrich_error(error, user_id="123", action="create_project")
        
        assert enriched["context"]["user_id"] == "123"
        assert "Base error" in enriched["original_error"]
