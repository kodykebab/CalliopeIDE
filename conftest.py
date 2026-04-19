import sys
import os

# ── 1. Fix sys.path so `server` is importable ────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

# ── 2. Set required env vars BEFORE any server module is imported ─────────────
#    These mirror the keys your real .env uses; safe dummy values for tests.
os.environ.setdefault('SECRET_KEY',         'test-secret-key-for-pytest')
os.environ.setdefault('JWT_SECRET_KEY',     'test-jwt-secret-key-for-pytest')
os.environ.setdefault('DATABASE_URL',       'sqlite:///:memory:')
os.environ.setdefault('FLASK_ENV',          'testing')
os.environ.setdefault('FRONTEND_URL',       'http://localhost:3000')
os.environ.setdefault('BACKEND_URL',        'http://localhost:5000')
os.environ.setdefault('GITHUB_CLIENT_ID',   '')
os.environ.setdefault('GITHUB_CLIENT_SECRET', '')
os.environ.setdefault('GOOGLE_CLIENT_ID',   '')
os.environ.setdefault('GOOGLE_CLIENT_SECRET', '')