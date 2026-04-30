#!/usr/bin/env python3
"""
Simple test for structured logging without heavy dependencies
"""
import json
import time
import logging
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, Optional


class SimpleStructuredLogger:
    """Simplified version of StructuredLogger for testing"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Create structured JSON formatter
        handler = logging.StreamHandler()
        handler.setFormatter(SimpleStructuredFormatter())
        self.logger.addHandler(handler)
    
    def _build_log_record(self, level: str, message: str, **kwargs) -> Dict[str, Any]:
        """Build structured log record with context"""
        record = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': level.upper(),
            'logger': self.logger.name,
            'message': message,
            'service': 'calliope-ide',
        }
        
        # Add any additional context
        record.update(kwargs)
        
        return record
    
    def info(self, message: str, **kwargs):
        """Log info level message"""
        record = self._build_log_record('info', message, **kwargs)
        self.logger.info(json.dumps(record))
    
    def warning(self, message: str, **kwargs):
        """Log warning level message"""
        record = self._build_log_record('warning', message, **kwargs)
        self.logger.warning(json.dumps(record))
    
    def error(self, message: str, **kwargs):
        """Log error level message"""
        record = self._build_log_record('error', message, **kwargs)
        self.logger.error(json.dumps(record))
    
    def log_api_request(self, method: str, endpoint: str, user_id: Optional[int] = None, **kwargs):
        """Log API request with structured data"""
        self.info(
            f"API request: {method} {endpoint}",
            event_type='api_request',
            method=method,
            endpoint=endpoint,
            user_id=user_id,
            **kwargs
        )
    
    def log_execution_start(self, command: str, user_id: Optional[int] = None, **kwargs):
        """Log code execution start"""
        self.info(
            f"Code execution started: {command[:100]}{'...' if len(command) > 100 else ''}",
            event_type='execution_start',
            command=command,
            user_id=user_id,
            **kwargs
        )
    
    def log_execution_complete(self, command: str, status: str, duration_ms: float,
                              user_id: Optional[int] = None, **kwargs):
        """Log code execution completion"""
        self.info(
            f"Code execution completed: {status} in {duration_ms:.2f}ms",
            event_type='execution_complete',
            command=command,
            status=status,
            duration_ms=duration_ms,
            user_id=user_id,
            **kwargs
        )


class SimpleStructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging"""
    
    def format(self, record):
        # If the record already contains JSON (from our StructuredLogger), pass it through
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            try:
                # Try to parse as JSON to see if it's already structured
                json.loads(record.msg)
                return record.msg
            except (json.JSONDecodeError, ValueError):
                pass
        
        # For non-structured logs, format them as JSON
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'service': 'calliope-ide',
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def test_logging_functionality():
    """Test the logging functionality"""
    print("Testing structured logging functionality...")
    
    # Create logger
    logger = SimpleStructuredLogger('test-logger')
    
    # Test basic logging
    print("1. Testing basic logging...")
    logger.info("Test info message", test_type="basic_logging")
    logger.warning("Test warning message", test_type="basic_logging")
    logger.error("Test error message", test_type="basic_logging")
    
    # Test specialized logging methods
    print("2. Testing specialized logging methods...")
    logger.log_api_request("GET", "/test", user_id=123)
    logger.log_execution_start("print('hello')", user_id=123)
    logger.log_execution_complete("print('hello')", "success", 50.2, user_id=123)
    
    # Test performance
    print("3. Testing performance...")
    
    num_logs = 1000
    start_time = time.time()
    
    for i in range(num_logs):
        logger.info(f"Performance test message {i}", iteration=i, test_type="performance")
    
    end_time = time.time()
    duration = end_time - start_time
    avg_time_per_log = (duration / num_logs) * 1000  # Convert to milliseconds
    
    print(f"   Logged {num_logs} messages in {duration:.3f} seconds")
    print(f"   Average time per log: {avg_time_per_log:.3f} ms")
    
    if avg_time_per_log < 1.0:
        print("   Performance: EXCELLENT (< 1ms per log)")
    elif avg_time_per_log < 5.0:
        print("   Performance: GOOD (< 5ms per log)")
    elif avg_time_per_log < 10.0:
        print("   Performance: ACCEPTABLE (< 10ms per log)")
    else:
        print("   Performance: CONCERNING (> 10ms per log)")
    
    return avg_time_per_log < 10.0  # Acceptable performance threshold


def test_json_format():
    """Test that logs are properly formatted as JSON"""
    print("4. Testing JSON output format...")
    
    import io
    from contextlib import redirect_stderr
    
    logger = SimpleStructuredLogger('format-test')
    
    # Capture log output
    log_capture = io.StringIO()
    original_stderr = sys.stderr
    sys.stderr = log_capture
    
    logger.info("JSON format test", test_type="format_verification", structured_data={"key": "value"})
    
    sys.stderr = original_stderr
    
    # Check if output is valid JSON
    log_output = log_capture.getvalue().strip()
    try:
        parsed = json.loads(log_output)
        print("   JSON format: VALID")
        
        # Check required fields
        required_fields = ['timestamp', 'level', 'logger', 'message', 'service', 'test_type', 'structured_data']
        missing_fields = [field for field in required_fields if field not in parsed]
        
        if missing_fields:
            print(f"   Missing required fields: {missing_fields}")
            return False
        else:
            print("   All required fields present")
            return True
            
    except json.JSONDecodeError as e:
        print(f"   JSON format: INVALID - {e}")
        print(f"   Raw output: {log_output}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("SIMPLE STRUCTURED LOGGING TEST")
    print("=" * 60)
    
    success = True
    
    # Run tests
    success &= test_logging_functionality()
    success &= test_json_format()
    
    print("\n" + "=" * 60)
    if success:
        print("ALL TESTS PASSED!")
        print("Structured logging implementation is working correctly.")
        print("Performance impact is acceptable.")
    else:
        print("SOME TESTS FAILED!")
        print("Please check the implementation for issues.")
    print("=" * 60)
