"""Chat routes for managing chat history and messages"""
from flask import Blueprint, request, jsonify
from server.models import Session, ChatHistory
from server.middleware.database import db
from server.utils.auth_utils import token_required
from server.utils.db_utils import (
    add_chat_message,
    get_session_chat_history,
    get_session_by_id
)

chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')


@chat_bp.route('/message', methods=['POST'])
@token_required
def send_message(current_user):
    """Send a chat message and store it in the database"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Required fields
        session_id = data.get('session_id')
        role = data.get('role', 'user')
        content = data.get('content')
        
        if not session_id:
            return jsonify({'success': False, 'error': 'Session ID is required'}), 400
        
        if not content:
            return jsonify({'success': False, 'error': 'Message content is required'}), 400
        
        # Verify session belongs to current user
        session = Session.query.filter_by(id=session_id, user_id=current_user.id, is_active=True).first()
        if not session:
            return jsonify({'success': False, 'error': 'Session not found or access denied'}), 404
        
        # Optional fields
        message_type = data.get('message_type', None)
        execution_time = data.get('execution_time', None)
        
        # Validate role
        if role not in ['user', 'assistant']:
            role = 'user'
        
        # Add message to database
        chat_message = add_chat_message(
            session_id=session_id,
            role=role,
            content=content,
            message_type=message_type,
            execution_time=execution_time
        )
        
        return jsonify({
            'success': True,
            'message': 'Chat message saved successfully',
            'chat_message': chat_message.to_dict()
        }), 201
        
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        print(f"Send message error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while saving the message'}), 500


@chat_bp.route('/history/<int:session_id>', methods=['GET'])
@token_required
def get_chat_history(current_user, session_id):
    """Get chat history for a session"""
    try:
        # Verify session belongs to current user
        session = Session.query.filter_by(id=session_id, user_id=current_user.id).first()
        if not session:
            return jsonify({'success': False, 'error': 'Session not found or access denied'}), 404
        
        # Get pagination parameters
        limit = min(int(request.args.get('limit', 50)), 100)  # Max 100 messages
        offset = max(int(request.args.get('offset', 0)), 0)
        
        # Get chat history
        messages = get_session_chat_history(session_id, limit, offset)
        
        # Get total count for pagination
        total_messages = ChatHistory.query.filter_by(session_id=session_id).count()
        
        return jsonify({
            'success': True,
            'session': session.to_dict(),
            'messages': [msg.to_dict() for msg in messages],
            'pagination': {
                'total': total_messages,
                'limit': limit,
                'offset': offset,
                'has_more': offset + limit < total_messages
            }
        }), 200
        
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        print(f"Get chat history error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while retrieving chat history'}), 500


@chat_bp.route('/recent/<int:session_id>', methods=['GET'])
@token_required
def get_recent_messages(current_user, session_id):
    """Get recent messages for a session"""
    try:
        # Verify session belongs to current user
        session = Session.query.filter_by(id=session_id, user_id=current_user.id).first()
        if not session:
            return jsonify({'success': False, 'error': 'Session not found or access denied'}), 404
        
        # Get recent messages
        limit = min(int(request.args.get('limit', 10)), 50)  # Max 50 recent messages
        messages = ChatHistory.get_recent_messages(session_id, limit)
        
        # Reverse to get chronological order (oldest to newest)
        messages.reverse()
        
        return jsonify({
            'success': True,
            'session': session.to_dict(),
            'messages': [msg.to_dict() for msg in messages],
            'count': len(messages)
        }), 200
        
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        print(f"Get recent messages error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while retrieving recent messages'}), 500


@chat_bp.route('/sessions', methods=['GET'])
@token_required
def get_user_chat_sessions(current_user):
    """Get all chat sessions for the current user"""
    try:
        # Get user sessions with optional filtering
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        
        if active_only:
            sessions = Session.query.filter_by(user_id=current_user.id, is_active=True)\
                                    .order_by(Session.updated_at.desc()).all()
        else:
            sessions = Session.query.filter_by(user_id=current_user.id)\
                                    .order_by(Session.updated_at.desc()).all()
        
        # Add message count for each session
        session_data = []
        for session in sessions:
            session_dict = session.to_dict()
            session_dict['message_count'] = ChatHistory.query.filter_by(session_id=session.id).count()
            session_dict['last_message'] = None
            
            # Get last message if exists
            last_message = ChatHistory.query.filter_by(session_id=session.id)\
                                           .order_by(ChatHistory.timestamp.desc()).first()
            if last_message:
                session_dict['last_message'] = {
                    'content_preview': last_message.content[:100] + '...' if len(last_message.content) > 100 else last_message.content,
                    'role': last_message.role,
                    'timestamp': last_message.timestamp.isoformat()
                }
            
            session_data.append(session_dict)
        
        return jsonify({
            'success': True,
            'sessions': session_data,
            'total_sessions': len(sessions)
        }), 200
        
    except Exception as e:
        print(f"Get user sessions error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while retrieving sessions'}), 500


@chat_bp.route('/session/<int:session_id>/deactivate', methods=['POST'])
@token_required
def deactivate_chat_session(current_user, session_id):
    """Deactivate a chat session"""
    try:
        # Verify session belongs to current user
        session = Session.query.filter_by(id=session_id, user_id=current_user.id).first()
        if not session:
            return jsonify({'success': False, 'error': 'Session not found or access denied'}), 404
        
        session.deactivate()
        
        return jsonify({
            'success': True,
            'message': 'Session deactivated successfully',
            'session': session.to_dict()
        }), 200
        
    except Exception as e:
        print(f"Deactivate session error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while deactivating the session'}), 500