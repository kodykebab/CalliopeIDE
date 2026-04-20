"""
Secure Code Execution Module

This module provides a secure sandboxed environment for executing user-submitted Python code.
It implements comprehensive security measures to prevent malicious access to the host system.
"""

import ast
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from typing import Dict, Any, List, Optional
import logging
import docker
from docker.errors import DockerException, ImageNotFound, APIError

# Try to import resource module (Unix only)
try:
    import resource
    RESOURCE_AVAILABLE = True
except ImportError:
    RESOURCE_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# Security constants
EXECUTION_TIMEOUT = 5  # seconds
MAX_MEMORY_MB = 50  # MB
MAX_OUTPUT_SIZE = 10000  # characters

# Dangerous modules and functions that should be blocked
DANGEROUS_IMPORTS = {
    'os', 'sys', 'subprocess', 'shutil', 'glob', 'pathlib',
    'socket', 'urllib', 'requests', 'http', 'ftplib', 'smtplib',
    'telnetlib', 'xmlrpc', 'email', 'webbrowser', 'platform',
    'getpass', 'tempfile', 'pickle', 'shelve', 'dbm', 'sqlite3',
    'ctypes', 'threading', 'multiprocessing', 'concurrent',
    'importlib', '__import__', 'exec', 'eval', 'compile',
    'open', 'file', 'input', 'raw_input'
}

DANGEROUS_BUILTINS = {
    '__import__', 'exec', 'eval', 'compile', 'open', 'file',
    'input', 'raw_input', 'reload', 'vars', 'dir', 'globals',
    'locals', 'hasattr', 'getattr', 'setattr', 'delattr'
}

DANGEROUS_KEYWORDS = {
    r'\bos\.',
    r'\bsys\.',
    r'\bsubprocess\.',
    r'\bsocket\.',
    r'\bopen\s*\(',
    r'\bfile\s*\(',
    r'\bexec\s*\(',
    r'\beval\s*\(',
    r'\b__import__\s*\(',
    r'\binput\s*\(',
    r'\braw_input\s*\(',
}


class SecurityError(Exception):
    """Raised when potentially dangerous code is detected."""
    pass


class ExecutionTimeoutError(Exception):
    """Raised when code execution exceeds timeout limit."""
    pass


class MemoryLimitError(Exception):
    """Raised when memory usage exceeds limit."""
    pass


def validate_code_safety(code: str) -> None:
    """
    Validate code for dangerous operations before execution.
    
    Args:
        code: The code string to validate
        
    Raises:
        SecurityError: If dangerous operations are detected
    """
    if not code or not code.strip():
        raise SecurityError("Empty code provided")
    
    # Check for dangerous keywords using regex
    for pattern in DANGEROUS_KEYWORDS:
        if re.search(pattern, code, re.IGNORECASE):
            raise SecurityError(f"Restricted operation detected: {pattern}")
    
    # Parse AST to check for dangerous imports and calls
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise SecurityError(f"Invalid Python syntax: {str(e)}")
    
    for node in ast.walk(tree):
        # Check for dangerous imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_module = alias.name.split('.')[0]
                if root_module in DANGEROUS_IMPORTS:
                    raise SecurityError(f"Import of restricted module: {alias.name}")
        
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_module = node.module.split('.')[0]
                if root_module in DANGEROUS_IMPORTS:
                    raise SecurityError(f"Import from restricted module: {node.module}")
        
        # Check for dangerous function calls
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in DANGEROUS_BUILTINS:
                    raise SecurityError(f"Call to restricted builtin: {node.func.id}")
            elif isinstance(node.func, ast.Attribute):
                # Calls like module.func(...)
                if isinstance(node.func.value, ast.Name):
                    base_name = node.func.value.id
                    # Block calls to functions from dangerous modules, e.g., os.system(...)
                    if base_name in DANGEROUS_IMPORTS:
                        raise SecurityError(
                            f"Call to restricted module function: {base_name}.{node.func.attr}"
                        )
                    # Block access to dangerous builtins via the builtins module, e.g., builtins.open(...)
                    if base_name == "builtins" and node.func.attr in DANGEROUS_BUILTINS:
                        raise SecurityError(
                            f"Call to restricted builtin via builtins: {base_name}.{node.func.attr}"
                        )


