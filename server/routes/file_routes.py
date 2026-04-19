"""
File persistence routes for Calliope IDE autosave system.
Addresses issue #57.

Endpoints:
  POST   /api/files/save           — save (create/overwrite) a file
  GET    /api/files/load           — load file contents
  GET    /api/files/list           — list all files in session workspace
  DELETE /api/files/delete         — delete a file
  POST   /api/files/mkdir          — create a directory
"""

import os
import re
import logging
from pathlib import Path
from flask import Blueprint, request, jsonify
from server.utils.auth_utils import token_required
from server.utils.monitoring import capture_exception

try:
    from server.models import Session
except Exception:
    Session = None  # type: ignore

files_bp = Blueprint("files", __name__, url_prefix="/api/files")
logger = logging.getLogger(__name__)

# Max file size: 5 MB
_MAX_FILE_SIZE = 5 * 1024 * 1024
# Allowed extensions (empty = allow all text files)
_BLOCKED_EXTENSIONS = {".exe", ".bin", ".so", ".dll", ".dylib"}


# ── Path safety ───────────────────────────────────────────────────────────────

def _safe_path(relative_path: str, instance_dir: str) -> str | None:
    """
    Resolve relative_path inside instance_dir and validate no path traversal.
    Returns absolute path on success, None on traversal attempt.
    """
    base = os.path.abspath(instance_dir)
    target = os.path.abspath(os.path.join(base, relative_path))
    if not target.startswith(base + os.sep) and target != base:
        return None
    return target


def _validate_filename(path: str) -> bool:
    """Block null bytes, absolute paths, and suspicious patterns."""
    if "\x00" in path:
        return False
    if os.path.isabs(path):
        return False
    # Block hidden files at root level (e.g. .env, .git)
    parts = Path(path).parts
    if parts and parts[0].startswith("."):
        return False
    return True


# ── Routes ────────────────────────────────────────────────────────────────────

@files_bp.route("/save", methods=["POST"])
@token_required
def save_file(current_user):
    """
    Save (create or overwrite) a file in the session workspace.

    Request JSON:
        session_id  (int)  — active session ID
        path        (str)  — relative path inside the workspace
        content     (str)  — file content (text)

    Response JSON:
        success     (bool)
        path        (str)  — relative path
        size        (int)  — bytes written
        created     (bool) — True if new file, False if overwritten
    """
    try:
        data = request.get_json(silent=True, force=True)
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        session_id = data.get("session_id")
        rel_path = (data.get("path") or "").strip()
        content = data.get("content", "")

        if not session_id:
            return jsonify({"success": False, "error": "session_id is required"}), 400
        if not rel_path:
            return jsonify({"success": False, "error": "path is required"}), 400
        if not isinstance(content, str):
            return jsonify({"success": False, "error": "content must be a string"}), 400
        if len(content.encode("utf-8")) > _MAX_FILE_SIZE:
            return jsonify({"success": False, "error": f"File too large (max {_MAX_FILE_SIZE // 1024}KB)"}), 413

        # Validate filename
        if not _validate_filename(rel_path):
            return jsonify({"success": False, "error": "Invalid path"}), 400

        # Block dangerous extensions
        ext = Path(rel_path).suffix.lower()
        if ext in _BLOCKED_EXTENSIONS:
            return jsonify({"success": False, "error": f"File type '{ext}' not allowed"}), 400

        # Verify session
        session = _get_session(session_id, current_user.id)
        if not session:
            return jsonify({"success": False, "error": "Session not found or access denied"}), 404

        instance_dir = session.instance_dir
        if not instance_dir or not os.path.isdir(instance_dir):
            return jsonify({"success": False, "error": "Session workspace not found"}), 404

        abs_path = _safe_path(rel_path, instance_dir)
        if not abs_path:
            return jsonify({"success": False, "error": "Path traversal detected"}), 400

        # Create parent directories if needed
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        created = not os.path.exists(abs_path)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)

        size = os.path.getsize(abs_path)
        logger.info("User %s saved file %s (%d bytes)", current_user.username, rel_path, size)

        return jsonify({
            "success": True,
            "path": rel_path,
            "size": size,
            "created": created,
        }), 200

    except OSError as e:
        logger.exception("File save OS error")
        return jsonify({"success": False, "error": f"File system error: {e.strerror}"}), 500
    except Exception as e:
        logger.exception("Save file error")
        capture_exception(e, {"route": "files.save_file", "user_id": current_user.id})
        return jsonify({"success": False, "error": "An error occurred while saving the file"}), 500


