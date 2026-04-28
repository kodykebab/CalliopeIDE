"""
Tests for OAuth routes.
Run with: pytest tests/test_oauth.py -v
"""
import time
import pytest
from unittest.mock import patch, MagicMock

from server.start import app
from server.middleware.database import db
from server.routes.oauth_routes import (
    _new_state, _consume_state, _STATE_STORE,
    _PENDING_TOKENS, _issue_tokens_redirect,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.drop_all()


@pytest.fixture(autouse=True)
def clear_stores():
    """Wipe state + token stores between tests."""
    _STATE_STORE.clear()
    _PENDING_TOKENS.clear()
    yield
    _STATE_STORE.clear()
    _PENDING_TOKENS.clear()


# ── State store ───────────────────────────────────────────────────────────────

class TestStateStore:
    def test_new_state_returns_string(self):
        state = _new_state()
        assert isinstance(state, str)
        assert len(state) > 20

    def test_consume_state_valid(self):
        state = _new_state()
        assert _consume_state(state) is True

    def test_consume_state_one_time_only(self):
        state = _new_state()
        _consume_state(state)
        assert _consume_state(state) is False  # second call must fail

    def test_consume_state_unknown(self):
        assert _consume_state('not-a-real-state') is False

    def test_expired_state_rejected(self):
        state = _new_state()
        # Manually expire it
        _STATE_STORE[state] = time.time() - 1
        assert _consume_state(state) is False


# ── Login redirect endpoints ───────────────────────────────────────────────────

class TestLoginEndpoints:
    def test_github_login_returns_auth_url(self, client):
        with patch('server.routes.oauth_routes.GITHUB_CLIENT_ID', 'test-id'):
            res = client.get('/api/auth/oauth/github',
                             headers={'Accept': 'application/json'})
        assert res.status_code == 200
        data = res.get_json()
        assert 'auth_url' in data
        assert 'github.com/login/oauth/authorize' in data['auth_url']
        assert 'state' in data

    def test_google_login_returns_auth_url(self, client):
        with patch('server.routes.oauth_routes.GOOGLE_CLIENT_ID', 'test-id'):
            res = client.get('/api/auth/oauth/google',
                             headers={'Accept': 'application/json'})
        assert res.status_code == 200
        data = res.get_json()
        assert 'auth_url' in data
        assert 'accounts.google.com' in data['auth_url']

    def test_github_login_unconfigured(self, client):
        with patch('server.routes.oauth_routes.GITHUB_CLIENT_ID', ''):
            res = client.get('/api/auth/oauth/github',
                             headers={'Accept': 'application/json'})
        assert res.status_code == 501

    def test_google_login_unconfigured(self, client):
        with patch('server.routes.oauth_routes.GOOGLE_CLIENT_ID', ''):
            res = client.get('/api/auth/oauth/google',
                             headers={'Accept': 'application/json'})
        assert res.status_code == 501


# ── Token exchange endpoint ────────────────────────────────────────────────────

class TestTokenExchange:
    def _plant_code(self, access='acc', refresh='ref', offset=60):
        """Insert a valid pending code into the store."""
        import secrets
        code = secrets.token_urlsafe(16)
        _PENDING_TOKENS[code] = {
            'access':  access,
            'refresh': refresh,
            'expiry':  time.time() + offset,
        }
        return code

    def test_valid_exchange(self, client):
        code = self._plant_code()
        res = client.post('/api/auth/oauth/exchange',
                          json={'code': code})
        assert res.status_code == 200
        data = res.get_json()
        assert data['access_token']  == 'acc'
        assert data['refresh_token'] == 'ref'

    def test_code_consumed_after_use(self, client):
        code = self._plant_code()
        client.post('/api/auth/oauth/exchange', json={'code': code})
        # Second attempt must fail
        res = client.post('/api/auth/oauth/exchange', json={'code': code})
        assert res.status_code == 400

    def test_expired_code_rejected(self, client):
        code = self._plant_code(offset=-1)   # already expired
        res = client.post('/api/auth/oauth/exchange', json={'code': code})
        assert res.status_code == 400

    def test_missing_code(self, client):
        res = client.post('/api/auth/oauth/exchange', json={})
        assert res.status_code == 400

    def test_unknown_code(self, client):
        res = client.post('/api/auth/oauth/exchange',
                          json={'code': 'totally-fake-code'})
        assert res.status_code == 400


# ── Callback endpoints (CSRF + missing params) ────────────────────────────────

class TestCallbacks:
    def test_github_callback_missing_params(self, client):
        res = client.get('/api/auth/oauth/github/callback')
        # Should redirect to frontend error page
        assert res.status_code == 302
        assert 'error' in res.headers['Location']

    def test_github_callback_invalid_state(self, client):
        res = client.get('/api/auth/oauth/github/callback'
                         '?code=abc&state=invalid-state')
        assert res.status_code == 302
        assert 'error' in res.headers['Location']

    def test_google_callback_missing_params(self, client):
        res = client.get('/api/auth/oauth/google/callback')
        assert res.status_code == 302
        assert 'error' in res.headers['Location']

    def test_google_callback_invalid_state(self, client):
        res = client.get('/api/auth/oauth/google/callback'
                         '?code=abc&state=invalid-state')
        assert res.status_code == 302
        assert 'error' in res.headers['Location']

    @patch('server.routes.oauth_routes.requests.post')
    @patch('server.routes.oauth_routes.requests.get')
    def test_github_callback_full_flow(self, mock_get, mock_post, client):
        state = _new_state()

        # Token exchange
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'access_token': 'gh-token'},
        )
        # Profile + emails
        profile = {'id': 99, 'name': 'Test User', 'login': 'testuser',
                   'email': 'test@example.com', 'avatar_url': 'https://example.com/av.png'}
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: profile,
        )

        res = client.get(f'/api/auth/oauth/github/callback'
                         f'?code=real-code&state={state}')

        assert res.status_code == 302
        location = res.headers['Location']
        # Should redirect to frontend with one-time code, NOT raw token
        assert 'code=' in location
        assert 'access_token' not in location
        assert 'refresh_token' not in location

    @patch('server.routes.oauth_routes.requests.post')
    @patch('server.routes.oauth_routes.requests.get')
    def test_google_callback_full_flow(self, mock_get, mock_post, client):
        state = _new_state()

        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'access_token': 'google-token'},
        )
        userinfo = {'id': '42', 'email': 'google@example.com',
                    'name': 'Google User', 'picture': 'https://example.com/pic.png'}
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: userinfo,
        )

        res = client.get(f'/api/auth/oauth/google/callback'
                         f'?code=real-code&state={state}')

        assert res.status_code == 302
        location = res.headers['Location']
        assert 'code=' in location
        assert 'access_token' not in location


