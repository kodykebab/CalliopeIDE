"""Tests for authentication utilities (Bug 1 regression)"""
import pytest
import os
import sys
from unittest.mock import patch


class TestHardcodedSecretKeyGuard:
    """Ensure auth_utils raises EnvironmentError when JWT_SECRET_KEY is unset"""

    def test_missing_jwt_secret_key_raises_error(self):
        """auth_utils should raise EnvironmentError when JWT_SECRET_KEY is unset"""
        # Temporarily remove JWT_SECRET_KEY from environment
        with patch.dict(os.environ, {}, clear=True):
            # Force reload of auth_utils to trigger the guard
            if 'server.utils.auth_utils' in sys.modules:
                del sys.modules['server.utils.auth_utils']

            with pytest.raises(EnvironmentError, match="JWT_SECRET_KEY environment variable is not set"):
                import server.utils.auth_utils

    def test_missing_flask_secret_key_raises_error(self):
        """start.py should raise EnvironmentError when SECRET_KEY is unset"""
        # Test this by checking the guard is present in start.py
        start_path = os.path.join(os.path.dirname(__file__), '..', 'start.py')
        with open(start_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert '_flask_secret = os.getenv(\'SECRET_KEY\')' in content
            assert 'if not _flask_secret:' in content
            assert 'raise EnvironmentError' in content


class TestJwtTokenRoundTrip:
    """Test JWT token generation and validation"""

    @pytest.fixture(autouse=True)
    def setup_env(self):
        """Set required environment variables"""
        with patch.dict(os.environ, {
            'JWT_SECRET_KEY': 'test-secret-key-for-testing-only',
            'SECRET_KEY': 'test-flask-secret-key',
            'DATABASE_URL': 'sqlite:///:memory:'
        }):
            yield

    def test_access_token_encodes_user_data(self):
        """Access token should encode correct user_id and type"""
        # Force reload with test environment
        if 'server.utils.auth_utils' in sys.modules:
            del sys.modules['server.utils.auth_utils']

        from server.utils.auth_utils import generate_access_token, decode_token

        token = generate_access_token(user_id=42, username="alice")
        payload = decode_token(token)

        assert payload is not None
        assert payload['user_id'] == 42
        assert payload['username'] == "alice"
        assert payload['type'] == 'access'

    def test_expired_token_returns_none(self):
        """Expired token should return None from decode_token"""
        if 'server.utils.auth_utils' in sys.modules:
            del sys.modules['server.utils.auth_utils']

        from server.utils.auth_utils import decode_token
        import jwt
        from datetime import datetime, timedelta

        # Create an expired token
        expired_payload = {
            'user_id': 1,
            'type': 'access',
            'exp': datetime.utcnow() - timedelta(hours=1)  # Expired 1 hour ago
        }
        expired_token = jwt.encode(expired_payload, 'test-secret-key-for-testing-only', algorithm='HS256')

        result = decode_token(expired_token)
        assert result is None

    def test_refresh_token_type_validation(self):
        """Refresh token type should be distinguishable from access token"""
        if 'server.utils.auth_utils' in sys.modules:
            del sys.modules['server.utils.auth_utils']

        from server.utils.auth_utils import generate_refresh_token, decode_token
        from server.middleware.database import db, init_db
        from flask import Flask

        # Create test Flask app
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        init_db(app)

        with app.app_context():
            db.create_all()
            token = generate_refresh_token(user_id=1, username="bob")
            payload = decode_token(token)

            assert payload is not None
            assert payload['type'] == 'refresh'
            assert payload['type'] != 'access'
