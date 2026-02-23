"""Session model for tracking user sessions"""
from datetime import datetime
from server.middleware.database import db


class Session(db.Model):
    """Session model for storing user session information"""
    
    __tablename__ = 'sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    session_token = db.Column(db.String(255), unique=True, nullable=True, index=True)
    instance_dir = db.Column(db.String(255), nullable=True)
    port = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('sessions', lazy=True, cascade='all, delete-orphan'))
    chat_history = db.relationship('ChatHistory', backref='session', lazy=True, cascade='all, delete-orphan')
    
    def __init__(self, user_id, session_token=None, instance_dir=None, port=None):
        self.user_id = user_id
        self.session_token = session_token
        self.instance_dir = instance_dir
        self.port = port
        self.is_active = True
    
    def deactivate(self):
        """Mark session as inactive"""
        self.is_active = False
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self):
        """Convert session object to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_token': self.session_token,
            'instance_dir': self.instance_dir,
            'port': self.port,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<Session {self.id} for User {self.user_id}>'