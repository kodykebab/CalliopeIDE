"""Authentication routes for user registration, login, and token management"""
from flask import Blueprint, request, jsonify
from server.models import User, RefreshToken
from server.middleware.database import db
from server.utils.auth_utils import (
    generate_access_token,
    generate_refresh_token,
    decode_token,
    token_required,
    revoke_refresh_token
)
from server.utils.validators import (
    validate_registration_data,
    validate_login_data,
    sanitize_input,
    validate_password
)
from datetime import datetime
import logging
from server.utils.monitoring import capture_exception

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')
logger = logging.getLogger(__name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        is_valid, errors = validate_registration_data(data)
        if not is_valid:
            # Return the first error message for simplicity on the frontend
            first_error = next(iter(errors.values())) if errors else "Validation failed"
            return jsonify({'success': False, 'error': first_error, 'errors': errors}), 400
        
        email = sanitize_input(data['email'].lower(), 255)
        username = sanitize_input(data['username'], 80)
        password = data['password']
        full_name = sanitize_input(data.get('full_name', ''), 150) or None
        
        existing_user = User.query.filter(
            (User.email == email) | (User.username == username)
        ).first()
        
        if existing_user:
            if existing_user.email == email:
                return jsonify({'success': False, 'error': 'Email already registered'}), 400
            else:
                return jsonify({'success': False, 'error': 'Username already taken'}), 400
        
        new_user = User(email=email, username=username, password=password, full_name=full_name)
        db.session.add(new_user)
        db.session.commit()
        
        access_token = generate_access_token(new_user.id, new_user.username)
        refresh_token = generate_refresh_token(new_user.id, new_user.username)
        
        return jsonify({
            'success': True,
            'message': 'User registered successfully',
            'user': new_user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.exception("Registration error")
        capture_exception(e, {'route': 'auth.register'})
        return jsonify({'success': False, 'error': 'An error occurred during registration'}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user and return tokens"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        is_valid, errors = validate_login_data(data)
        if not is_valid:
            return jsonify({'success': False, 'errors': errors}), 400
        
        login = sanitize_input(data['login'].lower(), 255)
        password = data['password']
        
        user = User.query.filter((User.email == login) | (User.username == login)).first()
        
        if not user or not user.check_password(password):
            return jsonify({'success': False, 'error': 'Invalid email/username or password'}), 401
        
        if not user.is_active:
            return jsonify({'success': False, 'error': 'Account is deactivated'}), 403
        
        user.update_last_login()
        
        access_token = generate_access_token(user.id, user.username)
        refresh_token = generate_refresh_token(user.id, user.username)
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 200
        
    except Exception as e:
        logger.exception("Login error")
        capture_exception(e, {'route': 'auth.login'})
        return jsonify({'success': False, 'error': 'An error occurred during login'}), 500


@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """Refresh access token using refresh token"""
    try:
        data = request.get_json()
        
        if not data or 'refresh_token' not in data:
            return jsonify({'success': False, 'error': 'Refresh token is required'}), 400
        
        token = data['refresh_token']
        stored_token = RefreshToken.query.filter_by(token=token).first()
        
        if not stored_token:
            return jsonify({'success': False, 'error': 'Invalid refresh token'}), 401
        
        if stored_token.is_revoked:
            return jsonify({'success': False, 'error': 'Refresh token has been revoked'}), 401
        
        if stored_token.expires_at < datetime.utcnow():
            return jsonify({'success': False, 'error': 'Refresh token has expired'}), 401
        
        payload = decode_token(token)
        
        if not payload or payload.get('type') != 'refresh':
            return jsonify({'success': False, 'error': 'Invalid refresh token'}), 401
        
        user = User.query.filter_by(id=payload['user_id']).first()
        
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 401
        
        if not user.is_active:
            return jsonify({'success': False, 'error': 'Account is deactivated'}), 403
        
        access_token = generate_access_token(user.id, user.username)
        
        return jsonify({'success': True, 'access_token': access_token}), 200
        
    except Exception as e:
        logger.exception("Token refresh error")
        capture_exception(e, {'route': 'auth.refresh'})
        return jsonify({'success': False, 'error': 'An error occurred during token refresh'}), 500


@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout(current_user):
    """Logout user and revoke refresh token"""
    try:
        data = request.get_json()
        
        if not data or 'refresh_token' not in data:
            return jsonify({'success': False, 'error': 'Refresh token is required'}), 400
        
        token = data['refresh_token']
        revoke_refresh_token(token)
        
        return jsonify({'success': True, 'message': 'Logout successful'}), 200
        
    except Exception as e:
        logger.exception("Logout error")
        capture_exception(e, {'route': 'auth.logout', 'user_id': current_user.id})
        return jsonify({'success': False, 'error': 'An error occurred during logout'}), 500


@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user(current_user):
    """Get current user's information"""
    return jsonify({'success': True, 'user': current_user.to_dict(include_sensitive=True)}), 200


@auth_bp.route('/me', methods=['PUT'])
@token_required
def update_profile(current_user):
    """Update current user's profile"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        if 'full_name' in data:
            current_user.full_name = sanitize_input(data['full_name'], 150) or None
        
        if 'bio' in data:
            current_user.bio = sanitize_input(data['bio'], 500) or None
        
        if 'avatar_url' in data:
            current_user.avatar_url = sanitize_input(data['avatar_url'], 500) or None
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully',
            'user': current_user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.exception("Profile update error")
        capture_exception(e, {'route': 'auth.update_profile', 'user_id': current_user.id})
        return jsonify({'success': False, 'error': 'An error occurred during profile update'}), 500


@auth_bp.route('/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    """Change user's password"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
        new_password_confirm = data.get('new_password_confirm', '')
        
        if not current_user.check_password(current_password):
            return jsonify({'success': False, 'error': 'Current password is incorrect'}), 401
        
        is_valid, error, _ = validate_password(new_password)
        if not is_valid:
            return jsonify({'success': False, 'error': error}), 400
        
        if new_password != new_password_confirm:
            return jsonify({'success': False, 'error': 'New passwords do not match'}), 400
        
        current_user.set_password(new_password)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Password changed successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.exception("Password change error")
        capture_exception(e, {'route': 'auth.change_password', 'user_id': current_user.id})
        return jsonify({'success': False, 'error': 'An error occurred during password change'}), 500