"""
OAuth routes for Calliope IDE
Handles GitHub and Google OAuth 2.0 login flows.

Flow:
  1. Frontend calls  GET /api/auth/oauth/<provider>          → redirect URL
  2. User authorises on GitHub / Google
  3. Provider redirects to GET /api/auth/oauth/<provider>/callback?code=...&state=...
  4. Server exchanges code → access token → user profile
  5. Server upserts User row, issues JWT + refresh token
  6. Server redirects browser to  FRONTEND_URL/auth/callback?token=<jwt>&refresh=<refresh>
"""

import os
import secrets
import urllib.parse

import requests
from flask import Blueprint, jsonify, redirect, request, session

from server.middleware.database import db
from server.models import User, RefreshToken
from server.utils.auth_utils import generate_access_token, generate_refresh_token

oauth_bp = Blueprint('oauth', __name__, url_prefix='/api/auth/oauth')

# ------------------------------------------------------------------ #
# Configuration helpers
# ------------------------------------------------------------------ #

FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')

GITHUB_CLIENT_ID     = os.getenv('GITHUB_CLIENT_ID', '')
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET', '')

GOOGLE_CLIENT_ID     = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')

# Must match the "Authorized redirect URIs" in the provider dashboards
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:5000')


def _callback_url(provider: str) -> str:
    return f"{BACKEND_URL}/api/auth/oauth/{provider}/callback"


# ------------------------------------------------------------------ #
# State helpers  (CSRF protection)
# ------------------------------------------------------------------ #

import time

_STATE_STORE: dict[str, float] = {}  # state → expiry timestamp
_PENDING_TOKENS: dict[str, dict] = {}  # code → {access, refresh, expiry}
STATE_TTL = 600   # 10 min
CODE_TTL  = 60    # 1 min

def _prune():
    now = time.time()
    for store in (_STATE_STORE, _PENDING_TOKENS):
        dead = [k for k, v in store.items()
                if (v if isinstance(v, float) else v['expiry']) < now]
        for k in dead:
            del store[k]

def _new_state() -> str:
    _prune()
    state = secrets.token_urlsafe(32)
    _STATE_STORE[state] = time.time() + STATE_TTL
    return state

def _consume_state(state: str) -> bool:
    expiry = _STATE_STORE.pop(state, None)
    return expiry is not None and time.time() < expiry

# ------------------------------------------------------------------ #
# User upsert helper
# ------------------------------------------------------------------ #

def _upsert_oauth_user(email: str, provider: str, oauth_id: str,
                       full_name: str, avatar_url: str) -> User:
    """
    Find existing user by (provider, oauth_id) or email, create if needed.
    Linking: if a password-based account shares the email, attach OAuth to it.
    """
    # 1. Exact match on provider + oauth_id (fastest, most stable)
    user = User.query.filter_by(
        oauth_provider=provider, oauth_id=str(oauth_id)
    ).first()

    if user:
        # Refresh profile data on each login
        user.avatar_url = avatar_url or user.avatar_url
        user.full_name  = full_name  or user.full_name
        db.session.commit()
        return user

    # 2. Existing account with same email → link OAuth to it
    user = User.query.filter_by(email=email.lower().strip()).first()
    if user:
        user.oauth_provider = provider
        user.oauth_id       = str(oauth_id)
        user.is_verified    = True
        user.avatar_url     = avatar_url or user.avatar_url
        user.full_name      = full_name  or user.full_name
        db.session.commit()
        return user

    # 3. Brand-new user
    base_username = (full_name or email.split('@')[0]).replace(' ', '_').lower()
    username = base_username
    counter  = 1
    while User.query.filter_by(username=username).first():
        username = f"{base_username}{counter}"
        counter += 1

    user = User.create_oauth_user(
        email=email,
        username=username,
        full_name=full_name,
        avatar_url=avatar_url,
        oauth_provider=provider,
        oauth_id=str(oauth_id),
    )
    db.session.add(user)
    db.session.commit()
    return user

def _issue_tokens_redirect(user: User) -> str:
    """Store tokens server-side; send a short-lived one-time code to the browser."""
    code = secrets.token_urlsafe(32)
    _PENDING_TOKENS[code] = {
        'access':  generate_access_token(user.id, user.username),
        'refresh': generate_refresh_token(user.id, user.username),
        'expiry':  time.time() + CODE_TTL,
    }
    return f"{FRONTEND_URL}/auth/callback?code={code}"
# ================================================================== #
#  GITHUB
# ================================================================== #

@oauth_bp.route('/github', methods=['GET'])
def github_login():
    """Return the GitHub authorization URL (or redirect to it)."""
    if not GITHUB_CLIENT_ID:
        return jsonify({'error': 'GitHub OAuth not configured'}), 501

    state = _new_state()
    params = urllib.parse.urlencode({
        'client_id':    GITHUB_CLIENT_ID,
        'redirect_uri': _callback_url('github'),
        'scope':        'read:user user:email',
        'state':        state,
    })
    auth_url = f"https://github.com/login/oauth/authorize?{params}"

    # If called from the browser directly → redirect; if called as API → return JSON
    if request.headers.get('Accept', '').startswith('text/html'):
        return redirect(auth_url)
    return jsonify({'auth_url': auth_url, 'state': state}), 200


