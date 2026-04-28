"""
Docker-based code execution backend for Calliope IDE.

Replaces the bare subprocess.Popen path in secure_execution.py with an
ephemeral Docker container that enforces:

  • Filesystem isolation  — no host FS is mounted
  • Network isolation     — --network none
  • CPU cap               — --cpus 0.5
  • Memory cap            — --memory 64m  (no swap)
  • Read-only rootfs      — --read-only with a /sandbox tmpfs
  • Non-root user         — UID 65534 inside the image
  • Automatic cleanup     — container is removed after each run

Public API
----------
  run_code_in_sandbox(code, timeout) -> dict
      Drop-in replacement for the old subprocess block.  Returns the same
      shape as secure_execution.secure_execute():
          {status, output, error, execution_time}
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

# ── Configuration (overridable via environment) ────────────────────────────────

SANDBOX_IMAGE = os.environ.get("SANDBOX_IMAGE", "calliope-sandbox:latest")

# Resource limits applied to every container
_CPU_QUOTA = os.environ.get("SANDBOX_CPU", "0.5")       # fractional cores
_MEMORY    = os.environ.get("SANDBOX_MEMORY", "64m")     # Docker memory string
_MAX_OUTPUT = int(os.environ.get("SANDBOX_MAX_OUTPUT", "10000"))   # chars

# How long we give Docker itself to respond before we consider it broken
_DOCKER_API_TIMEOUT = 10  # seconds

# ── Lazy Docker client ─────────────────────────────────────────────────────────

_docker_client = None
_docker_available = False


def _get_docker_client():
    """Return a cached Docker SDK client, or None if Docker is unavailable."""
    global _docker_client, _docker_available

    if _docker_client is not None:
        return _docker_client

    try:
        import docker  # type: ignore
        client = docker.from_env(timeout=_DOCKER_API_TIMEOUT)
        client.ping()   # verifies the daemon is reachable
        _docker_client = client
        _docker_available = True
        logger.info("Docker daemon connected — sandbox executor ready")
    except Exception as exc:
        logger.warning(
            "Docker unavailable (%s). Container sandbox disabled; "
            "falling back to subprocess sandbox.",
            exc,
        )
        _docker_available = False

    return _docker_client


def is_docker_available() -> bool:
    """Return True if the Docker daemon is reachable."""
    _get_docker_client()
    return _docker_available


# ── Image management ───────────────────────────────────────────────────────────

def ensure_sandbox_image(force_rebuild: bool = False) -> bool:
    """
    Build the sandbox image if it does not already exist.

    Called once at server startup. Returns True on success.
    """
    client = _get_docker_client()
    if client is None:
        return False

    try:
        import docker  # type: ignore

        if not force_rebuild:
            try:
                client.images.get(SANDBOX_IMAGE)
                logger.info("Sandbox image '%s' already exists.", SANDBOX_IMAGE)
                return True
            except docker.errors.ImageNotFound:
                pass

        logger.info("Building sandbox image '%s' …", SANDBOX_IMAGE)
        # Dockerfile lives at docker/sandbox.Dockerfile relative to project root
        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        _, build_logs = client.images.build(
            path=project_root,
            dockerfile="docker/sandbox.Dockerfile",
            tag=SANDBOX_IMAGE,
            rm=True,
            forcerm=True,
        )
        for chunk in build_logs:
            if "stream" in chunk:
                logger.debug("docker build: %s", chunk["stream"].rstrip())

        logger.info("Sandbox image '%s' built successfully.", SANDBOX_IMAGE)
        return True

    except Exception as exc:
        logger.error("Failed to build sandbox image: %s", exc)
        return False


# ── Core execution ─────────────────────────────────────────────────────────────

def run_code_in_sandbox(code: str, timeout: int = 5) -> dict[str, Any]:
    """
    Execute *code* inside an ephemeral Docker container.

    Security guarantees
    -------------------
    * --network none             — no outbound or inbound network
    * --read-only                — rootfs is read-only
    * --tmpfs /sandbox           — writable scratchpad in RAM only
    * --memory / --memory-swap   — hard memory ceiling
    * --cpus                     — CPU share limit
    * --pids-limit               — limits fork bombs
    * --cap-drop ALL             — all Linux capabilities stripped
    * --security-opt no-new-privileges
    * non-root UID 65534 inside container
    * auto-remove after execution

    Returns the same dict shape as secure_execution.secure_execute().
    """
    client = _get_docker_client()
    if client is None:
        return _error("Docker daemon not available", 0)

    start = time.time()
    container = None

    try:
        import docker  # type: ignore

        container = client.containers.run(
            image=SANDBOX_IMAGE,
            # Pipe code via stdin
            stdin_open=True,
            # Runtime isolation
            network_mode="none",
            read_only=True,
            tmpfs={"/sandbox": "size=32m,mode=1777"},
            # Resource limits
            cpu_quota=int(float(_CPU_QUOTA) * 100_000),  # microseconds per 100 ms
            cpu_period=100_000,
            mem_limit=_MEMORY,
            memswap_limit=_MEMORY,  # swap == mem → effectively no swap
            pids_limit=64,
            # Security
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            # Lifecycle
            detach=True,
            remove=False,   # we remove manually after reading logs
            stdout=True,
            stderr=True,
        )

        # Send code to the container's stdin and close the pipe
        sock = container.attach_socket(
            params={"stdin": 1, "stream": 1, "stdout": 0, "stderr": 0}
        )
        raw_sock = getattr(sock, "_sock", sock)
        raw_sock.sendall(code.encode())
        raw_sock.close()

        # Wait with a wall-clock timeout
        result = container.wait(timeout=timeout + 2)   # +2 for Docker overhead
        exit_code = result.get("StatusCode", -1)

        elapsed = time.time() - start

        # Retrieve logs
        stdout_raw = container.logs(stdout=True, stderr=False).decode(errors="replace")
        stderr_raw = container.logs(stdout=False, stderr=True).decode(errors="replace")

        # Enforce output size cap
        if len(stdout_raw) > _MAX_OUTPUT:
            stdout_raw = stdout_raw[:_MAX_OUTPUT] + "\n… (output truncated)"
        if len(stderr_raw) > _MAX_OUTPUT:
            stderr_raw = stderr_raw[:_MAX_OUTPUT] + "\n… (error truncated)"

        if exit_code == 0:
            return {
                "status": "success",
                "output": stdout_raw,
                "error": f"Warnings: {stderr_raw}" if stderr_raw else "",
                "execution_time": elapsed,
            }
        elif "MemoryError" in stderr_raw or "Killed" in stderr_raw:
            return {
                "status": "memory_error",
                "output": stdout_raw,
                "error": "Memory limit exceeded",
                "execution_time": elapsed,
            }
        else:
            return {
                "status": "error",
                "output": stdout_raw,
                "error": stderr_raw or "Non-zero exit code",
                "execution_time": elapsed,
            }

    except Exception as exc:
        elapsed = time.time() - start
        exc_str = str(exc)

        # Distinguish timeout from other errors
        if "timed out" in exc_str.lower() or "timeout" in exc_str.lower():
            logger.warning("Sandbox timeout after %.1fs", elapsed)
            return {
                "status": "timeout",
                "output": "",
                "error": f"Execution time limit exceeded ({timeout}s)",
                "execution_time": timeout,
            }

        logger.error("Sandbox execution error: %s", exc, exc_info=True)
        return _error(f"Sandbox execution failed: {exc_str}", elapsed)

    finally:
        # Always remove the container — even if we hit an exception
        if container is not None:
            try:
                container.remove(force=True)
            except Exception as cleanup_exc:
                logger.warning("Failed to remove container: %s", cleanup_exc)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _error(msg: str, elapsed: float) -> dict[str, Any]:
    return {
        "status": "error",
        "output": "",
        "error": msg,
        "execution_time": elapsed,
    }