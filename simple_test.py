import sys
import os
sys.path.append('.')

# Direct import of secure_execute without executing module as __main__
from server.utils.secure_execution import secure_execute

# Test simple code execution
result = secure_execute("print('Hello World')")
print("=== Simple Test Result ===") 
print(f"Status: {result['status']}")
print(f"Output: {result['output']}")
print(f"Error: {result['error']}")
print(f"Execution time: {result['execution_time']}")
print()

# Test another case
result2 = secure_execute("x = 5 + 3\nprint(f'Result: {x}')")
print("=== Math Test Result ===")
print(f"Status: {result2['status']}")
print(f"Output: {result2['output']}")
print(f"Error: {result2['error']}")
print(f"Execution time: {result2['execution_time']}")