@files_bp.route("/load", methods=["GET"])
@token_required
def load_file(current_user):
    """
    Load file contents from the session workspace.

    Query params:
        session_id  (int)  — active session ID
        path        (str)  — relative path inside the workspace

    Response JSON:
        success   (bool)
        path      (str)
        content   (str)
        size      (int)
    """
    try:
        session_id = request.args.get("session_id", type=int)
        rel_path = (request.args.get("path") or "").strip()

        if not session_id:
            return jsonify({"success": False, "error": "session_id is required"}), 400
        if not rel_path:
            return jsonify({"success": False, "error": "path is required"}), 400

        session = _get_session(session_id, current_user.id)
        if not session:
            return jsonify({"success": False, "error": "Session not found or access denied"}), 404

        instance_dir = session.instance_dir
        if not instance_dir or not os.path.isdir(instance_dir):
            return jsonify({"success": False, "error": "Session workspace not found"}), 404

        abs_path = _safe_path(rel_path, instance_dir)
        if not abs_path:
            return jsonify({"success": False, "error": "Path traversal detected"}), 400

        if not os.path.exists(abs_path):
            return jsonify({"success": False, "error": "File not found"}), 404

        if not os.path.isfile(abs_path):
            return jsonify({"success": False, "error": "Path is not a file"}), 400

        size = os.path.getsize(abs_path)
        if size > _MAX_FILE_SIZE:
            return jsonify({"success": False, "error": "File too large to load"}), 413

        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        return jsonify({
            "success": True,
            "path": rel_path,
            "content": content,
            "size": size,
        }), 200

    except OSError as e:
        return jsonify({"success": False, "error": f"File system error: {e.strerror}"}), 500
    except Exception as e:
        logger.exception("Load file error")
        capture_exception(e, {"route": "files.load_file", "user_id": current_user.id})
        return jsonify({"success": False, "error": "An error occurred while loading the file"}), 500


@files_bp.route("/list", methods=["GET"])
@token_required
def list_files(current_user):
    """
    List all files in the session workspace (recursive).

    Query params:
        session_id  (int)  — active session ID
        subdir      (str)  — optional subdirectory to list

    Response JSON:
        success  (bool)
        files    (list[dict]) — [{path, size, is_dir}]
        total    (int)
    """
    try:
        session_id = request.args.get("session_id", type=int)
        subdir = (request.args.get("subdir") or "").strip()

        if not session_id:
            return jsonify({"success": False, "error": "session_id is required"}), 400

        session = _get_session(session_id, current_user.id)
        if not session:
            return jsonify({"success": False, "error": "Session not found or access denied"}), 404

        instance_dir = session.instance_dir
        if not instance_dir or not os.path.isdir(instance_dir):
            return jsonify({"success": False, "error": "Session workspace not found"}), 404

        if subdir:
            root = _safe_path(subdir, instance_dir)
            if not root:
                return jsonify({"success": False, "error": "Path traversal detected"}), 400
        else:
            root = os.path.abspath(instance_dir)

        if not os.path.isdir(root):
            return jsonify({"success": False, "error": "Directory not found"}), 404

        files = []
        for item in sorted(Path(root).rglob("*")):
            # Skip hidden files and __pycache__
            parts = item.relative_to(root).parts
            if any(p.startswith(".") or p == "__pycache__" for p in parts):
                continue
            rel = str(item.relative_to(instance_dir))
            files.append({
                "path": rel,
                "size": item.stat().st_size if item.is_file() else 0,
                "is_dir": item.is_dir(),
            })

        return jsonify({
            "success": True,
            "files": files,
            "total": len(files),
        }), 200

    except Exception as e:
        logger.exception("List files error")
        capture_exception(e, {"route": "files.list_files", "user_id": current_user.id})
        return jsonify({"success": False, "error": "An error occurred while listing files"}), 500


