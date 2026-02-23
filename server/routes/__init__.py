"""
API routes for Calliope IDE
"""

from .auth_routes import auth_bp
from .chat_routes import chat_bp
from .project_routes import project_bp

__all__ = ['auth_bp', 'chat_bp', 'project_bp']