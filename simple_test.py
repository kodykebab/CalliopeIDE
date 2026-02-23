import sys
import os
sys.path.append('.')

# Direct import to avoid dependency issues
exec(open('server/utils/secure_execution.py').read())

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