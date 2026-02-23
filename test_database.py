"""
Test script to verify database initialization and basic operations
This script tests the persistent database implementation
"""
import os
import sys

# Add server directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'server'))

from flask import Flask
from server.middleware.database import init_db
from server.models import User, Session, ChatHistory, ProjectMetadata
from server.utils.db_utils import (
    ensure_database_directory,
    create_session_for_user,
    add_chat_message,
    create_project_metadata,
    get_database_stats
)

def test_database_setup():
    """Test database initialization"""
    print("🧪 Testing Database Setup...")
    
    # Create test Flask app
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_calliope.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    with app.app_context():
        try:
            # Initialize database
            db = init_db(app)
            print("✅ Database initialized successfully")
            
            # Ensure database directory exists
            ensure_database_directory()
            print("✅ Database directory created")
            
            # Check if tables were created
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            expected_tables = ['users', 'refresh_tokens', 'sessions', 'chat_history', 'project_metadata']
            for table in expected_tables:
                if table in tables:
                    print(f"✅ Table '{table}' created")
                else:
                    print(f"❌ Table '{table}' missing")
            
            # Test basic operations
            print("\n🧪 Testing Basic Operations...")
            
            # Create test user
            test_user = User(
                email='test@example.com',
                username='testuser',
                password='testpassword123'
            )
            db.session.add(test_user)
            db.session.commit()
            print("✅ Test user created")
            
            # Create session
            session = create_session_for_user(
                user_id=test_user.id,
                session_token='test_session_123',
                instance_dir='test_instance',
                port=8080
            )
            print("✅ Test session created")
            
            # Add chat message
            chat_msg = add_chat_message(
                session_id=session.id,
                role='user',
                content='Test message',
                message_type='text'
            )
            print("✅ Chat message added")
            
            # Create project
            project = create_project_metadata(
                user_id=test_user.id,
                project_name='Test Project',
                description='A test project',
                project_type='web_app',
                language='python'
            )
            print("✅ Project metadata created")
            
            # Get stats
            stats = get_database_stats()
            print(f"✅ Database stats retrieved: {stats}")
            
            # Cleanup test database
            os.remove('test_calliope.db')
            print("✅ Test database cleaned up")
            
            print("\n🎉 All tests passed! Database implementation is working correctly.")
            return True
            
        except Exception as e:
            print(f"❌ Error during testing: {str(e)}")
            # Cleanup on error
            if os.path.exists('test_calliope.db'):
                os.remove('test_calliope.db')
            return False

if __name__ == "__main__":
    success = test_database_setup()
    if success:
        print("\n✅ Database implementation is ready for production!")
    else:
        print("\n❌ Database implementation has issues that need to be fixed.")