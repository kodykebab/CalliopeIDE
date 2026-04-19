"""
Streaming chat routes for Calliope IDE AI assistant.
Addresses issue #56 — AI responses appear progressively in the UI.

Endpoints:
  POST /api/chat/stream     — stream AI response via Server-Sent Events
  POST /api/chat/stream/stop — stop an in-progress stream
"""

import json
import time
import uuid
import logging
import threading
from contextvars import ContextVar
from flask import Blueprint, request, Response, stream_with_context
from server.utils.auth_utils import token_required
from server.utils.monitoring import capture_exception

try:
    from server.models import Session, ChatHistory
    from server.middleware.database import db
    from server.utils.db_utils import add_chat_message
except Exception:
    Session = None  # type: ignore
    ChatHistory = None  # type: ignore
    db = None  # type: ignore
    add_chat_message = None  # type: ignore

logger = logging.getLogger(__name__)

streaming_chat_bp = Blueprint("streaming_chat", __name__, url_prefix="/api/chat")

# ── In-memory stream registry ─────────────────────────────────────────────────
# Maps stream_id → stop event so clients can cancel streams.
_active_streams: dict[str, threading.Event] = {}
_streams_lock = threading.Lock()


def _register_stream(stream_id: str) -> threading.Event:
    stop_event = threading.Event()
    with _streams_lock:
        _active_streams[stream_id] = stop_event
    return stop_event


def _deregister_stream(stream_id: str) -> None:
    with _streams_lock:
        _active_streams.pop(stream_id, None)


# ── SSE helper ────────────────────────────────────────────────────────────────

def _sse(event_type: str, data: dict) -> str:
    """Format a single SSE frame."""
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"


def _sse_bytes(event_type: str, data: dict) -> bytes:
    return _sse(event_type, data).encode()


# ── Gemini streaming integration ──────────────────────────────────────────────

def _stream_gemini(
    message: str,
    history: list[dict],
    session_id: int,
    stream_id: str,
    stop_event: threading.Event,
    system_prompt: str | None = None,
):
    """
    Generator that streams tokens from Gemini and yields SSE frames.

    Yields:
        bytes — SSE frames with types:
            stream_start   — stream has begun
            token          — one or more tokens from the model
            stream_end     — stream completed successfully
            error          — an error occurred
    """
    try:
        import google.generativeai as genai
        import os

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            yield _sse_bytes("error", {"message": "GEMINI_API_KEY not configured"})
            return

        genai.configure(api_key=api_key)

        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config={
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
            },
            system_instruction=system_prompt or (
                "You are Calliope, an AI assistant for the Calliope IDE. "
                "Help users with Soroban smart contract development, Stellar blockchain, "
                "and general coding tasks. Be concise and helpful."
            ),
        )

        # Build chat history for Gemini
        gemini_history = []
        for msg in history:
            role = "user" if msg.get("role") == "user" else "model"
            gemini_history.append({
                "role": role,
                "parts": [msg.get("content", "")],
            })

        chat = model.start_chat(history=gemini_history)

        yield _sse_bytes("stream_start", {"stream_id": stream_id})

        full_response = []

        # Stream tokens from Gemini
        response = chat.send_message(message, stream=True)

        for chunk in response:
            if stop_event.is_set():
                yield _sse_bytes("stream_end", {
                    "stream_id": stream_id,
                    "stopped": True,
                    "full_text": "".join(full_response),
                })
                return

            if chunk.text:
                full_response.append(chunk.text)
                yield _sse_bytes("token", {"text": chunk.text, "stream_id": stream_id})

        complete_text = "".join(full_response)

        # Persist assistant response to DB
        if add_chat_message and session_id:
            try:
                add_chat_message(
                    session_id=session_id,
                    role="assistant",
                    content=complete_text,
                    message_type="ai_response",
                )
            except Exception as e:
                logger.warning("Failed to persist AI response: %s", e)

        yield _sse_bytes("stream_end", {
            "stream_id": stream_id,
            "stopped": False,
            "full_text": complete_text,
        })

    except Exception as e:
        logger.exception("Gemini streaming error (stream_id=%s)", stream_id)
        yield _sse_bytes("error", {
            "stream_id": stream_id,
            "message": str(e),
        })
    finally:
        _deregister_stream(stream_id)