# ── User upsert logic ─────────────────────────────────────────────────────────

class TestUpsertOAuthUser:
    from server.routes.oauth_routes import _upsert_oauth_user

    def test_creates_new_user(self, client):
        from server.models.user import User
        from server.routes.oauth_routes import _upsert_oauth_user
        with app.app_context():
            user = _upsert_oauth_user(
                email='new@example.com',
                provider='github',
                oauth_id='111',
                full_name='New User',
                avatar_url='https://example.com/av.png',
            )
            assert user.id is not None
            assert user.email == 'new@example.com'
            assert user.is_verified is True

    def test_links_existing_password_user(self, client):
        from server.models.user import User
        from server.routes.oauth_routes import _upsert_oauth_user
        with app.app_context():
            existing = User(email='existing@example.com',
                            username='existing', password='secret')
            db.session.add(existing)
            db.session.commit()

            linked = _upsert_oauth_user(
                email='existing@example.com',
                provider='github',
                oauth_id='222',
                full_name='Existing User',
                avatar_url='',
            )
            assert linked.id == existing.id
            assert linked.oauth_provider == 'github'
            assert linked.is_verified is True

    def test_returns_existing_oauth_user(self, client):
        from server.routes.oauth_routes import _upsert_oauth_user
        with app.app_context():
            first  = _upsert_oauth_user('repeat@example.com', 'github',
                                         '333', 'Repeat', '')
            second = _upsert_oauth_user('repeat@example.com', 'github',
                                         '333', 'Repeat Updated', '')
            assert first.id == second.id

    def test_username_collision_resolved(self, client):
        from server.models.user import User
        from server.routes.oauth_routes import _upsert_oauth_user
        with app.app_context():
            # Plant a user whose username matches the derived one
            blocker = User(email='other@example.com',
                           username='john_doe', password='x')
            db.session.add(blocker)
            db.session.commit()

            user = _upsert_oauth_user('john.doe@example.com', 'google',
                                       '444', 'John Doe', '')
            assert user.username != 'john_doe'
            assert user.username.startswith('john_doe')