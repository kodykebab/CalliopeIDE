import json
import logging
import time
import uuid
import sys
from flask import Flask, g
from server.utils import metrics as metrics_dict, increment, logger
from server.utils.structured_logging import JsonFormatter

def run_demo():
    print("=" * 70)
    print("CALLIOPE IDE - ADVANCED OBSERVABILITY DEMO")
    print("=" * 70)
    
    # 1. Initialize Logger
    base_logger = logger.base_logger
    
    # Setup a stream for demo to capture logs
    import io
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setFormatter(JsonFormatter())
    base_logger.addHandler(handler)
    
    app = Flask(__name__)
    
    with app.test_request_context('/api/execute', headers={'X-Request-ID': 'demo-trace-uuid'}):
        # 2. Simulate Request Tracing Context
        g.request_id = 'demo-trace-uuid'
        g.user_id = 42
        increment("request_count")
        
        print("\n1. EMITTING STANDARD JSON LOG...")
        logger.log_info("Demo API request received", extra={"feature": "demo", "status": "active"})
        
        # 3. Simulate Execution Lifecycle
        print("\n2. SIMULATING EXECUTION LIFECYCLE...")
        exec_id = f"exec_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        logger.log_execution_lifecycle("execution_started", exec_id, extra={"language": "python"})
        
        # Pause for effect
        time.sleep(0.5)
        
        logger.log_execution_lifecycle("execution_completed", exec_id, extra={"execution_time": 0.52, "status": "success"})
        
        # 4. Simulate Slow Request
        print("\n3. SIMULATING SLOW REQUEST DETECTION...")
        logger.log_warning("slow_request", extra={"duration_ms": 1200, "path": "/api/execute"})
        
        # 5. Simulate Error
        print("\n4. EMITTING ERROR LOG (Auto-increments error_count)...")
        try:
            1/0
        except ZeroDivisionError as e:
            logger.log_error("Failed to process math operation", error=e, extra={"op": "division"})
            
    print("\n" + "=" * 70)
    print("CURRENT JSON LOG OUTPUT:")
    print("=" * 70)
    log_lines = log_capture.getvalue().strip().split('\n')
    for line in log_lines:
        print(line)
        
    print("\n" + "=" * 70)
    print("METRICS SNAPSHOT:")
    print("=" * 70)
    print(json.dumps(metrics_dict, indent=2))
    print("=" * 70)

if __name__ == "__main__":
    run_demo()