def set_memory_limit():
    """Set memory limit for the subprocess."""
    if RESOURCE_AVAILABLE and sys.platform != 'win32':  # Unix systems only
        try:
            # Set memory limit (in bytes)
            memory_limit = MAX_MEMORY_MB * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
        except (OSError, ValueError) as e:
            logger.warning(f"Could not set memory limit: {e}")
    else:
        # On Windows, we can't set memory limits using resource module
        # The subprocess monitoring will handle memory issues through timeout
        logger.info("Memory limiting not available on Windows platform")


def create_restricted_environment() -> Dict[str, str]:
    """
    Create a restricted environment for code execution.
    
    Returns:
        Dictionary of environment variables
    """
    # Start with minimal environment
    env = {
        'PATH': '',  # Remove PATH to prevent running external commands
        'PYTHONPATH': '',
        'PYTHONHOME': '',
        'PYTHONUSERBASE': '',
        'HOME': '',
        'TEMP': '',
        'TMP': '',
    }
    
    # Add minimal Python paths if needed
    python_exe = sys.executable
    if python_exe:
        env['PYTHON_EXE'] = python_exe
    
    return env


# Initialize Docker client
try:
    docker_client = docker.from_env()
    DOCKER_AVAILABLE = True
except Exception:
    docker_client = None
    DOCKER_AVAILABLE = False
    logger.warning("Docker daemon not found. Container-based isolation will not be available.")

# Sandbox image configuration
SANDBOX_IMAGE = "calliope-sandbox"

def get_docker_client():
    """Get or initialize Docker client."""
    global docker_client, DOCKER_AVAILABLE
    if docker_client is None:
        try:
            docker_client = docker.from_env()
            DOCKER_AVAILABLE = True
        except Exception:
            DOCKER_AVAILABLE = False
    return docker_client

def docker_execute(code: str, timeout: int = EXECUTION_TIMEOUT) -> Dict[str, Any]:
    """
    Execute user code inside an isolated Docker container.
    """
    client = get_docker_client()
    if not client:
        return None  # Fallback to subprocess

    start_time = time.time()
    container = None
    
    try:
        # Security validation still applies
        validate_code_safety(code)
        
        # Prepare the script content
        # We don't need restricted_import anymore as Docker provides better isolation,
        # but we can keep it as an extra layer if desired.
        script_content = code
        
        # Create ephemeral container
        container = client.containers.run(
            image=SANDBOX_IMAGE,
            command=["python3", "-c", script_content],
            mem_limit=f"{MAX_MEMORY_MB}m",
            cpu_quota=50000,  # 50% of one CPU
            network_disabled=True,
            detach=True,
            remove=False, # We'll remove it after getting logs
            working_dir="/workspace",
            user="sandboxuser"
        )
        
        # Wait for completion with timeout
        try:
            result = container.wait(timeout=timeout)
            exit_code = result.get('StatusCode', 0)
        except Exception:
            # Timeout or other error during wait
            container.kill()
            return {
                'status': 'timeout',
                'output': '',
                'error': f'Execution time limit exceeded ({timeout}s)',
                'execution_time': timeout
            }
        
        # Get logs
        stdout = container.logs(stdout=True, stderr=False).decode('utf-8', errors='replace')
        stderr = container.logs(stdout=False, stderr=True).decode('utf-8', errors='replace')
        
        execution_time = time.time() - start_time
        
        # Truncate output if needed
        if len(stdout) > MAX_OUTPUT_SIZE:
            stdout = stdout[:MAX_OUTPUT_SIZE] + '\n... (output truncated)'
        
        if len(stderr) > MAX_OUTPUT_SIZE:
            stderr = stderr[:MAX_OUTPUT_SIZE] + '\n... (error output truncated)'
            
        status = 'success' if exit_code == 0 else 'error'
        if exit_code == 137: # Out of memory or killed
             status = 'memory_error'
             stderr = 'Memory limit exceeded or process killed'
             
        return {
            'status': status,
            'output': stdout,
            'error': stderr,
            'execution_time': execution_time
        }
        
    except ImageNotFound:
        logger.error(f"Sandbox image {SANDBOX_IMAGE} not found.")
        return None
    except Exception as e:
        logger.error(f"Docker execution failed: {str(e)}")
        return None
    finally:
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass

