"""Input validation utilities for authentication"""
import re
from email_validator import validate_email, EmailNotValidError


def validate_email_format(email):
    """Validate email format"""
    try:
        validated = validate_email(email, check_deliverability=False)
        return True, None
    except EmailNotValidError as e:
        return False, str(e)


def validate_username(username):
    """Validate username format"""
    if not username:
        return False, "Username is required"
    
    if len(username) < 3:
        return False, "Username must be at least 3 characters long"
    
    if len(username) > 30:
        return False, "Username must be less than 30 characters"
    
    if not username[0].isalpha():
        return False, "Username must start with a letter"
    
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', username):
        return False, "Username can only contain letters, numbers, underscores, and hyphens"
    
    if '--' in username or '__' in username or '-_' in username or '_-' in username:
        return False, "Username cannot contain consecutive special characters"
    
    return True, None


def validate_password(password):
    """Validate password strength"""
    if not password:
        return False, "Password is required", 0
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters long", 0
    
    if len(password) > 128:
        return False, "Password must be less than 128 characters", 0
    
    has_upper = bool(re.search(r'[A-Z]', password))
    has_lower = bool(re.search(r'[a-z]', password))
    has_digit = bool(re.search(r'\d', password))
    has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))
    
    strength_score = sum([has_upper, has_lower, has_digit, has_special])
    
    if len(password) >= 12:
        strength_score += 1
    
    if not has_upper:
        return False, "Password must contain at least one uppercase letter", strength_score
    
    if not has_lower:
        return False, "Password must contain at least one lowercase letter", strength_score
    
    if not has_digit:
        return False, "Password must contain at least one number", strength_score
    
    return True, None, strength_score


def validate_registration_data(data):
    """Validate registration request data"""
    errors = {}
    
    email = data.get('email', '').strip()
    is_valid, error = validate_email_format(email)
    if not is_valid:
        errors['email'] = error
    
    username = data.get('username', '').strip()
    is_valid, error = validate_username(username)
    if not is_valid:
        errors['username'] = error
    
    password = data.get('password', '')
    is_valid, error, _ = validate_password(password)
    if not is_valid:
        errors['password'] = error
    
    password_confirm = data.get('password_confirm')
    if password_confirm is not None and password != password_confirm:
        errors['password_confirm'] = "Passwords do not match"
    
    return len(errors) == 0, errors


def validate_login_data(data):
    """Validate login request data"""
    errors = {}
    
    login = data.get('login', '').strip()
    if not login:
        errors['login'] = "Email or username is required"
    
    password = data.get('password', '')
    if not password:
        errors['password'] = "Password is required"
    
    return len(errors) == 0, errors


def sanitize_input(text, max_length=None):
    """Sanitize user input"""
    if not text:
        return ""
    
    text = text.strip()
    
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    return text