@files_bp.route("/delete", methods=["DELETE"])
@token_required
def delete_file(current_user):
    """
    Delete a file from the session workspace.

    Request JSON:
        session_id  (int)  — active session ID
        path        (str)  — relative path inside the workspace

    Response JSON:
        success  (bool)
        path     (str)
    """
    try:
        data = request.get_json(silent=True, force=True)
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        session_id = data.get("session_id")
        rel_path = (data.get("path") or "").strip()

        if not session_id:
            return jsonify({"success": False, "error": "session_id is required"}), 400
        if not rel_path:
            return jsonify({"success": False, "error": "path is required"}), 400

        session = _get_session(session_id, current_user.id)
        if not session:
            return jsonify({"success": False, "error": "Session not found or access denied"}), 404

        instance_dir = session.instance_dir
        if not instance_dir or not os.path.isdir(instance_dir):
            return jsonify({"success": False, "error": "Session workspace not found"}), 404

        abs_path = _safe_path(rel_path, instance_dir)
        if not abs_path:
            return jsonify({"success": False, "error": "Path traversal detected"}), 400

        if not os.path.exists(abs_path):
            return jsonify({"success": False, "error": "File not found"}), 404

        if not os.path.isfile(abs_path):
            return jsonify({"success": False, "error": "Path is not a file — use rmdir for directories"}), 400

        os.remove(abs_path)
        logger.info("User %s deleted file %s", current_user.username, rel_path)

        return jsonify({"success": True, "path": rel_path}), 200

    except OSError as e:
        return jsonify({"success": False, "error": f"File system error: {e.strerror}"}), 500
    except Exception as e:
        logger.exception("Delete file error")
        capture_exception(e, {"route": "files.delete_file", "user_id": current_user.id})
        return jsonify({"success": False, "error": "An error occurred while deleting the file"}), 500


@files_bp.route("/mkdir", methods=["POST"])
@token_required
def make_directory(current_user):
    """
    Create a directory in the session workspace.

    Request JSON:
        session_id  (int)  — active session ID
        path        (str)  — relative path for the new directory

    Response JSON:
        success  (bool)
        path     (str)
        created  (bool)
    """
    try:
        data = request.get_json(silent=True, force=True)
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        session_id = data.get("session_id")
        rel_path = (data.get("path") or "").strip()

        if not session_id:
            return jsonify({"success": False, "error": "session_id is required"}), 400
        if not rel_path:
            return jsonify({"success": False, "error": "path is required"}), 400

        if not _validate_filename(rel_path):
            return jsonify({"success": False, "error": "Invalid path"}), 400

        session = _get_session(session_id, current_user.id)
        if not session:
            return jsonify({"success": False, "error": "Session not found or access denied"}), 404

        instance_dir = session.instance_dir
        if not instance_dir or not os.path.isdir(instance_dir):
            return jsonify({"success": False, "error": "Session workspace not found"}), 404

        abs_path = _safe_path(rel_path, instance_dir)
        if not abs_path:
            return jsonify({"success": False, "error": "Path traversal detected"}), 400

        created = not os.path.exists(abs_path)
        os.makedirs(abs_path, exist_ok=True)

        return jsonify({"success": True, "path": rel_path, "created": created}), 200

    except OSError as e:
        return jsonify({"success": False, "error": f"File system error: {e.strerror}"}), 500
    except Exception as e:
        logger.exception("mkdir error")
        capture_exception(e, {"route": "files.make_directory", "user_id": current_user.id})
        return jsonify({"success": False, "error": "An error occurred while creating the directory"}), 500


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_session(session_id: int, user_id: int):
    if Session is None:
        return None
    return Session.query.filter_by(
        id=session_id, user_id=user_id, is_active=True
    ).first()
