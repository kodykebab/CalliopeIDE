import sys
sys.path.append('.')

from server.utils.secure_execution import secure_execute

# Test simple code execution
result = secure_execute("print('Hello World')")
print("=== Simple Test Result ===")
print(f"Status: {result['status']}")
print(f"Output: {result['output']}")
print(f"Error: {result['error']}")
print(f"Execution time: {result['execution_time']}")