def docker_run_command(cmd: str, workdir: str = None, timeout: int = 300) -> Dict[str, Any]:
    """
    Execute a shell command inside an isolated Docker container.
    """
    client = get_docker_client()
    if not client:
        return None

    start_time = time.time()
    container = None
    
    try:
        volumes = {}
        if workdir:
            # Mount the host workdir to /workspace in container
            abs_workdir = os.path.abspath(workdir)
            volumes[abs_workdir] = {'bind': '/workspace', 'mode': 'rw'}
        
        # Create ephemeral container
        container = client.containers.run(
            image=SANDBOX_IMAGE,
            command=["sh", "-c", cmd],
            mem_limit=f"{MAX_MEMORY_MB * 4}m", # Higher limit for commands like build
            cpu_quota=100000, # 100% of one CPU
            network_disabled=True,
            detach=True,
            remove=False,
            volumes=volumes,
            working_dir="/workspace",
            user="root" # Many tools need root or it depends on how the image is set up
        )
        
        # Wait for completion
        try:
            result = container.wait(timeout=timeout)
            exit_code = result.get('StatusCode', 0)
        except Exception:
            container.kill()
            return {
                'status': 'timeout',
                'output': '',
                'error': f'Command timed out ({timeout}s)',
                'exit_code': -1
            }
        
        stdout = container.logs(stdout=True, stderr=False).decode('utf-8', errors='replace')
        stderr = container.logs(stdout=False, stderr=True).decode('utf-8', errors='replace')
        
        return {
            'status': 'success' if exit_code == 0 else 'error',
            'output': stdout,
            'error': stderr,
            'exit_code': exit_code,
            'execution_time': time.time() - start_time
        }
        
    except Exception as e:
        logger.error(f"Docker command execution failed: {str(e)}")
        return None
    finally:
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass

