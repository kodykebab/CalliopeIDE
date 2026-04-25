"""
Soroban prompt action routes for Calliope IDE.
Addresses issue #54.

Endpoints:
  GET  /api/prompts/soroban         — list all available prompt templates
  GET  /api/prompts/soroban/<id>    — get a single template's metadata
  POST /api/prompts/soroban/execute — build + execute a prompt via Gemini
  POST /api/prompts/soroban/build   — build prompt text only (no AI call)
"""

import os
import logging
from flask import Blueprint, request, jsonify
from server.utils.auth_utils import token_required
from server.utils.monitoring import capture_exception
from server.utils.soroban_prompts import (
    list_prompt_templates,
    get_prompt_template,
    build_soroban_prompt,
    PROMPT_TEMPLATES,
)

try:
    from server.models import Session, ChatHistory
    from server.utils.db_utils import add_chat_message
except Exception:
    Session = None  # type: ignore
    ChatHistory = None  # type: ignore
    add_chat_message = None  # type: ignore

logger = logging.getLogger(__name__)

soroban_prompts_bp = Blueprint(
    "soroban_prompts", __name__, url_prefix="/api/prompts/soroban"
)

_MAX_CODE_LEN = 50_000   # characters
_MAX_DESC_LEN = 2_000


# ── Routes ────────────────────────────────────────────────────────────────────

@soroban_prompts_bp.route("/", methods=["GET"])
@soroban_prompts_bp.route("", methods=["GET"])
def list_prompts():
    """
    List all available Soroban prompt templates.

    Response JSON:
        success    (bool)
        prompts    (list[dict]) — id, name, description, category, requires_code, placeholder
        total      (int)
    """
    try:
        prompts = list_prompt_templates()
        return jsonify({"success": True, "prompts": prompts, "total": len(prompts)}), 200
    except Exception as e:
        logger.exception("List prompts error")
        return jsonify({"success": False, "error": "Failed to list prompts"}), 500


@soroban_prompts_bp.route("/<prompt_id>", methods=["GET"])
def get_prompt(prompt_id: str):
    """
    Get metadata for a single prompt template.

    Response JSON:
        success  (bool)
        prompt   (dict)
    """
    try:
        prompt = get_prompt_template(prompt_id)
        if not prompt:
            return jsonify({
                "success": False,
                "error": f"Prompt '{prompt_id}' not found",
                "available": [p["id"] for p in list_prompt_templates()],
            }), 404
        return jsonify({"success": True, "prompt": prompt}), 200
    except Exception as e:
        logger.exception("Get prompt error")
        return jsonify({"success": False, "error": "Failed to get prompt"}), 500


@soroban_prompts_bp.route("/build", methods=["POST"])
@token_required
def build_prompt_text(current_user):
    """
    Build the full prompt text without executing it.
    Useful for the frontend to preview the prompt before sending.

    Request JSON:
        prompt_id        (str)  — one of: generate_contract, explain_contract, generate_tests, security_review
        description      (str)  — user's task description
        context_code     (str)  — optional: contract source code

    Response JSON:
        success      (bool)
        prompt_id    (str)
        prompt_text  (str)  — the full prompt string
        char_count   (int)
    """
    try:
        data = request.get_json(silent=True, force=True)
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        prompt_id = (data.get("prompt_id") or "").strip()
        description = (data.get("description") or "").strip()[:_MAX_DESC_LEN]
        context_code = (data.get("context_code") or "").strip()[:_MAX_CODE_LEN]

        if not prompt_id:
            return jsonify({"success": False, "error": "prompt_id is required"}), 400

        if prompt_id not in PROMPT_TEMPLATES:
            return jsonify({
                "success": False,
                "error": f"Unknown prompt '{prompt_id}'",
                "available": list(PROMPT_TEMPLATES.keys()),
            }), 404

        template = PROMPT_TEMPLATES[prompt_id]
        if template.requires_code and not context_code and not description:
            return jsonify({
                "success": False,
                "error": f"Prompt '{prompt_id}' requires either contract code or a description",
            }), 400

        prompt_text = build_soroban_prompt(prompt_id, description, context_code)

        return jsonify({
            "success": True,
            "prompt_id": prompt_id,
            "prompt_text": prompt_text,
            "char_count": len(prompt_text),
        }), 200

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.exception("Build prompt error")
        capture_exception(e, {"route": "soroban_prompts.build_prompt_text", "user_id": current_user.id})
        return jsonify({"success": False, "error": "Failed to build prompt"}), 500


@soroban_prompts_bp.route("/execute", methods=["POST"])
@token_required
def execute_prompt(current_user):
    """
    Build and execute a Soroban prompt via Gemini, returning the AI response.

    Request JSON:
        session_id       (int)  — active session ID (for chat history)
        prompt_id        (str)  — one of: generate_contract, explain_contract, generate_tests, security_review
        description      (str)  — user's task description
        context_code     (str)  — optional: contract source code

    Response JSON:
        success      (bool)
        prompt_id    (str)
        result       (str)   — AI-generated response
        char_count   (int)
    """
    try:
        data = request.get_json(silent=True, force=True)
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        session_id = data.get("session_id")
        prompt_id = (data.get("prompt_id") or "").strip()
        description = (data.get("description") or "").strip()[:_MAX_DESC_LEN]
        context_code = (data.get("context_code") or "").strip()[:_MAX_CODE_LEN]

        if not session_id:
            return jsonify({"success": False, "error": "session_id is required"}), 400
        if not prompt_id:
            return jsonify({"success": False, "error": "prompt_id is required"}), 400

        if prompt_id not in PROMPT_TEMPLATES:
            return jsonify({
                "success": False,
                "error": f"Unknown prompt '{prompt_id}'",
                "available": list(PROMPT_TEMPLATES.keys()),
            }), 404

        template = PROMPT_TEMPLATES[prompt_id]
        if template.requires_code and not context_code and not description:
            return jsonify({
                "success": False,
                "error": f"Prompt '{prompt_id}' requires either contract code or a description",
            }), 400

        # Verify session
        if Session:
            session = Session.query.filter_by(
                id=session_id, user_id=current_user.id, is_active=True
            ).first()
            if not session:
                return jsonify({"success": False, "error": "Session not found or access denied"}), 404

        # Build prompt
        prompt_text = build_soroban_prompt(prompt_id, description, context_code)

        # Call Gemini
        try:
            import google.generativeai as genai
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                return jsonify({"success": False, "error": "GEMINI_API_KEY not configured"}), 500

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name="gemini-2.0-flash",
                generation_config={
                    "temperature": 0.2,
                    "top_p": 0.95,
                    "max_output_tokens": 8192,
                },
            )
            response = model.generate_content(prompt_text)
            result = response.text
        except ImportError:
            return jsonify({"success": False, "error": "Gemini SDK not installed"}), 500

        # Persist to chat history
        if add_chat_message and session_id:
            try:
                add_chat_message(
                    session_id=session_id,
                    role="user",
                    content=f"[{template.name}] {description or '(no description)'}",
                    message_type="soroban_prompt",
                )
                add_chat_message(
                    session_id=session_id,
                    role="assistant",
                    content=result,
                    message_type="soroban_prompt_response",
                )
            except Exception as e:
                logger.warning("Failed to persist prompt result: %s", e)

        return jsonify({
            "success": True,
            "prompt_id": prompt_id,
            "result": result,
            "char_count": len(result),
        }), 200

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.exception("Execute prompt error")
        capture_exception(e, {"route": "soroban_prompts.execute_prompt", "user_id": current_user.id})
        return jsonify({"success": False, "error": "An error occurred while executing the prompt"}), 500