# ── Routes ────────────────────────────────────────────────────────────────────

@streaming_chat_bp.route("/stream", methods=["POST"])
@token_required
def stream_message(current_user):
    """
    Stream an AI response via Server-Sent Events.

    Request JSON:
        session_id   (int)         — active session ID
        message      (str)         — user's message
        history      (list[dict])  — previous messages [{role, content}]
        system_prompt (str|None)   — optional system prompt override

    Response:
        text/event-stream with SSE frames:
          stream_start  — {"stream_id": "..."}
          token         — {"text": "...", "stream_id": "..."}
          stream_end    — {"stream_id": "...", "stopped": bool, "full_text": "..."}
          error         — {"message": "..."}
    """
    try:
        data = request.get_json(silent=True, force=True)
        if not data:
            return Response(
                _sse("error", {"message": "No data provided"}),
                status=400,
                mimetype="text/event-stream",
            )

        session_id = data.get("session_id")
        message = (data.get("message") or "").strip()
        history = data.get("history", [])
        system_prompt = data.get("system_prompt")

        if not session_id:
            return Response(
                _sse("error", {"message": "session_id is required"}),
                status=400,
                mimetype="text/event-stream",
            )

        if not message:
            return Response(
                _sse("error", {"message": "message is required"}),
                status=400,
                mimetype="text/event-stream",
            )

        # Verify session belongs to current user
        if Session:
            session = Session.query.filter_by(
                id=session_id, user_id=current_user.id, is_active=True
            ).first()
            if not session:
                return Response(
                    _sse("error", {"message": "Session not found or access denied"}),
                    status=404,
                    mimetype="text/event-stream",
                )

        # Persist user message to DB
        if add_chat_message:
            try:
                add_chat_message(
                    session_id=session_id,
                    role="user",
                    content=message,
                    message_type="user_message",
                )
            except Exception as e:
                logger.warning("Failed to persist user message: %s", e)

        stream_id = str(uuid.uuid4())
        stop_event = _register_stream(stream_id)

        def generate():
            yield from _stream_gemini(
                message=message,
                history=history,
                session_id=session_id,
                stream_id=stream_id,
                stop_event=stop_event,
                system_prompt=system_prompt,
            )

        response = Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
        )
        response.headers["Cache-Control"] = "no-cache, no-transform"
        response.headers["Connection"] = "keep-alive"
        response.headers["X-Accel-Buffering"] = "no"
        response.headers["Transfer-Encoding"] = "chunked"
        return response

    except Exception as e:
        logger.exception("Stream message error")
        capture_exception(e, {
            "route": "streaming_chat.stream_message",
            "user_id": current_user.id,
        })
        return Response(
            _sse("error", {"message": "An error occurred while starting the stream"}),
            status=500,
            mimetype="text/event-stream",
        )


@streaming_chat_bp.route("/stream/stop", methods=["POST"])
@token_required
def stop_stream(current_user):
    """
    Stop an in-progress AI stream.

    Request JSON:
        stream_id  (str) — ID returned in stream_start event

    Response JSON:
        success  (bool)
        stopped  (bool) — True if stream was found and stopped
    """
    try:
        data = request.get_json()
        stream_id = (data or {}).get("stream_id", "").strip()

        if not stream_id:
            return {"success": False, "error": "stream_id is required"}, 400

        with _streams_lock:
            stop_event = _active_streams.get(stream_id)

        if stop_event:
            stop_event.set()
            return {"success": True, "stopped": True}, 200

        return {"success": True, "stopped": False}, 200

    except Exception as e:
        logger.exception("Stop stream error")
        return {"success": False, "error": str(e)}, 500


@streaming_chat_bp.route("/stream/active", methods=["GET"])
@token_required
def list_active_streams(current_user):
    """
    List active stream IDs (debug/admin endpoint).
    """
    with _streams_lock:
        stream_ids = list(_active_streams.keys())
    return {"success": True, "active_streams": stream_ids, "count": len(stream_ids)}, 200
