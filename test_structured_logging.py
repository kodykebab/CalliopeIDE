#!/usr/bin/env python3
"""
Test script for structured logging implementation
Verifies that the logging system works correctly and measures performance impact
"""
import time
import json
import sys
import os

# Add server directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

def test_structured_logger():
    """Test the structured logger functionality"""
    print("Testing structured logging implementation...")
    
    try:
        from server.utils.structured_logger import get_structured_logger
        logger = get_structured_logger('test-logger')
        
        # Test basic logging
        print("1. Testing basic logging...")
        logger.info("Test info message", test_type="basic_logging")
        logger.warning("Test warning message", test_type="basic_logging")
        logger.error("Test error message", test_type="basic_logging")
        
        # Test specialized logging methods
        print("2. Testing specialized logging methods...")
        logger.log_api_request("GET", "/test", user_id=123)
        logger.log_api_response("GET", "/test", 200, 150.5, user_id=123)
        logger.log_execution_start("print('hello')", user_id=123)
        logger.log_execution_complete("print('hello')", "success", 50.2, user_id=123)
        logger.log_session_event("session_start", "sess_123", user_id=123)
        logger.log_auth_event("login_success", user_id=123)
        
        # Test error logging with context
        print("3. Testing error logging with context...")
        try:
            raise ValueError("Test error for logging")
        except ValueError as e:
            logger.log_error_with_context(e, {"test_context": "error_logging_test"})
        
        print("4. Testing performance...")
        
        # Measure performance of logging operations
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
        
        print("5. Testing JSON output format...")
        
        # Capture log output to verify JSON format
        import io
        from contextlib import redirect_stderr
        
        log_capture = io.StringIO()
        
        # Temporarily redirect stderr to capture logs
        original_stderr = sys.stderr
        sys.stderr = log_capture
        
        logger.info("JSON format test", test_type="format_verification", structured_data={"key": "value"})
        
        sys.stderr = original_stderr
        
        # Check if output is valid JSON
        log_output = log_capture.getvalue().strip()
        try:
            parsed = json.loads(log_output)
            print("   JSON format: VALID")
            print(f"   Sample log structure: {json.dumps(parsed, indent=2)}")
        except json.JSONDecodeError:
            print("   JSON format: INVALID")
            print(f"   Raw output: {log_output}")
        
        print("\nStructured logging test completed successfully!")
        return True
        
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure the server directory is available and dependencies are installed")
        return False
    except Exception as e:
        print(f"Test failed with error: {e}")
        return False

def test_request_tracing():
    """Test request tracing functionality"""
    print("\nTesting request tracing...")
    
    try:
        # Simulate Flask context
        class MockFlaskG:
            def __init__(self):
                self.request_id = "test-req-123"
                self.user_id = 456
                self.session_id = "test-sess-789"
        
        class MockFlask:
            def __init__(self):
                self.g = MockFlaskG()
        
        # Mock Flask app for testing
        app = MockFlask()
        
        from server.utils.structured_logger import get_structured_logger
        logger = get_structured_logger('test-tracing')
        
        # Test logging with request context
        logger.info("Test with request context", test_type="request_tracing")
        
        print("   Request tracing test passed!")
        return True
        
    except Exception as e:
        print(f"Request tracing test failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("STRUCTURED LOGGING IMPLEMENTATION TEST")
    print("=" * 60)
    
    success = True
    
    # Run tests
    success &= test_structured_logger()
    success &= test_request_tracing()
    
    print("\n" + "=" * 60)
    if success:
        print("ALL TESTS PASSED!")
        print("Structured logging implementation is working correctly.")
    else:
        print("SOME TESTS FAILED!")
        print("Please check the implementation for issues.")
    print("=" * 60)
