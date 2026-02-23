"""
Database utilities for Calliope IDE
Provides helper functions for common database operations
"""

import os
from datetime import datetime
from flask import has_app_context
from server.middleware.database import db
from server.models import User, Session, ChatHistory, ProjectMetadata


def ensure_database_directory():
    """Ensure database directory exists.

    This function is safe to call before the Flask app and database are
    fully initialized; in that case it will perform no action.
    """
    db_path = None

    # Only attempt to access the SQLAlchemy engine when an app context is active.
    if has_app_context():
        try:
            # Prefer get_engine if available; fall back to direct engine access.
            engine = getattr(db, "get_engine", None)
            engine = engine() if callable(engine) else db.engine
            db_path = engine.url.database
        except Exception:
            # If the engine is not available or misconfigured, silently skip.
            db_path = None
    if db_path and not db_path.startswith(':memory:'):
        db_dir = os.path.dirname(os.path.abspath(db_path))
        os.makedirs(db_dir, exist_ok=True)


def create_session_for_user(user_id, session_token=None, instance_dir=None, port=None):
    """Create a new session for a user"""
    try:
        # Deactivate any existing active sessions for the user (optional, depending on requirements)
        # existing_sessions = Session.query.filter_by(user_id=user_id, is_active=True).all()
        # for session in existing_sessions:
        #     session.deactivate()
        
        new_session = Session(
            user_id=user_id,
            session_token=session_token,
            instance_dir=instance_dir,
            port=port
        )
        
        db.session.add(new_session)
        db.session.commit()
        return new_session
    except Exception as e:
        db.session.rollback()
        raise e


def add_chat_message(session_id, role, content, message_type=None, execution_time=None):
    """Add a chat message to the database"""
    try:
        # Verify session exists and is active
        session = Session.query.filter_by(id=session_id, is_active=True).first()
        if not session:
            raise ValueError(f"Active session with ID {session_id} not found")
        
        chat_message = ChatHistory(
            session_id=session_id,
            role=role,
            content=content,
            message_type=message_type,
            execution_time=execution_time
        )
        
        db.session.add(chat_message)
        
        # Update session timestamp
        session.updated_at = datetime.utcnow()
        
        db.session.commit()
        return chat_message
    except Exception as e:
        db.session.rollback()
        raise e


def get_session_chat_history(session_id, limit=50, offset=0):
    """Get chat history for a session with pagination"""
    try:
        # Verify session exists
        session = Session.query.filter_by(id=session_id).first()
        if not session:
            raise ValueError(f"Session with ID {session_id} not found")
        
        return ChatHistory.get_session_history(session_id, limit, offset)
    except Exception as e:
        raise e


def create_project_metadata(user_id, project_name, description=None, project_type=None, language=None, framework=None, project_path=None):
    """Create project metadata for a user"""
    try:
        # Check if project already exists
        existing_project = ProjectMetadata.get_project_by_name(user_id, project_name)
        if existing_project:
            raise ValueError(f"Project '{project_name}' already exists for user")
        
        project = ProjectMetadata(
            user_id=user_id,
            project_name=project_name,
            description=description,
            project_type=project_type,
            language=language,
            framework=framework,
            project_path=project_path
        )
        
        db.session.add(project)
        db.session.commit()
        return project
    except Exception as e:
        db.session.rollback()
        raise e


def update_project_metadata(user_id, project_id, **kwargs):
    """Update project metadata"""
    try:
        project = ProjectMetadata.query.filter_by(id=project_id, user_id=user_id, is_active=True).first()
        if not project:
            raise ValueError(f"Project with ID {project_id} not found for user")
        
        # Update allowed fields
        allowed_fields = ['project_name', 'description', 'project_type', 'language', 'framework', 'project_path']
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(project, field, value)
        
        project.updated_at = datetime.utcnow()
        db.session.commit()
        return project
    except Exception as e:
        db.session.rollback()
        raise e


def get_user_active_sessions(user_id):
    """Get all active sessions for a user"""
    return Session.query.filter_by(user_id=user_id, is_active=True).all()


def get_session_by_id(session_id):
    """Get session by ID"""
    return Session.query.filter_by(id=session_id).first()


def deactivate_session(session_id):
    """Deactivate a session"""
    try:
        session = Session.query.filter_by(id=session_id).first()
        if session:
            session.deactivate()
        return session
    except Exception as e:
        db.session.rollback()
        raise e


def cleanup_inactive_sessions(days=7):
    """Clean up sessions inactive for specified days"""
    try:
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        inactive_sessions = Session.query.filter(
            Session.updated_at < cutoff_date,
            Session.is_active == False
        ).all()
        
        for session in inactive_sessions:
            db.session.delete(session)
        
        db.session.commit()
        return len(inactive_sessions)
    except Exception as e:
        db.session.rollback()
        raise e


def get_database_stats():
    """Get database statistics"""
    try:
        stats = {
            'users': User.query.count(),
            'sessions': Session.query.count(),
            'active_sessions': Session.query.filter_by(is_active=True).count(),
            'chat_messages': ChatHistory.query.count(),
            'projects': ProjectMetadata.query.count(),
            'active_projects': ProjectMetadata.query.filter_by(is_active=True).count()
        }
        return stats
    except Exception as e:
        return {'error': str(e)}


def safe_commit():
    """Safely commit database changes with rollback on error.

    Returns:
        Tuple[bool, Optional[str]]: (success, error_message). On success, returns (True, None).
        On failure, performs a rollback and returns (False, error_message).
    """
    try:
        db.session.commit()
        return True, None
    except Exception as e:
        db.session.rollback()
        return False, str(e)