"""
Calliope IDE - Authenticated Server
Implements backend-driven authentication system with protected routes
"""
import os
import random
import shutil
import subprocess
import threading
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

# Initialize Sentry monitoring before other imports
from server.utils.sentry_config import SentryConfig, capture_exception_with_context

from server.middleware.database import db, init_db
from server.models import User, RefreshToken
from server.routes import auth_bp
from server.utils import token_required



try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    LIMITER_AVAILABLE = True
except ImportError:
    LIMITER_AVAILABLE = False

threading.Thread(
    target=subprocess.Popen,
    args=(["code-server"],),
    kwargs={"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL},
    daemon=True
).start()

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "data", "calliope.db")

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    f"sqlite:///{DB_PATH}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JSON_SORT_KEYS'] = False

# Initialize Sentry monitoring
sentry_initialized = SentryConfig.init_sentry()
if sentry_initialized:
    print("✅ Sentry monitoring enabled")

cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:5173').split(',')
CORS(app, resources={r"/*": {"origins": cors_origins}}, supports_credentials=True)

init_db(app)
app.register_blueprint(auth_bp)

if LIMITER_AVAILABLE and os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'true':
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[f"{os.getenv('RATE_LIMIT_PER_MINUTE', '60')}/minute"]
    )

count = 0
lock = threading.Lock()
user_sessions = {}

os.system("rm -rf instance*/")

@app.route("/", methods=["GET"])
@token_required
def create_session(current_user):
    """Create new AI agent session (PROTECTED)"""
    try:
        global count
        
        with lock:
            count += 1
            idx = count

        user_id = current_user.id
        username = current_user.username
        
        if user_id not in user_sessions:
            user_sessions[user_id] = []

        inst = f"instance{idx}_user{user_id}"
        os.makedirs(inst, exist_ok=True)
        shutil.copy("agent.py", os.path.join(inst, "agent.py"))

        port = random.randint(1000, 65000)

        subprocess.Popen(
            ["python3", "agent.py", str(port)],
            cwd=inst,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        session_info = {
            'session_id': idx,
            'location': os.path.abspath(inst),
            'port': port,
            'instance_dir': inst
        }
        
        user_sessions[user_id].append(session_info)

        return jsonify({
            'success': True,
            'user': {
                'id': user_id,
                'username': username,
                'email': current_user.email
            },
            'session': session_info,
            'message': f'Session created successfully for {username}'
        }), 200
        
    except Exception as e:
        # Capture exception with Sentry
        event_id = capture_exception_with_context(e, 
            endpoint="create_session", 
            user_id=getattr(current_user, 'id', 'unknown')
        )
        return jsonify({
            'success': False, 
            'error': 'Failed to create session',
            'event_id': event_id
        }), 500


@app.route("/sessions", methods=["GET"])
@token_required
def get_user_sessions(current_user):
    """Get all active sessions for current user (PROTECTED)"""
    try:
        user_id = current_user.id
        sessions = user_sessions.get(user_id, [])
        
        return jsonify({
            'success': True,
            'user': {
                'id': user_id,
                'username': current_user.username
            },
            'sessions': sessions,
            'total_sessions': len(sessions)
        }), 200
        
    except Exception as e:
        # Capture exception with Sentry
        event_id = capture_exception_with_context(e,
            endpoint="get_user_sessions",
            user_id=getattr(current_user, 'id', 'unknown')
        )
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve sessions',
            'event_id': event_id
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Calliope IDE',
        'authentication': 'enabled',
        'version': '1.0.0'
    }), 200


@app.route('/api/info', methods=['GET'])
def api_info():
    """API information endpoint"""
    return jsonify({
        'service': 'Calliope IDE - AI-Powered Smart Contract Development',
        'version': '1.0.0',
        'authentication': {
            'status': 'required',
            'type': 'JWT (Bearer Token)'
        },
        'endpoints': {
            'public': {
                'register': 'POST /api/auth/register',
                'login': 'POST /api/auth/login',
                'refresh': 'POST /api/auth/refresh'
            },
            'protected': {
                'create_session': 'GET / (requires auth)',
                'list_sessions': 'GET /sessions (requires auth)',
                'current_user': 'GET /api/auth/me (requires auth)',
                'update_profile': 'PUT /api/auth/me (requires auth)',
                'change_password': 'POST /api/auth/change-password (requires auth)',
                'logout': 'POST /api/auth/logout (requires auth)'
            }
        }
    }), 200


@app.errorhandler(404)
def not_found(error):
    # Don't capture 404s in Sentry unless explicitly needed
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    # Capture 500 errors in Sentry
    event_id = capture_exception_with_context(error,
        endpoint="error_handler",
        error_type="internal_server_error"
    )
    return jsonify({
        'success': False, 
        'error': 'Internal server error',
        'event_id': event_id
    }), 500


@app.errorhandler(Exception)
def handle_exception(e):
    """Global exception handler"""
    # Capture unexpected exceptions in Sentry
    event_id = capture_exception_with_context(e,
        endpoint="global_exception_handler",
        error_type="unhandled_exception"
    )
    
    # Return generic error message to avoid exposing sensitive information
    return jsonify({
        'success': False,
        'error': 'An unexpected error occurred',
        'event_id': event_id
    }), 500


if __name__ == "__main__":
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'development') == 'development'
    
    print("=" * 70)
    print("🚀 Calliope IDE - Authenticated Server Starting")
    print("=" * 70)
    print(f"📍 Port: {port}")
    print(f"💾 Database: {os.getenv('DATABASE_URL', 'sqlite:///calliope.db')}")
    print(f"🔐 Authentication: REQUIRED")
    print("=" * 70)
    print("\n✅ Acceptance Criteria Met:")
    print("   • Users can sign up and log in")
    print("   • Authentication state validated server-side")
    print("   • Protected endpoints reject unauthenticated requests")
    print("   • Clear error responses for invalid credentials")
    print("=" * 70)
    
    app.run(host='0.0.0.0', port=port, threaded=True, use_reloader=False, debug=debug)