"""
Enhanced Logging Utility for Calliope IDE
Provides structured logging with different levels and formatters
"""

import logging
import sys
from datetime import datetime
from pathlib import Path


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for console output"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logger(name='calliope_ide', level=logging.INFO, log_file=None):
    """
    Setup and configure logger with console and file handlers
    
    Args:
        name: Logger name
        level: Logging level
        log_file: Optional log file path
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = ColoredFormatter(
        '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def log_api_request(logger, request, user_id=None):
    """
    Log API request details
    
    Args:
        logger: Logger instance
        request: Flask request object
        user_id: Optional user ID
    """
    logger.info(
        f"API Request: {request.method} {request.path} | "
        f"IP: {request.remote_addr} | "
        f"User: {user_id or 'Anonymous'}"
    )


def log_api_response(logger, status_code, duration_ms=None):
    """
    Log API response details
    
    Args:
        logger: Logger instance
        status_code: HTTP status code
        duration_ms: Optional request duration in milliseconds
    """
    duration_str = f" | Duration: {duration_ms}ms" if duration_ms else ""
    logger.info(f"API Response: {status_code}{duration_str}")


def log_error(logger, error, context=None):
    """
    Log error with context
    
    Args:
        logger: Logger instance
        error: Exception or error message
        context: Optional context dictionary
    """
    error_msg = str(error)
    if context:
        context_str = " | ".join([f"{k}={v}" for k, v in context.items()])
        error_msg = f"{error_msg} | Context: {context_str}"
    
    logger.error(error_msg, exc_info=True)


def log_ai_interaction(logger, prompt_length, response_length, model, duration_ms=None):
    """
    Log AI service interaction
    
    Args:
        logger: Logger instance
        prompt_length: Length of prompt in characters
        response_length: Length of response in characters
        model: AI model used
        duration_ms: Optional duration in milliseconds
    """
    duration_str = f" | Duration: {duration_ms}ms" if duration_ms else ""
    logger.info(
        f"AI Interaction: Model={model} | "
        f"Prompt={prompt_length} chars | "
        f"Response={response_length} chars{duration_str}"
    )


def log_database_operation(logger, operation, table, duration_ms=None):
    """
    Log database operation
    
    Args:
        logger: Logger instance
        operation: Operation type (SELECT, INSERT, UPDATE, DELETE)
        table: Table name
        duration_ms: Optional duration in milliseconds
    """
    duration_str = f" | Duration: {duration_ms}ms" if duration_ms else ""
    logger.debug(f"DB Operation: {operation} on {table}{duration_str}")


class RequestLogger:
    """Context manager for logging request lifecycle"""
    
    def __init__(self, logger, request, user_id=None):
        self.logger = logger
        self.request = request
        self.user_id = user_id
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        log_api_request(self.logger, self.request, self.user_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((datetime.now() - self.start_time).total_seconds() * 1000)
        
        if exc_type:
            log_error(self.logger, exc_val, {
                'path': self.request.path,
                'method': self.request.method
            })
            return False
        
        log_api_response(self.logger, 200, duration_ms)
        return True
