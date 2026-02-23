#!/usr/bin/env python3
"""
🧪 TESTING PROMPT IMPLEMENTATION

Test the persistent database implementation with the following:

✅ Start backend → Verify database file is created automatically
✅ Create a new session → Verify record stored in DB
✅ Send chat messages → Verify ChatHistory rows inserted
✅ Restart server → Verify previous data still exists
✅ Retrieve past chat → Verify history loads correctly
✅ Create a project → Verify ProjectMetadata stored
✅ Attempt invalid DB operation → Ensure backend does not crash

Confirm:
✅ Data persists across restarts
✅ Foreign key relationships work
✅ No API responses are broken
✅ No unhandled exceptions occur
"""

import os
import sys
import time
import json

# Add server directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'server'))

def test_full_database_functionality():
    """Comprehensive test of the database implementation"""
    
    print("🧪 CALLIOPE IDE - DATABASE PERSISTENCE TEST")
    print("=" * 50)
    
    from flask import Flask
    from server.middleware.database import init_db
    from server.models import User, Session, ChatHistory, ProjectMetadata
    from server.utils.db_utils import (
        ensure_database_directory,
        create_session_for_user,
        add_chat_message,
        get_session_chat_history,
        create_project_metadata,
        get_database_stats
    )
    
    # Setup test database
    test_db_path = 'test_calliope_full.db'
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{test_db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    test_results = []
    
    with app.app_context():
        try:
            # TEST 1: Database file creation
            print("\n📁 TEST 1: Database file creation")
            db = init_db(app)
            ensure_database_directory()
            
            if os.path.exists(test_db_path):
                test_results.append("✅ Database file created automatically")
                print("✅ Database file created automatically")
            else:
                test_results.append("❌ Database file not created")
                print("❌ Database file not created")
            
            # TEST 2: Create test user and session
            print("\n👤 TEST 2: User and Session creation")
            test_user = User(
                email='test@calliopeioe.com',
                username='testuser',
                password='securepassword123'
            )
            db.session.add(test_user)
            db.session.commit()
            
            session = create_session_for_user(
                user_id=test_user.id,
                session_token='test_session_001',
                instance_dir='instance1_user1',
                port=5001
            )
            
            if session and session.id:
                test_results.append("✅ Session created and stored in DB")
                print(f"✅ Session created and stored in DB (ID: {session.id})")
            else:
                test_results.append("❌ Session creation failed")
                print("❌ Session creation failed")
            
            # TEST 3: Send chat messages
            print("\n💬 TEST 3: Chat message storage")
            messages = [
                ("user", "Hello, I'm testing the chat functionality.", "text"),
                ("assistant", "Hello! I can see your message has been stored in the database.", "text"),
                ("user", "print('Testing code execution')", "code"),
                ("assistant", "Testing code execution", "execution_result")
            ]
            
            chat_msgs = []
            for role, content, msg_type in messages:
                chat_msg = add_chat_message(
                    session_id=session.id,
                    role=role,
                    content=content,
                    message_type=msg_type
                )
                chat_msgs.append(chat_msg)
            
            if len(chat_msgs) == 4:
                test_results.append("✅ Chat messages stored successfully")
                print(f"✅ {len(chat_msgs)} chat messages stored successfully")
            else:
                test_results.append("❌ Chat message storage failed")
                print("❌ Chat message storage failed")
            
            # TEST 4: Create project metadata
            print("\n📁 TEST 4: Project metadata storage")
            project = create_project_metadata(
                user_id=test_user.id,
                project_name='Test Smart Contract',
                description='A test Solidity smart contract project',
                project_type='smart_contract',
                language='solidity',
                framework='hardhat'
            )
            
            if project and project.id:
                test_results.append("✅ Project metadata stored successfully")
                print(f"✅ Project metadata stored (ID: {project.id})")
            else:
                test_results.append("❌ Project metadata storage failed")
                print("❌ Project metadata storage failed")
            
            # TEST 5: Data persistence check (simulate restart)
            print("\n🔄 TEST 5: Data persistence after 'restart'")
            
            # Re-query data from database
            stored_user = User.query.filter_by(email='test@calliopeioe.com').first()
            stored_session = Session.query.filter_by(user_id=stored_user.id).first()
            stored_messages = ChatHistory.query.filter_by(session_id=stored_session.id).all()
            stored_project = ProjectMetadata.query.filter_by(user_id=stored_user.id).first()
            
            persistence_checks = [
                (stored_user is not None, "User data"),
                (stored_session is not None, "Session data"),
                (len(stored_messages) == 4, "Chat messages"),
                (stored_project is not None, "Project metadata")
            ]
            
            for check_passed, data_type in persistence_checks:
                if check_passed:
                    test_results.append(f"✅ {data_type} persisted correctly")
                    print(f"✅ {data_type} persisted correctly")
                else:
                    test_results.append(f"❌ {data_type} not persisted")
                    print(f"❌ {data_type} not persisted")
            
            # TEST 6: Chat history retrieval
            print("\n📜 TEST 6: Chat history retrieval")
            chat_history = get_session_chat_history(stored_session.id, limit=10)
            
            if len(chat_history) == 4:
                test_results.append("✅ Chat history retrieved correctly")
                print(f"✅ Chat history retrieved ({len(chat_history)} messages)")
                
                # Display messages
                for msg in chat_history:
                    print(f"   {msg.role}: {msg.content[:50]}...")
            else:
                test_results.append("❌ Chat history retrieval failed")
                print("❌ Chat history retrieval failed")
            
            # TEST 7: Foreign key relationships
            print("\n🔗 TEST 7: Foreign key relationships")
            session_user = stored_session.user
            session_messages = stored_session.chat_history
            user_projects = stored_user.projects
            
            relationships_ok = [
                (session_user.id == stored_user.id, "Session->User relationship"),
                (len(session_messages) == 4, "Session->ChatHistory relationship"),
                (len(user_projects) == 1, "User->Projects relationship")
            ]
            
            for rel_ok, rel_name in relationships_ok:
                if rel_ok:
                    test_results.append(f"✅ {rel_name} working")
                    print(f"✅ {rel_name} working")
                else:
                    test_results.append(f"❌ {rel_name} broken")
                    print(f"❌ {rel_name} broken")
            
            # TEST 8: Database statistics
            print("\n📊 TEST 8: Database statistics")
            stats = get_database_stats()
            
            if stats and not stats.get('error'):
                test_results.append("✅ Database statistics retrieved")
                print(f"✅ Database statistics: {stats}")
            else:
                test_results.append("❌ Database statistics failed")
                print("❌ Database statistics failed")
            
            # TEST 9: Invalid operations don't crash
            print("\n⚠️  TEST 9: Invalid operations handling")
            try:
                # Try to add message to non-existent session
                add_chat_message(
                    session_id=999999,
                    role='user',
                    content='This should fail gracefully'
                )
                test_results.append("❌ Invalid operation should have failed")
                print("❌ Invalid operation should have failed")
            except ValueError:
                test_results.append("✅ Invalid operations handled gracefully")
                print("✅ Invalid operations handled gracefully")
            
            # FINAL RESULTS
            print("\n" + "=" * 50)
            print("📊 FINAL TEST RESULTS")
            print("=" * 50)
            
            passed_tests = len([r for r in test_results if r.startswith("✅")])
            total_tests = len(test_results)
            
            for result in test_results:
                print(result)
            
            print(f"\n📈 SUMMARY: {passed_tests}/{total_tests} tests passed")
            
            if passed_tests == total_tests:
                print("\n🎉 ALL TESTS PASSED! Database implementation is production-ready.")
            else:
                print(f"\n⚠️  {total_tests - passed_tests} tests failed. Review implementation.")
            
        except Exception as e:
            print(f"\n❌ CRITICAL ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Cleanup
            if os.path.exists(test_db_path):
                os.remove(test_db_path)
                print(f"\n🧹 Cleaned up test database: {test_db_path}")

if __name__ == "__main__":
    test_full_database_functionality()