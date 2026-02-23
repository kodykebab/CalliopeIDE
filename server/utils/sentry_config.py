"""
Sentry configuration for CalliopeIDE backend
"""
import os
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from typing import Dict, Any


class SentryConfig:
    """Sentry configuration class for secure and conditional initialization"""
    
    @staticmethod
    def is_monitoring_enabled() -> bool:
        """Check if monitoring is enabled via environment variable"""
        return os.getenv('ENABLE_MONITORING', 'false').lower() == 'true'
    
    @staticmethod
    def get_dsn() -> str:
        """Get Sentry DSN from environment"""
        return os.getenv('SENTRY_DSN', '')
    
    @staticmethod
    def get_environment() -> str:
        """Get deployment environment"""
        return os.getenv('FLASK_ENV', 'development')
    
    @staticmethod
    def get_release() -> str:
        """Get release version"""
        return os.getenv('APP_VERSION', '1.0.0')
    
    @staticmethod
    def before_send(event: Dict[str, Any], hint: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter sensitive data before sending to Sentry
        """
        # Remove sensitive data from request data
        if 'request' in event:
            request_data = event['request']
            
            # Remove sensitive headers
            if 'headers' in request_data:
                headers = request_data['headers']
                sensitive_headers = ['authorization', 'cookie', 'x-api-key', 'x-auth-token']
                for header in sensitive_headers:
                    if header in headers:
                        headers[header] = '[Filtered]'
                    # Case-insensitive filtering
                    for key in list(headers.keys()):
                        if key.lower() in sensitive_headers:
                            headers[key] = '[Filtered]'
            
            # Remove sensitive form data and JSON data
            if 'data' in request_data:
                data = request_data['data']
                if isinstance(data, dict):
                    sensitive_fields = ['password', 'token', 'secret', 'key', 'auth']
                    for field in sensitive_fields:
                        if field in data:
                            data[field] = '[Filtered]'
                        # Case-insensitive filtering
                        for key in list(data.keys()):
                            if any(sensitive_word in key.lower() for sensitive_word in sensitive_fields):
                                data[key] = '[Filtered]'
        
        # Remove sensitive user context
        if 'user' in event:
            user = event['user']
            # Keep essential user info but remove sensitive data
            allowed_fields = ['id', 'username', 'email']
            event['user'] = {k: v for k, v in user.items() if k in allowed_fields}
            
            # Mask email partially for privacy
            if 'email' in event['user'] and event['user']['email']:
                email = event['user']['email']
                if '@' in email:
                    local, domain = email.split('@', 1)
                    if len(local) > 2:
                        event['user']['email'] = f"{local[:2]}***@{domain}"
        
        return event
    
    @classmethod
    def init_sentry(cls) -> bool:
        """
        Initialize Sentry with Flask integration
        Returns True if initialized successfully, False otherwise
        """
        if not cls.is_monitoring_enabled():
            print("⚠️  Monitoring disabled - Sentry not initialized")
            return False
        
        dsn = cls.get_dsn()
        if not dsn:
            print("⚠️  SENTRY_DSN not provided - Sentry not initialized")
            return False
        
        try:
            sentry_sdk.init(
                dsn=dsn,
                integrations=[
                    FlaskIntegration(transaction_style='endpoint'),
                    SqlalchemyIntegration(),
                ],
                # Performance monitoring
                traces_sample_rate=0.1,  # Sample 10% of transactions for performance monitoring
                
                # Error sampling
                sample_rate=1.0,  # Send all errors
                
                # Environment and release
                environment=cls.get_environment(),
                release=cls.get_release(),
                
                # Security and privacy
                before_send=cls.before_send,
                send_default_pii=False,  # Don't send personally identifiable information
                
                # Debug mode (only in development)
                debug=cls.get_environment() == 'development',
                
                # Additional options
                attach_stacktrace=True,
                shutdown_timeout=2,  # Quick shutdown
            )
            
            print(f"✅ Sentry initialized for environment: {cls.get_environment()}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize Sentry: {e}")
            return False


def capture_exception_with_context(exception: Exception, **context) -> str:
    """
    Capture exception with additional context if Sentry is enabled
    Returns the event ID for tracking
    """
    if not SentryConfig.is_monitoring_enabled():
        return ""
    
    try:
        with sentry_sdk.configure_scope() as scope:
            # Add context to the event
            for key, value in context.items():
                scope.set_context(key, value)
            
            event_id = sentry_sdk.capture_exception(exception)
            return event_id
    except Exception as e:
        print(f"Failed to capture exception in Sentry: {e}")
        return ""


def capture_message_with_context(message: str, level: str = "info", **context) -> str:
    """
    Capture message with additional context if Sentry is enabled
    Returns the event ID for tracking
    """
    if not SentryConfig.is_monitoring_enabled():
        return ""
    
    try:
        with sentry_sdk.configure_scope() as scope:
            # Add context to the event
            for key, value in context.items():
                scope.set_context(key, value)
            
            event_id = sentry_sdk.capture_message(message, level)
            return event_id
    except Exception as e:
        print(f"Failed to capture message in Sentry: {e}")
        return ""