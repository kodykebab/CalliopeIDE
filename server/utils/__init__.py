"""
Utility functions for Calliope IDE
"""

from .auth_utils import (
    generate_access_token,
    generate_refresh_token,
    decode_token,
    token_required,
    revoke_refresh_token,
)
from .validators import (
    validate_email_format,
    validate_username,
    validate_password,
    validate_registration_data,
    validate_login_data,
    sanitize_input,
)
from .agent_validators import (
    validate_agent_input,
    sanitize_agent_input,
    is_dangerous_command,
)
from .secure_execution import (
    secure_execute,
    SecurityError,
    ExecutionTimeoutError,
    MemoryLimitError,
    validate_code_safety,
)
from . import context_builder
from . import prompt_builder

# Issue #59: container-based isolation modules
from . import container_manager   # agent container lifecycle
from . import docker_executor     # ephemeral sandbox for /execute

__all__ = [
    # Auth
    'generate_access_token',
    'generate_refresh_token',
    'decode_token',
    'token_required',
    'revoke_refresh_token',
    # Validation
    'validate_email_format',
    'validate_username',
    'validate_password',
    'validate_registration_data',
    'validate_login_data',
    'sanitize_input',
    # Agent validators
    'validate_agent_input',
    'sanitize_agent_input',
    'is_dangerous_command',
    # Execution
    'secure_execute',
    'SecurityError',
    'ExecutionTimeoutError',
    'MemoryLimitError',
    'validate_code_safety',
    # Context / prompts
    'context_builder',
    'prompt_builder',
    # Issue #59
    'container_manager',
    'docker_executor',
]