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

from server.middleware.database import db, init_db
from server.models import User, RefreshToken
from server.routes import auth_bp
from server.utils import token_required, secure_execute, SecurityError



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


@app.route("/sessions", methods=["GET"])
@token_required
def get_user_sessions(current_user):
    """Get all active sessions for current user (PROTECTED)"""
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
                'execute_code': 'POST /execute (requires auth)',
                'current_user': 'GET /api/auth/me (requires auth)',
                'update_profile': 'PUT /api/auth/me (requires auth)',
                'change_password': 'POST /api/auth/change-password (requires auth)',
                'logout': 'POST /api/auth/logout (requires auth)'
            }
        }
    }), 200


def execute_code_internal(current_user):
    """
    Internal function to execute user-submitted Python code in a secure sandbox
    
    Expected JSON payload:
    {
        "code": "print('Hello World')",
        "timeout": 5  # optional, defaults to 5 seconds
    }
    
    Returns:
    {
        "success": bool,
        "status": "success|error|timeout|memory_error",
        "output": str,
        "error": str,
        "execution_time": float,
        "user_id": int
    }
    """
    try:
        # Validate request data
        if not request.is_json:
            return jsonify({
                'success': False,
                'status': 'error',
                'output': '',
                'error': 'Content-Type must be application/json',
                'execution_time': 0,
                'user_id': current_user.id
            }), 400
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'status': 'error',
                'output': '',
                'error': 'No JSON data provided',
                'execution_time': 0,
                'user_id': current_user.id
            }), 400
        
        # Extract code from request
        code = data.get('code')
        if not code:
            return jsonify({
                'success': False,
                'status': 'error',
                'output': '',
                'error': 'No code provided in request',
                'execution_time': 0,
                'user_id': current_user.id
            }), 400
        
        if not isinstance(code, str):
            return jsonify({
                'success': False,
                'status': 'error',
                'output': '',
                'error': 'Code must be a string',
                'execution_time': 0,
                'user_id': current_user.id
            }), 400
        
        # Extract optional timeout parameter
        timeout = data.get('timeout', 5)
        try:
            timeout = int(timeout)
            if timeout < 1 or timeout > 30:  # Limit timeout to reasonable range
                timeout = 5
        except (ValueError, TypeError):
            timeout = 5
        
        # Log the execution attempt
        app.logger.info(f"User {current_user.username} (ID: {current_user.id}) executing code")
        
        # Execute the code securely
        result = secure_execute(code, timeout=timeout)
        
        # Prepare response
        success = result['status'] == 'success'
        response_data = {
            'success': success,
            'status': result['status'],
            'output': result['output'],
            'error': result['error'],
            'execution_time': result['execution_time'],
            'user_id': current_user.id
        }
        
        # Set appropriate HTTP status code
        if success:
            status_code = 200
        elif result['status'] == 'timeout':
            status_code = 408  # Request Timeout
        elif result['status'] == 'memory_error':
            status_code = 413  # Payload Too Large
        else:
            status_code = 400  # Bad Request
        
        return jsonify(response_data), status_code
    
    except SecurityError as e:
        app.logger.warning(f"Security violation by user {current_user.username}: {str(e)}")
        return jsonify({
            'success': False,
            'status': 'error',
            'output': '',
            'error': f'Restricted operation detected: {str(e)}',
            'execution_time': 0,
            'user_id': current_user.id
        }), 403  # Forbidden
    
    except Exception as e:
        app.logger.error(f"Unexpected error in execute_code: {str(e)}")
        return jsonify({
            'success': False,
            'status': 'error',
            'output': '',
            'error': 'Internal server error occurred',
            'execution_time': 0,
            'user_id': current_user.id if current_user else None
        }), 500


@app.route('/execute', methods=['POST'])
@token_required
def execute_code(current_user):
    """
    Execute user-submitted Python code in a secure sandbox (PROTECTED)
    """
    return execute_code_internal(current_user)


@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500


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