def secure_execute(code: str, timeout: int = EXECUTION_TIMEOUT) -> Dict[str, Any]:
    """
    Execute user code in a secure sandboxed environment.
    
    Args:
        code: The Python code to execute
        timeout: Maximum execution time in seconds
        
    Returns:
        Dictionary containing:
        - status: 'success', 'error', 'timeout', 'memory_error'
        - output: stdout content (if successful)
        - error: error message (if failed)
        - execution_time: time taken to execute
    """
    start_time = time.time()
    
    try:
        # Try Docker execution first
        if DOCKER_AVAILABLE:
            result = docker_execute(code, timeout)
            if result:
                return result
        
        # Fallback to subprocess execution (original logic)
        # Input validation
        if not isinstance(code, str):
            return {
                'status': 'error',
                'output': '',
                'error': 'Invalid input: code must be a string',
                'execution_time': 0
            }
        
        code = code.strip()
        if len(code) > 50000:  # Limit code length
            return {
                'status': 'error',
                'output': '',
                'error': 'Code too long (max 50,000 characters)',
                'execution_time': time.time() - start_time
            }
        
        # Security validation
        validate_code_safety(code)
        
        # Create temporary directory for execution
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create the Python script file
            script_path = os.path.join(temp_dir, 'user_code.py')
            
            # Wrap user code with security restrictions
            wrapped_code = f'''
import sys
import os

# Restrict imports by overriding __import__
original_import = __import__

def restricted_import(name, *args, **kwargs):
    dangerous_modules = {repr(DANGEROUS_IMPORTS)}
    # Block both the exact module and any of its submodules, e.g. "os.path"
    try:
        module_name = str(name)
    except Exception:
        module_name = name
    root_name = module_name.split('.', 1)[0]
    if root_name in dangerous_modules:
        raise ImportError(f"Import of '{{module_name}}' is not allowed for security reasons")
    return original_import(name, *args, **kwargs)

# Override the import function
__builtins__.__import__ = restricted_import

# Disable some potentially dangerous operations  
sys.exit = lambda code=0: None
os.system = lambda cmd: None

# User code starts here
{code}
'''
            
            try:
                with open(script_path, 'w', encoding='utf-8') as f:
                    f.write(wrapped_code)
            except Exception as e:
                return {
                    'status': 'error',
                    'output': '',
                    'error': f'Failed to create script file: {str(e)}',
                    'execution_time': time.time() - start_time
                }
            
            # Prepare restricted environment
            env = create_restricted_environment()
            
            # Execute the code in subprocess with restrictions
            try:
                # Create preexec function for Unix systems
                def preexec_fn():
                    if sys.platform != 'win32':
                        set_memory_limit()
                        # Set process group to allow killing child processes
                        os.setpgrp()
                
                preexec = preexec_fn if sys.platform != 'win32' else None
                
                # Run the subprocess
                process = subprocess.Popen(
                    [sys.executable, script_path],
                    cwd=temp_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                    preexec_fn=preexec,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
                )
                
                try:
                    stdout, stderr = process.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # Kill the process group to ensure all child processes are terminated
                    try:
                        if sys.platform == 'win32':
                            process.terminate()
                        else:
                            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    except (OSError, ProcessLookupError):
                        pass
                    
                    process.kill()
                    return {
                        'status': 'timeout',
                        'output': '',
                        'error': f'Execution time limit exceeded ({timeout}s)',
                        'execution_time': timeout
                    }
                
                execution_time = time.time() - start_time
                
                # Check output size limits
                if len(stdout) > MAX_OUTPUT_SIZE:
                    stdout = stdout[:MAX_OUTPUT_SIZE] + '\n... (output truncated)'
                
                if len(stderr) > MAX_OUTPUT_SIZE:
                    stderr = stderr[:MAX_OUTPUT_SIZE] + '\n... (error output truncated)'
                
                # Determine result status
                if process.returncode == 0:
                    if stderr:
                        # There might be warnings but execution succeeded
                        return {
                            'status': 'success',
                            'output': stdout,
                            'error': f'Warnings: {stderr}',
                            'execution_time': execution_time
                        }
                    else:
                        return {
                            'status': 'success',
                            'output': stdout,
                            'error': '',
                            'execution_time': execution_time
                        }
                else:
                    # Check for specific error types
                    if 'MemoryError' in stderr or 'memory' in stderr.lower():
                        return {
                            'status': 'memory_error',
                            'output': stdout,
                            'error': 'Memory limit exceeded',
                            'execution_time': execution_time
                        }
                    else:
                        return {
                            'status': 'error',
                            'output': stdout,
                            'error': stderr or 'Unknown execution error',
                            'execution_time': execution_time
                        }
                        
            except Exception as e:
                return {
                    'status': 'error',
                    'output': '',
                    'error': f'Subprocess execution failed: {str(e)}',
                    'execution_time': time.time() - start_time
                }
    
    except SecurityError as e:
        logger.warning(f"Security violation detected: {str(e)}")
        return {
            'status': 'error',
            'output': '',
            'error': f'Restricted operation detected: {str(e)}',
            'execution_time': time.time() - start_time
        }
    
    except Exception as e:
        logger.error(f"Unexpected error in secure_execute: {str(e)}")
        return {
            'status': 'error',
            'output': '',
            'error': f'Internal execution error: {str(e)}',
            'execution_time': time.time() - start_time
        }


def test_security_measures():
    """Test the security measures with various attack vectors."""
    
    test_cases = [
        # Normal code
        ("print('Hello World')", "should succeed"),
        
        # Infinite loop
        ("while True:\n    pass", "should timeout"),
        
        # Memory attack
        ("a = []\nwhile True:\n    a.append('A'*10**6)", "should hit memory limit"),
        
        # Dangerous imports
        ("import os\nos.system('ls')", "should be blocked"),
        ("import subprocess\nsubprocess.call('ls')", "should be blocked"),
        ("import socket", "should be blocked"),
        
        # Direct builtin access
        ("exec('print(1)')", "should be blocked"),
        ("eval('1+1')", "should be blocked"),
        ("open('/etc/passwd')", "should be blocked"),
    ]
    
    print("🔒 Testing Security Measures")
    print("=" * 50)
    print(f"Docker Available: {DOCKER_AVAILABLE}")
    print("-" * 50)
    
    for code, description in test_cases:
        print(f"\nTest: {description}")
        print(f"Code: {code[:50]}{'...' if len(code) > 50 else ''}")
        result = secure_execute(code, timeout=5)
        print(f"Status: {result['status']}")
        if result.get('error'):
            print(f"Error: {result['error'][:100]}{'...' if len(result['error']) > 100 else ''}")
        print("-" * 30)


if __name__ == "__main__":
    # Run security tests
    test_security_measures()