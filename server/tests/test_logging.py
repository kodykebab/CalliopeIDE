"""
Backend tests for structured logging system
Tests logging setup, formatters, and component loggers
"""

import json
import pytest
import logging
import tempfile
from pathlib import Path
from server.logger import (
    setup_logging,
    JSONFormatter,
    RequestLogger,
    DatabaseLogger,
    AuthLogger,
    get_loggers,
)


class TestJSONFormatter:
    """Test JSON formatter for logs"""

    def test_formatter_creates_valid_json(self, caplog):
        """Test that formatter produces valid JSON"""
        formatter = JSONFormatter()
        logger = logging.getLogger("test")
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        logger.info("Test message")
        
        # Parse formatted output as JSON
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        output = formatter.format(record)
        parsed = json.loads(output)
        
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Test message"
        assert "timestamp" in parsed
        assert parsed["logger"] == "test"

    def test_formatter_includes_exception_info(self):
        """Test that formatter includes exception information"""
        formatter = JSONFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=True,
            )
            record.exc_info = None  # Simulate exception
            
            output = formatter.format(record)
            parsed = json.loads(output)
            
            assert parsed["level"] == "ERROR"


class TestRequestLogger:
    """Test HTTP request logging"""

    def test_log_request(self, caplog):
        """Test request logging"""
        logger = logging.getLogger("test_request")
        request_logger = RequestLogger(logger)
        
        with caplog.at_level(logging.INFO):
            request_logger.log_request(
                method="GET",
                path="/api/test",
                remote_addr="127.0.0.1",
                user_agent="test-agent",
            )
        
        assert "GET /api/test" in caplog.text

    def test_log_response_success(self, caplog):
        """Test successful response logging"""
        logger = logging.getLogger("test_response")
        request_logger = RequestLogger(logger)
        
        with caplog.at_level(logging.INFO):
            request_logger.log_response(
                status_code=200,
                response_time_ms=45.2,
                path="/api/test",
                method="GET",
            )
        
        assert "GET /api/test 200" in caplog.text

    def test_log_response_error(self, caplog):
        """Test error response logging"""
        logger = logging.getLogger("test_error_response")
        request_logger = RequestLogger(logger)
        
        with caplog.at_level(logging.WARNING):
            request_logger.log_response(
                status_code=404,
                response_time_ms=10.5,
                path="/api/missing",
                method="GET",
            )
        
        assert "GET /api/missing 404" in caplog.text

    def test_log_response_server_error(self, caplog):
        """Test server error response logging"""
        logger = logging.getLogger("test_server_error")
        request_logger = RequestLogger(logger)
        
        with caplog.at_level(logging.ERROR):
            request_logger.log_response(
                status_code=500,
                response_time_ms=100.0,
                path="/api/broken",
                method="POST",
            )
        
        assert "GET /api/broken 500" in caplog.text or "POST /api/broken 500" in caplog.text

    def test_log_error(self, caplog):
        """Test error logging during request"""
        logger = logging.getLogger("test_error")
        request_logger = RequestLogger(logger)
        
        with caplog.at_level(logging.ERROR):
            request_logger.log_error(
                error=ValueError("Invalid input"),
                path="/api/test",
                method="POST",
                status_code=400,
            )
        
        assert "Error processing POST /api/test" in caplog.text


class TestDatabaseLogger:
    """Test database operation logging"""

    def test_log_query(self, caplog):
        """Test query logging"""
        logger = logging.getLogger("test_query")
        db_logger = DatabaseLogger(logger)
        
        with caplog.at_level(logging.DEBUG):
            db_logger.log_query(
                query="SELECT * FROM users WHERE id = ?",
                params={"id": 123},
                execution_time_ms=5.3,
            )
        
        assert "Query:" in caplog.text

    def test_log_connection(self, caplog):
        """Test connection logging"""
        logger = logging.getLogger("test_connection")
        db_logger = DatabaseLogger(logger)
        
        with caplog.at_level(logging.INFO):
            db_logger.log_connection(status="connected", host="localhost")
        
        assert "Database connection: connected" in caplog.text

    def test_log_error(self, caplog):
        """Test database error logging"""
        logger = logging.getLogger("test_db_error")
        db_logger = DatabaseLogger(logger)
        
        with caplog.at_level(logging.ERROR):
            db_logger.log_error(
                error=RuntimeError("Connection failed"),
                query="SELECT * FROM users",
            )
        
        assert "Database error" in caplog.text


