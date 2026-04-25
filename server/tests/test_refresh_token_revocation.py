"""Regression tests for refresh token revocation helpers.

Covers two security-sensitive behaviours that are used by the auth routes:

1. ``revoke_refresh_token`` must honour the optional ``user_id`` argument so
   that one authenticated user cannot revoke another user's refresh token.

2. ``revoke_all_user_refresh_tokens`` must revoke every active refresh token
   for a single user without touching other users' tokens. This is what
   /change-password calls to invalidate existing sessions.
"""
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from flask import Flask


@pytest.fixture
def app():
    """Build a minimal Flask app with an in-memory database for each test."""
    # Ensure JWT_SECRET_KEY is set before auth_utils is imported.
    with patch.dict(os.environ, {
        'JWT_SECRET_KEY': 'test-secret-key-for-testing-only',
        'SECRET_KEY': 'test-flask-secret-key',
        'DATABASE_URL': 'sqlite:///:memory:',
    }):
        # Force reload so module-level code picks up the env vars.
        for mod in (
            'server.utils.auth_utils',
            'server.middleware.database',
            'server.models',
            'server.models.refresh_token',
            'server.models.user',
        ):
            sys.modules.pop(mod, None)

        from server.middleware.database import db
        # Import models so SQLAlchemy registers the tables before create_all.
        from server.models import User, RefreshToken  # noqa: F401

        flask_app = Flask(__name__)
        flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(flask_app)

        with flask_app.app_context():
            db.create_all()
            yield flask_app
            db.session.remove()
            db.drop_all()


_TOKEN_COUNTER = {'n': 0}


def _make_refresh_token(user_id, username='user', offset_seconds=0):
    """Insert a RefreshToken row directly with a unique token string.

    The production helper ``generate_refresh_token`` embeds ``iat`` at second
    precision, which causes UNIQUE collisions when several tokens are issued
    in the same second. These tests only exercise the revocation helpers, so
    we just insert a row with a deterministic unique token string.
    """
    from server.middleware.database import db
    from server.models import RefreshToken

    _TOKEN_COUNTER['n'] += 1
    token_string = f'test-token-{user_id}-{_TOKEN_COUNTER["n"]}'
    row = RefreshToken(
        user_id=user_id,
        token=token_string,
        expires_at=datetime.utcnow() + timedelta(seconds=3600 + offset_seconds),
    )
    db.session.add(row)
    db.session.commit()
    return token_string


def _count_active_tokens(user_id):
    from server.models import RefreshToken
    return RefreshToken.query.filter_by(user_id=user_id, is_revoked=False).count()


class TestRevokeRefreshTokenOwnership:
    """revoke_refresh_token must not revoke tokens owned by other users."""

    def test_revokes_when_user_id_matches(self, app):
        from server.utils.auth_utils import revoke_refresh_token

        token = _make_refresh_token(user_id=1, username='alice')
        assert _count_active_tokens(1) == 1

        assert revoke_refresh_token(token, user_id=1) is True
        assert _count_active_tokens(1) == 0

    def test_does_not_revoke_when_user_id_mismatches(self, app):
        """Bug #1: /logout previously let any user revoke any refresh token."""
        from server.utils.auth_utils import revoke_refresh_token

        token = _make_refresh_token(user_id=1, username='alice')
        assert _count_active_tokens(1) == 1

        # User 2 tries to revoke user 1's token.
        result = revoke_refresh_token(token, user_id=2)

        assert result is False, "revoke must not succeed across users"
        assert _count_active_tokens(1) == 1, "victim's token must stay active"

    def test_backwards_compatible_without_user_id(self, app):
        """Callers that omit user_id (legacy callers) still work."""
        from server.utils.auth_utils import revoke_refresh_token

        token = _make_refresh_token(user_id=1, username='alice')
        assert revoke_refresh_token(token) is True
        assert _count_active_tokens(1) == 0

    def test_missing_token_returns_false(self, app):
        from server.utils.auth_utils import revoke_refresh_token
        assert revoke_refresh_token('not-a-real-token', user_id=1) is False


class TestRevokeAllUserRefreshTokens:
    """revoke_all_user_refresh_tokens is what /change-password relies on."""

    def test_revokes_every_active_token_for_user(self, app):
        from server.utils.auth_utils import revoke_all_user_refresh_tokens

        _make_refresh_token(user_id=1, username='alice')
        _make_refresh_token(user_id=1, username='alice')
        _make_refresh_token(user_id=1, username='alice')
        assert _count_active_tokens(1) == 3

        count = revoke_all_user_refresh_tokens(1)

        assert count == 3
        assert _count_active_tokens(1) == 0

    def test_does_not_touch_other_users_tokens(self, app):
        """Bug #2: changing user 1's password must NOT affect user 2."""
        from server.utils.auth_utils import revoke_all_user_refresh_tokens

        _make_refresh_token(user_id=1, username='alice')
        _make_refresh_token(user_id=2, username='bob')
        _make_refresh_token(user_id=2, username='bob')

        revoke_all_user_refresh_tokens(1)

        assert _count_active_tokens(1) == 0
        assert _count_active_tokens(2) == 2, "other users' sessions must remain"

    def test_is_idempotent(self, app):
        """Calling twice in a row is safe and reports zero the second time."""
        from server.utils.auth_utils import revoke_all_user_refresh_tokens

        _make_refresh_token(user_id=1, username='alice')

        first = revoke_all_user_refresh_tokens(1)
        second = revoke_all_user_refresh_tokens(1)

        assert first == 1
        assert second == 0

    def test_skips_already_revoked_tokens(self, app):
        from server.utils.auth_utils import (
            revoke_all_user_refresh_tokens,
            revoke_refresh_token,
        )

        t1 = _make_refresh_token(user_id=1, username='alice')
        _make_refresh_token(user_id=1, username='alice')
        revoke_refresh_token(t1, user_id=1)  # pre-revoke one

        count = revoke_all_user_refresh_tokens(1)

        # Only the remaining active token is newly revoked.
        assert count == 1
        assert _count_active_tokens(1) == 0

    def test_returns_zero_when_user_has_no_tokens(self, app):
        from server.utils.auth_utils import revoke_all_user_refresh_tokens
        assert revoke_all_user_refresh_tokens(999) == 0
