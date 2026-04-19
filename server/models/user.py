"""User model with OAuth support"""
import bcrypt
from datetime import datetime
from server.middleware.database import db


class User(db.Model):
    """User model supporting both password-based and OAuth authentication"""

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)

    # Nullable for OAuth users who never set a password
    password_hash = db.Column(db.String(255), nullable=True)

    # OAuth fields
    oauth_provider = db.Column(db.String(50), nullable=True)   # 'github' | 'google' | None
    oauth_id = db.Column(db.String(255), nullable=True, index=True)  # provider's user ID

    full_name = db.Column(db.String(150))
    avatar_url = db.Column(db.String(500))
    bio = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # ------------------------------------------------------------------ #
    # Constructors
    # ------------------------------------------------------------------ #

    def __init__(self, email, username, password=None, full_name=None,
                 oauth_provider=None, oauth_id=None, avatar_url=None):
        self.email = email.lower().strip()
        self.username = username.strip()
        self.full_name = full_name
        self.avatar_url = avatar_url
        self.oauth_provider = oauth_provider
        self.oauth_id = oauth_id

        # OAuth users don't need a password; verified on creation
        if password:
            self.set_password(password)
        if oauth_provider:
            self.is_verified = True  # OAuth providers already verified the email

    @classmethod
    def create_oauth_user(cls, email, username, full_name, avatar_url,
                          oauth_provider, oauth_id):
        """Factory for OAuth-originated accounts."""
        return cls(
            email=email,
            username=username,
            full_name=full_name,
            avatar_url=avatar_url,
            oauth_provider=oauth_provider,
            oauth_id=oauth_id,
        )

    # ------------------------------------------------------------------ #
    # Password helpers
    # ------------------------------------------------------------------ #

    def set_password(self, password):
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), salt
        ).decode('utf-8')

    def check_password(self, password):
        if not self.password_hash:
            return False
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self.password_hash.encode('utf-8')
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def update_last_login(self):
        self.last_login = datetime.utcnow()
        db.session.commit()

    def to_dict(self, include_sensitive=False):
        data = {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'full_name': self.full_name,
            'avatar_url': self.avatar_url,
            'bio': self.bio,
            'is_verified': self.is_verified,
            'oauth_provider': self.oauth_provider,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }
        if include_sensitive:
            data.update({
                'is_active': self.is_active,
                'is_admin': self.is_admin,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            })
        return data

    def __repr__(self):
        return f'<User {self.username} ({self.oauth_provider or "password"})>'