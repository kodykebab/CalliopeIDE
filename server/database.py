"""
Calliope IDE — Database Integration
Implements SQLite persistence for chat sessions and agent task logs.
Addresses TODO: Database Integration
"""

import os
import uuid
from datetime import datetime
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Text,
    DateTime,
    Boolean,
    Integer,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from sqlalchemy.exc import SQLAlchemyError

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///calliope.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── Models ────────────────────────────────────────────────────────────────────

class ChatSession(Base):
    """Represents a single user chat session with the Calliope agent."""

    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    title = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    messages = relationship(
        "ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )
    task_logs = relationship(
        "AgentTaskLog", back_populates="session", cascade="all, delete-orphan", order_by="AgentTaskLog.created_at"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "title": self.title,
            "is_active": self.is_active,
            "message_count": len(self.messages),
        }


class ChatMessage(Base):
    """A single message within a chat session (user or agent)."""

    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(16), nullable=False)  # "user" or "agent"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("ChatSession", back_populates="messages")

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
        }


class AgentTaskLog(Base):
    """Logs each agent task: the input, commands run, and final output."""

    __tablename__ = "agent_task_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False)
    user_input = Column(Text, nullable=False)
    commands_run = Column(Integer, default=0)
    final_output = Column(Text, nullable=True)
    success = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    session = relationship("ChatSession", back_populates="task_logs")

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_input": self.user_input,
            "commands_run": self.commands_run,
            "final_output": self.final_output,
            "success": self.success,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


# ── Init ──────────────────────────────────────────────────────────────────────

def init_db():
    """Create all tables if they don't exist. Safe to call on every startup."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Yield a database session. Use as a context manager or call close() when done."""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


# ── Session helpers ───────────────────────────────────────────────────────────

def create_session(title: str | None = None) -> ChatSession:
    """Create and persist a new chat session."""
    db = get_db()
    try:
        session = ChatSession(title=title)
        db.add(session)
        db.commit()
        db.refresh(session)
        return session
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


def get_session(session_id: str) -> ChatSession | None:
    """Fetch a chat session by ID, or None if not found."""
    db = get_db()
    try:
        return db.query(ChatSession).filter(ChatSession.id == session_id).first()
    finally:
        db.close()


def list_sessions(limit: int = 50) -> list[ChatSession]:
    """Return the most recent chat sessions."""
    db = get_db()
    try:
        return (
            db.query(ChatSession)
            .filter(ChatSession.is_active == True)
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()


def delete_session(session_id: str) -> bool:
    """Soft-delete a session by marking it inactive."""
    db = get_db()
    try:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            return False
        session.is_active = False
        db.commit()
        return True
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


# ── Message helpers ───────────────────────────────────────────────────────────

def add_message(session_id: str, role: str, content: str) -> ChatMessage:
    """Append a message to a session. Role must be 'user' or 'agent'."""
    if role not in ("user", "agent"):
        raise ValueError(f"role must be 'user' or 'agent', got '{role}'")
    db = get_db()
    try:
        msg = ChatMessage(session_id=session_id, role=role, content=content)
        db.add(msg)
        # Update session timestamp
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            session.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(msg)
        return msg
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


def get_messages(session_id: str) -> list[ChatMessage]:
    """Return all messages for a session in chronological order."""
    db = get_db()
    try:
        return (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
    finally:
        db.close()


# ── Task log helpers ──────────────────────────────────────────────────────────

def log_task(session_id: str, user_input: str) -> AgentTaskLog:
    """Create a task log entry when a new task starts."""
    db = get_db()
    try:
        task = AgentTaskLog(session_id=session_id, user_input=user_input)
        db.add(task)
        db.commit()
        db.refresh(task)
        return task
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


def complete_task(
    task_id: str,
    final_output: str,
    commands_run: int = 0,
    success: bool = True,
) -> AgentTaskLog | None:
    """Mark a task log as completed with its final output."""
    db = get_db()
    try:
        task = db.query(AgentTaskLog).filter(AgentTaskLog.id == task_id).first()
        if not task:
            return None
        task.final_output = final_output
        task.commands_run = commands_run
        task.success = success
        task.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(task)
        return task
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()
