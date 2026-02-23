"""Chat history model for storing conversation messages"""
from datetime import datetime
from server.middleware.database import db


class ChatHistory(db.Model):
    """Chat history model for storing conversation messages"""
    
    __tablename__ = 'chat_history'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, index=True)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Optional metadata fields
    message_type = db.Column(db.String(50), nullable=True)  # 'text', 'code', 'error', etc.
    execution_time = db.Column(db.Float, nullable=True)  # For code execution messages
    
    def __init__(self, session_id, role, content, message_type=None, execution_time=None):
        self.session_id = session_id
        self.role = role.lower() if role else 'user'
        self.content = content
        self.message_type = message_type
        self.execution_time = execution_time
        self.timestamp = datetime.utcnow()
    
    @staticmethod
    def get_session_history(session_id, limit=50, offset=0):
        """Get chat history for a session with pagination"""
        return ChatHistory.query.filter_by(session_id=session_id)\
                                .order_by(ChatHistory.timestamp.asc())\
                                .offset(offset).limit(limit).all()
    
    @staticmethod
    def get_recent_messages(session_id, limit=10):
        """Get recent messages for a session"""
        return ChatHistory.query.filter_by(session_id=session_id)\
                                .order_by(ChatHistory.timestamp.desc())\
                                .limit(limit).all()
    
    def to_dict(self):
        """Convert chat message object to dictionary"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'role': self.role,
            'content': self.content,
            'message_type': self.message_type,
            'execution_time': self.execution_time,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
    
    def __repr__(self):
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f'<ChatHistory {self.id}: {self.role} - {content_preview}>'