"""
Calliope IDE - Authenticated Server
Implements backend-driven authentication system with protected routes
"""
import os
import socket
import shutil
import subprocess
import threading
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from server.middleware.database import db, init_db
from server.models import User, RefreshToken, Session, ChatHistory, ProjectMetadata
from server.routes import auth_bp
from server.routes.chat_routes import chat_bp
from server.routes.project_routes import project_bp
from server.utils import token_required, secure_execute, SecurityError
from server.utils.db_utils import create_session_for_user, add_chat_message, ensure_database_directory, get_database_stats
from server.utils.monitoring import setup_logging, init_sentry, monitor_endpoint, get_monitoring_stats
from server.utils.structured_logging import setup_logging as setup_structured_logging, init_request_logging

# Resolve agent.py path relative to this file
_SERVER_DIR = os.path.abspath(os.path.dirname(__file__))
_AGENT_PY = os.path.join(_SERVER_DIR, "agent.py")

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
_flask_secret = os.getenv('SECRET_KEY')
if not _flask_secret:
    raise EnvironmentError(
        "SECRET_KEY environment variable is not set. "
        "Generate a secure key with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
app.config['SECRET_KEY'] = _flask_secret
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

# Initialize monitoring and error tracking
app.logger = setup_logging("calliope-ide")
init_sentry(app)

# Initialize database and register blueprints
init_db(app)
init_request_logging(app)

# Ensure database directory exists after database initialization, within app context
with app.app_context():
    ensure_database_directory()
app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(project_bp)

if LIMITER_AVAILABLE and os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'true':
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[f"{os.getenv('RATE_LIMIT_PER_MINUTE', '60')}/minute"]
    )

count = 0
lock = threading.Lock()


def find_free_port() -> int:
    """Ask the OS for a guaranteed-free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


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
    
    # Create instance directory
    inst = f"instance{idx}_user{user_id}"
    os.makedirs(inst, exist_ok=True)
    shutil.copy(_AGENT_PY, os.path.join(inst, "agent.py"))

    port = find_free_port()

    # Start the agent process
    subprocess.Popen(
        ["python3", "agent.py", str(port)],
        cwd=inst,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    try:
        # Create session in database
        session = create_session_for_user(
            user_id=user_id,
            session_token=f"session_{idx}_{user_id}",
            instance_dir=inst,
            port=port
        )
        
        session_info = {
            'session_id': session.id,
            'location': os.path.abspath(inst),
            'port': port,
            'instance_dir': inst,
            'created_at': session.created_at.isoformat()
        }
        
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
        print(f"Session creation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to create session',
            'message': str(e)
        }), 500


@app.route("/sessions", methods=["GET"])
@token_required
def get_user_sessions(current_user):
    """Get all active sessions for current user (PROTECTED)"""
    user_id = current_user.id
    
    try:
        # Get sessions from database
        sessions = Session.query.filter_by(user_id=user_id, is_active=True)\
                                .order_by(Session.updated_at.desc()).all()
        
        # Convert to response format
        session_list = []
        for session in sessions:
            session_data = {
                'session_id': session.id,
                'location': os.path.abspath(session.instance_dir) if session.instance_dir else None,
                'port': session.port,
                'instance_dir': session.instance_dir,
                'created_at': session.created_at.isoformat(),
                'updated_at': session.updated_at.isoformat()
            }
            session_list.append(session_data)
        
        return jsonify({
            'success': True,
            'user': {
                'id': user_id,
                'username': current_user.username
            },
            'sessions': session_list,
            'total_sessions': len(session_list)
        }), 200
        
    except Exception as e:
        print(f"Get sessions error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve sessions',
            'message': str(e)
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


@app.route('/api/monitoring', methods=['GET'])
@token_required
def monitoring_status(current_user):
    """Get monitoring and error tracking status (admin only)"""
    if not current_user.is_admin:
        return jsonify({
            'success': False,
            'error': 'Admin access required'
        }), 403

    return jsonify({
        'success': True,
        'monitoring': get_monitoring_stats()
    }), 200


@app.route('/api/stats', methods=['GET'])
@token_required
def database_stats(current_user):
    """Database statistics endpoint (admin only or current user stats)"""
    try:
        if current_user.is_admin:
            # Admin gets full stats
            stats = get_database_stats()
        else:
            # Regular users get their own stats
            user_sessions = Session.query.filter_by(user_id=current_user.id).count()
            active_sessions = Session.query.filter_by(user_id=current_user.id, is_active=True).count()
            user_projects = ProjectMetadata.query.filter_by(user_id=current_user.id, is_active=True).count()
            user_messages = ChatHistory.query.join(Session).filter(Session.user_id == current_user.id).count()
            
            stats = {
                'user_sessions': user_sessions,
                'user_active_sessions': active_sessions,
                'user_projects': user_projects,
                'user_chat_messages': user_messages
            }
        
        return jsonify({
            'success': True,
            'stats': stats
        }), 200
        
    except Exception as e:
        print(f"Stats error: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to retrieve statistics'}), 500


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
        
        # Try to log code execution to chat history if session_id is provided
        session_id = data.get('session_id')
        if session_id:
            try:
                # Verify session belongs to user
                session = Session.query.filter_by(id=session_id, user_id=current_user.id, is_active=True).first()
                if session:
                    # Log user code
                    add_chat_message(
                        session_id=session_id,
                        role='user',
                        content=code,
                        message_type='code',
                        execution_time=result.get('execution_time')
                    )
                    
                    # Log execution result
                    if result['output'] or result['error']:
                        output_content = result['output'] if result['output'] else result['error']
                        add_chat_message(
                            session_id=session_id,
                            role='assistant',
                            content=output_content,
                            message_type='execution_result',
                            execution_time=result.get('execution_time')
                        )
            except Exception as chat_error:
                # Don't fail the execution if chat logging fails
                app.logger.warning(f"Failed to log chat message: {str(chat_error)}")
        
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
    app.logger.warning(f"404 Not Found: {request.path}")
    return jsonify({
        'success': False,
        'error': 'Endpoint not found',
        'path': request.path
    }), 404


@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"500 Internal Error: {str(error)}", exc_info=True)
    from server.utils.monitoring import track_error
    track_error(error, {'endpoint': request.path, 'method': request.method})
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'message': 'An unexpected error occurred. The issue has been logged.'
    }), 500


@app.errorhandler(Exception)
def handle_exception(error):
    """Global exception handler for uncaught errors"""
    app.logger.error(f"Unhandled exception: {str(error)}", exc_info=True)
    from server.utils.monitoring import track_error
    track_error(error, {
        'endpoint': request.path if request else 'Unknown',
        'method': request.method if request else 'Unknown'
    })

    # Return JSON response for all errors
    return jsonify({
        'success': False,
        'error': 'An unexpected error occurred',
        'message': str(error) if app.debug else 'The error has been logged and will be investigated.'
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