@oauth_bp.route('/github/callback', methods=['GET'])
def github_callback():
    """Exchange GitHub code for access token, upsert user, issue JWT."""
    code  = request.args.get('code')
    state = request.args.get('state')

    if not code or not state:
        return _error_redirect('Missing code or state parameter')
    if not _consume_state(state):
        return _error_redirect('Invalid or expired state — possible CSRF attack')

    # Exchange code → GitHub access token
    token_resp = requests.post(
        'https://github.com/login/oauth/access_token',
        headers={'Accept': 'application/json'},
        json={
            'client_id':     GITHUB_CLIENT_ID,
            'client_secret': GITHUB_CLIENT_SECRET,
            'code':          code,
            'redirect_uri':  _callback_url('github'),
        },
        timeout=10,
    )
    if token_resp.status_code != 200:
        return _error_redirect('Failed to exchange GitHub code')

    gh_token = token_resp.json().get('access_token')
    if not gh_token:
        return _error_redirect('No access token in GitHub response')

    headers = {'Authorization': f'token {gh_token}', 'Accept': 'application/json'}

    # Fetch user profile
    profile_resp = requests.get('https://api.github.com/user', headers=headers, timeout=10)
    if profile_resp.status_code != 200:
        return _error_redirect('Failed to fetch GitHub profile')

    profile = profile_resp.json()

    # Fetch verified primary email (profile.email may be None if private)
    email = profile.get('email')
    if not email:
        emails_resp = requests.get('https://api.github.com/user/emails', headers=headers, timeout=10)
        if emails_resp.status_code == 200:
            for e in emails_resp.json():
                if e.get('primary') and e.get('verified'):
                    email = e['email']
                    break

    if not email:
        return _error_redirect('No verified email found on GitHub account')

    user = _upsert_oauth_user(
        email=email,
        provider='github',
        oauth_id=profile['id'],
        full_name=profile.get('name') or profile.get('login', ''),
        avatar_url=profile.get('avatar_url', ''),
    )
    user.update_last_login()
    return redirect(_issue_tokens_redirect(user))


# ================================================================== #
#  GOOGLE
# ================================================================== #

@oauth_bp.route('/google', methods=['GET'])
def google_login():
    """Return the Google authorization URL."""
    if not GOOGLE_CLIENT_ID:
        return jsonify({'error': 'Google OAuth not configured'}), 501

    state = _new_state()
    params = urllib.parse.urlencode({
        'client_id':             GOOGLE_CLIENT_ID,
        'redirect_uri':          _callback_url('google'),
        'response_type':         'code',
        'scope':                 'openid email profile',
        'access_type':           'offline',
        'prompt':                'select_account',
        'state':                 state,
    })
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"

    if request.headers.get('Accept', '').startswith('text/html'):
        return redirect(auth_url)
    return jsonify({'auth_url': auth_url, 'state': state}), 200


@oauth_bp.route('/google/callback', methods=['GET'])
def google_callback():
    """Exchange Google code for tokens, upsert user, issue JWT."""
    code  = request.args.get('code')
    state = request.args.get('state')

    if not code or not state:
        return _error_redirect('Missing code or state parameter')
    if not _consume_state(state):
        return _error_redirect('Invalid or expired state — possible CSRF attack')

    # Exchange code → Google tokens
    token_resp = requests.post(
        'https://oauth2.googleapis.com/token',
        data={
            'client_id':     GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'code':          code,
            'redirect_uri':  _callback_url('google'),
            'grant_type':    'authorization_code',
        },
        timeout=10,
    )
    if token_resp.status_code != 200:
        return _error_redirect('Failed to exchange Google code')

    google_access_token = token_resp.json().get('access_token')
    if not google_access_token:
        return _error_redirect('No access token in Google response')

    # Fetch user info
    userinfo_resp = requests.get(
        'https://www.googleapis.com/oauth2/v2/userinfo',
        headers={'Authorization': f'Bearer {google_access_token}'},
        timeout=10,
    )
    if userinfo_resp.status_code != 200:
        return _error_redirect('Failed to fetch Google user info')

    info = userinfo_resp.json()
    email = info.get('email')
    if not email:
        return _error_redirect('No email returned by Google')

    user = _upsert_oauth_user(
        email=email,
        provider='google',
        oauth_id=info['id'],
        full_name=info.get('name', ''),
        avatar_url=info.get('picture', ''),
    )
    user.update_last_login()
    return redirect(_issue_tokens_redirect(user))

@oauth_bp.route('/exchange', methods=['POST'])
def exchange_code():
    """Exchange a one-time OAuth code for real tokens. POST { code: str }"""
    code = (request.get_json() or {}).get('code')
    if not code:
        return jsonify({'error': 'Missing code'}), 400

    entry = _PENDING_TOKENS.pop(code, None)
    if not entry or time.time() > entry['expiry']:
        return jsonify({'error': 'Invalid or expired code'}), 400

    return jsonify({
        'access_token':  entry['access'],
        'refresh_token': entry['refresh'],
    }), 200
    
# ------------------------------------------------------------------ #
# Error helper
# ------------------------------------------------------------------ #

def _error_redirect(message: str) -> 'Response':
    params = urllib.parse.urlencode({'error': message})
    return redirect(f"{FRONTEND_URL}/auth/callback?{params}")