"""
Soroban smart contract routes — compile Rust contracts to WASM.
Addresses issue #49.

Endpoints:
  POST /api/soroban/compile   — compile a Rust project to WASM
  GET  /api/soroban/artifacts/<session_id>  — list WASM artifacts
"""

import os
import subprocess
import shutil
import glob
import logging
from pathlib import Path
from flask import Blueprint, request, jsonify
from server.utils.monitoring import capture_exception

soroban_bp = Blueprint("soroban", __name__, url_prefix="/api/soroban")

try:
    from server.models import Session
except Exception:
    Session = None  # type: ignore

try:
    from server.models import Session
except Exception:
    Session = None  # type: ignore
logger = logging.getLogger(__name__)

# Maximum compile time in seconds
COMPILE_TIMEOUT = int(os.getenv("SOROBAN_COMPILE_TIMEOUT", "120"))

# Allowed project path prefix to prevent path traversal
_SERVER_DIR = os.path.abspath(os.path.dirname(__file__))
_WORKSPACE_ROOT = os.path.abspath(os.path.join(_SERVER_DIR, ".."))


def _safe_project_path(raw_path: str, instance_dir: str) -> str | None:
    """
    Resolve and validate that project_path is inside the session instance_dir.
    Returns absolute path or None if the path is unsafe.
    """
    base = os.path.abspath(instance_dir)
    target = os.path.abspath(os.path.join(base, raw_path))
    if not target.startswith(base + os.sep) and target != base:
        return None
    return target


def _check_rust_toolchain() -> tuple[bool, str]:
    """Check that cargo and the wasm32 target are available."""
    if not shutil.which("cargo"):
        return False, "cargo not found. Please install Rust toolchain."
    result = subprocess.run(
        ["rustup", "target", "list", "--installed"],
        capture_output=True, text=True, timeout=10
    )
    if "wasm32-unknown-unknown" not in result.stdout:
        return False, (
            "wasm32-unknown-unknown target not installed. "
            "Run: rustup target add wasm32-unknown-unknown"
        )
    return True, "ok"


@soroban_bp.route("/compile", methods=["POST"])
@__import__('server.utils.auth_utils', fromlist=['token_required']).token_required
def compile_contract(current_user):
    """
    Compile a Soroban Rust project to WASM.

    Request JSON:
        session_id    (int)  — active session ID that owns the workspace
        project_path  (str)  — relative path inside the instance directory
                               where Cargo.toml lives (default: ".")
        release       (bool) — build with --release flag (default: true)

    Response JSON:
        success       (bool)
        wasm_artifacts (list[str]) — paths to generated .wasm files
        stdout        (str)
        stderr        (str)
        exit_code     (int)
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        session_id = data.get("session_id")
        if not session_id:
            return jsonify({"success": False, "error": "session_id is required"}), 400

        # Verify session belongs to current user
        session = Session.query.filter_by(
            id=session_id, user_id=current_user.id, is_active=True
        ).first()
        if not session:
            return jsonify({"success": False, "error": "Session not found or access denied"}), 404

        instance_dir = session.instance_dir
        if not instance_dir or not os.path.isdir(instance_dir):
            return jsonify({"success": False, "error": "Session workspace not found"}), 404

        # Resolve and validate project path
        raw_project_path = data.get("project_path", ".")
        project_path = _safe_project_path(raw_project_path, instance_dir)
        if not project_path:
            return jsonify({"success": False, "error": "Invalid project_path — path traversal not allowed"}), 400

        if not os.path.isdir(project_path):
            return jsonify({"success": False, "error": f"project_path does not exist: {raw_project_path}"}), 400

        cargo_toml = os.path.join(project_path, "Cargo.toml")
        if not os.path.isfile(cargo_toml):
            return jsonify({"success": False, "error": "No Cargo.toml found in project_path"}), 400

        # Check toolchain
        toolchain_ok, toolchain_msg = _check_rust_toolchain()
        if not toolchain_ok:
            return jsonify({"success": False, "error": toolchain_msg}), 500

        # Build the compile command
        release = data.get("release", True)
        cmd = ["cargo", "build", "--target", "wasm32-unknown-unknown"]
        if release:
            cmd.append("--release")

        logger.info(
            f"User {current_user.username} compiling Soroban contract "
            f"in {project_path} (release={release})"
        )

        # Run compilation
        result = subprocess.run(
            cmd,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=COMPILE_TIMEOUT,
        )

        # Collect WASM artifacts
        wasm_pattern = os.path.join(
            project_path, "target", "wasm32-unknown-unknown",
            "release" if release else "debug",
            "*.wasm"
        )
        wasm_files = [
            os.path.relpath(f, instance_dir)
            for f in glob.glob(wasm_pattern)
        ]

        success = result.returncode == 0

        logger.info(
            f"Compile finished for user {current_user.username}: "
            f"exit={result.returncode}, wasm_count={len(wasm_files)}"
        )

        return jsonify({
            "success": success,
            "wasm_artifacts": wasm_files,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "project_path": raw_project_path,
            "release": release,
        }), 200 if success else 422

    except subprocess.TimeoutExpired:
        logger.warning(f"Compile timed out for user {current_user.username}")
        return jsonify({
            "success": False,
            "error": f"Compilation timed out after {COMPILE_TIMEOUT}s",
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
        }), 408

    except Exception as e:
        logger.exception("Compile contract error")
        capture_exception(e, {
            "route": "soroban.compile_contract",
            "user_id": current_user.id,
        })
        return jsonify({"success": False, "error": "An error occurred during compilation"}), 500


@soroban_bp.route("/artifacts/<int:session_id>", methods=["GET"])
@__import__('server.utils.auth_utils', fromlist=['token_required']).token_required
def list_artifacts(current_user, session_id):
    """
    List all .wasm artifacts in a session workspace.

    Response JSON:
        success       (bool)
        artifacts     (list[dict])  — [{path, size_bytes, name}]
    """
    try:
        session = Session.query.filter_by(
            id=session_id, user_id=current_user.id, is_active=True
        ).first()
        if not session:
            return jsonify({"success": False, "error": "Session not found or access denied"}), 404

        instance_dir = session.instance_dir
        if not instance_dir or not os.path.isdir(instance_dir):
            return jsonify({"success": False, "artifacts": []}), 200

        wasm_files = []
        for wasm_path in Path(instance_dir).rglob("*.wasm"):
            wasm_files.append({
                "path": str(wasm_path.relative_to(instance_dir)),
                "name": wasm_path.name,
                "size_bytes": wasm_path.stat().st_size,
            })

        return jsonify({
            "success": True,
            "artifacts": wasm_files,
            "total": len(wasm_files),
        }), 200

    except Exception as e:
        logger.exception("List artifacts error")
        capture_exception(e, {
            "route": "soroban.list_artifacts",
            "user_id": current_user.id,
            "session_id": session_id,
        })
        return jsonify({"success": False, "error": "An error occurred while listing artifacts"}), 500