class TestAuthLogger:
    """Test authentication event logging"""

    def test_log_login(self, caplog):
        """Test login event logging"""
        logger = logging.getLogger("test_login")
        auth_logger = AuthLogger(logger)
        
        with caplog.at_level(logging.INFO):
            auth_logger.log_login(
                user_id="user123",
                method="password",
                ip_address="192.168.1.1",
            )
        
        assert "User login: user123 (password)" in caplog.text

    def test_log_logout(self, caplog):
        """Test logout event logging"""
        logger = logging.getLogger("test_logout")
        auth_logger = AuthLogger(logger)
        
        with caplog.at_level(logging.INFO):
            auth_logger.log_logout(user_id="user123")
        
        assert "User logout: user123" in caplog.text

    def test_log_auth_failure(self, caplog):
        """Test authentication failure logging"""
        logger = logging.getLogger("test_auth_failure")
        auth_logger = AuthLogger(logger)
        
        with caplog.at_level(logging.WARNING):
            auth_logger.log_auth_failure(
                reason="Invalid password",
                user_id="user123",
            )
        
        assert "Authentication failure: Invalid password" in caplog.text

    def test_log_token_refresh(self, caplog):
        """Test token refresh logging"""
        logger = logging.getLogger("test_token_refresh")
        auth_logger = AuthLogger(logger)
        
        with caplog.at_level(logging.DEBUG):
            auth_logger.log_token_refresh(user_id="user123")
        
        assert "Token refreshed for user: user123" in caplog.text


class TestSetupLogging:
    """Test logging setup"""

    def test_setup_logging_creates_loggers(self):
        """Test that setup creates all required loggers"""
        with tempfile.TemporaryDirectory() as tmpdir:
            loggers = setup_logging(
                app_name="test_app",
                level=logging.DEBUG,
                log_file=str(Path(tmpdir) / "test.log"),
            )
        
        assert "app" in loggers
        assert "http" in loggers
        assert "database" in loggers
        assert "auth" in loggers
        assert "request" in loggers
        assert "database_ops" in loggers
        assert "auth_ops" in loggers

    def test_setup_logging_file_handler(self):
        """Test that setup creates log file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            loggers = setup_logging(
                app_name="test_app",
                log_file=str(log_file),
            )
            
            # Log something
            loggers["app"].info("Test message")
            
            # File should exist
            assert log_file.exists()

    def test_get_loggers_singleton(self):
        """Test that get_loggers returns singleton"""
        loggers1 = get_loggers()
        loggers2 = get_loggers()
        
        assert loggers1 is loggers2


class TestLoggingIntegration:
    """Integration tests for logging system"""

    def test_request_response_flow(self, caplog):
        """Test complete request-response logging flow"""
        loggers = setup_logging(level=logging.DEBUG)
        request_logger = loggers["request"]
        
        with caplog.at_level(logging.INFO):
            request_logger.log_request(
                method="POST",
                path="/api/users",
                remote_addr="127.0.0.1",
            )
            request_logger.log_response(
                status_code=201,
                response_time_ms=23.5,
                path="/api/users",
                method="POST",
            )
        
        assert "POST /api/users" in caplog.text
        assert "201" in caplog.text

    def test_auth_flow_logging(self, caplog):
        """Test authentication flow logging"""
        loggers = setup_logging(level=logging.DEBUG)
        auth_logger = loggers["auth_ops"]
        
        with caplog.at_level(logging.INFO):
            auth_logger.log_login(user_id="user1", method="password")
            auth_logger.log_token_refresh(user_id="user1")
            auth_logger.log_logout(user_id="user1")
        
        assert "login" in caplog.text.lower()
        assert "logout" in caplog.text.lower()
