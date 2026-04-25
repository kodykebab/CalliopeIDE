"""JWT token utilities for authentication"""
import jwt
import os
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from server.models import User, RefreshToken
from server.middleware.database import db

JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
if not JWT_SECRET_KEY:
    raise EnvironmentError(
        "JWT_SECRET_KEY environment variable is not set. "
        "Generate a secure key with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 3600))
JWT_REFRESH_TOKEN_EXPIRES = int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES', 2592000))
JWT_ALGORITHM = 'HS256'


def generate_access_token(user_id, username):
    """Generate JWT access token"""
    payload = {
        'user_id': user_id,
        'username': username,
        'type': 'access',
        'exp': datetime.utcnow() + timedelta(seconds=JWT_ACCESS_TOKEN_EXPIRES),
        'iat': datetime.utcnow()
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def generate_refresh_token(user_id, username):
    """Generate JWT refresh token and store in database"""
    payload = {
        'user_id': user_id,
        'username': username,
        'type': 'refresh',
        'exp': datetime.utcnow() + timedelta(seconds=JWT_REFRESH_TOKEN_EXPIRES),
        'iat': datetime.utcnow()
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    refresh_token = RefreshToken(
        user_id=user_id,
        token=token,
        expires_at=datetime.utcnow() + timedelta(seconds=JWT_REFRESH_TOKEN_EXPIRES)
    )
    db.session.add(refresh_token)
    db.session.commit()
    
    return token


def decode_token(token):
    """Decode and verify JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def token_required(f):
    """Decorator to protect routes requiring authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]
            except IndexError:
                return jsonify({
                    'success': False,
                    'error': 'Invalid authorization header format. Use: Bearer <token>'
                }), 401
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Authentication token is missing'
            }), 401
        
        payload = decode_token(token)
        
        if not payload:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired token'
            }), 401
        
        if payload.get('type') != 'access':
            return jsonify({
                'success': False,
                'error': 'Invalid token type'
            }), 401
        
        current_user = User.query.filter_by(id=payload['user_id']).first()
        
        if not current_user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 401
        
        if not current_user.is_active:
            return jsonify({
                'success': False,
                'error': 'Account is deactivated'
            }), 403
        
        return f(current_user, *args, **kwargs)
    
    return decorated


def revoke_refresh_token(token, user_id=None):
    """Revoke a refresh token.

    When ``user_id`` is provided, the token is only revoked when it belongs to
    that user. This prevents a user with a valid access token from revoking
    refresh tokens belonging to a different user (e.g. causing a denial of
    service if a token string is leaked).

    Returns True if a matching token was revoked, False otherwise.
    """
    query = RefreshToken.query.filter_by(token=token)
    if user_id is not None:
        query = query.filter_by(user_id=user_id)
    refresh_token = query.first()
    if refresh_token:
        refresh_token.is_revoked = True
        db.session.commit()
        return True
    return False


def revoke_all_user_refresh_tokens(user_id):
    """Revoke every active refresh token for the given user.

    Intended to be called after security-sensitive events (password change,
    account takeover suspicion, admin action) so that previously-issued
    refresh tokens can no longer be exchanged for new access tokens.

    Returns the number of tokens that were revoked.
    """
    count = RefreshToken.query.filter_by(
        user_id=user_id,
        is_revoked=False,
    ).update({'is_revoked': True})
    db.session.commit()
    return count