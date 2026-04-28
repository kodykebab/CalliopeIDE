"""
Container lifecycle manager for Calliope IDE agent instances.

Each user session gets its own Docker container running agent.py.
This module handles:

  • Creating per-session containers from the backend image
  • Tracking container IDs against session identifiers
  • Destroying containers on session end or server shutdown
  • Periodic cleanup of orphaned / exited containers

Architecture
------------
  start.py  ──► container_manager.create_agent_container(port, instance_dir)
                    → returns container_id
  start.py  ──► container_manager.destroy_agent_container(container_id)

All container objects are kept in a module-level registry so the cleanup
thread can destroy any that were not explicitly torn down (crash recovery).

Environment variables
---------------------
  AGENT_IMAGE          Docker image for the agent (default: calliope-backend:latest)
  AGENT_MEMORY         Memory limit per agent container (default: 256m)
  AGENT_CPU            CPU share per agent container (default: 1.0)
  AGENT_NETWORK        Docker network for agent containers (default: calliope-net)
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────

AGENT_IMAGE   = os.environ.get("AGENT_IMAGE",   "calliope-backend:latest")
AGENT_MEMORY  = os.environ.get("AGENT_MEMORY",  "256m")
AGENT_CPU     = os.environ.get("AGENT_CPU",     "1.0")
AGENT_NETWORK = os.environ.get("AGENT_NETWORK", "calliope-net")

_DOCKER_TIMEOUT = 10  # seconds for Docker API calls
_CLEANUP_INTERVAL = 60  # seconds between orphan-sweep runs

# ── Registry ───────────────────────────────────────────────────────────────────
# Maps container_id → { 'container': docker container object,
#                        'session_id': str, 'created_at': float }

_registry: dict[str, dict] = {}
_registry_lock = threading.Lock()

# ── Docker client ──────────────────────────────────────────────────────────────

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        import docker  # type: ignore
        c = docker.from_env(timeout=_DOCKER_TIMEOUT)
        c.ping()
        _client = c
        logger.info("ContainerManager: Docker daemon connected.")
    except Exception as exc:
        logger.warning("ContainerManager: Docker unavailable — %s", exc)
    return _client


# ── Public API ─────────────────────────────────────────────────────────────────

def create_agent_container(
    port: int,
    instance_dir: str,
    session_id: Optional[str] = None,
    env_extras: Optional[dict] = None,
) -> Optional[str]:
    """
    Spin up an isolated agent container for a user session.

    The agent process inside the container is started by the image's default
    CMD/ENTRYPOINT (gunicorn / python start.py).  We override the command here
    to run agent.py directly on the requested port.

    Args:
        port:         Host port the agent should listen on.
        instance_dir: Absolute path to the per-session workspace on the host.
                      Mounted read-write so the agent can read/write project files.
        session_id:   Optional session identifier for tracking.
        env_extras:   Extra environment variables merged into the container env.

    Returns:
        Container ID string, or None if Docker is unavailable / creation failed.
    """
    client = _get_client()
    if client is None:
        return None

    # Forward required env vars into the agent container
    env = {
        "GEMINI_API_KEY":  os.environ.get("GEMINI_API_KEY", ""),
        "CORS_ORIGINS":    os.environ.get("CORS_ORIGINS", "http://localhost:3000"),
        "PYTHONUNBUFFERED": "1",
    }
    if env_extras:
        env.update(env_extras)

    try:
        container = client.containers.run(
            image=AGENT_IMAGE,
            command=["python3", "agent.py", str(port)],
            # Mount only the session workspace — not the whole host
            volumes={
                os.path.abspath(instance_dir): {
                    "bind": "/workspace",
                    "mode": "rw",
                }
            },
            working_dir="/workspace",
            environment=env,
            # Networking — agent needs to talk back to the frontend
            network=AGENT_NETWORK,
            ports={f"{port}/tcp": port},
            # Resource limits
            mem_limit=AGENT_MEMORY,
            memswap_limit=AGENT_MEMORY,
            cpu_quota=int(float(AGENT_CPU) * 100_000),
            cpu_period=100_000,
            pids_limit=128,
            # Security
            cap_drop=["ALL"],
            cap_add=["CHOWN", "SETUID", "SETGID"],  # minimal for process startup
            security_opt=["no-new-privileges:true"],
            # Lifecycle
            detach=True,
            remove=False,  # we manage removal explicitly
            stdout=True,
            stderr=True,
            labels={
                "calliope.role":       "agent",
                "calliope.session_id": session_id or "",
                "calliope.port":       str(port),
            },
        )

        cid = container.id
        with _registry_lock:
            _registry[cid] = {
                "container":  container,
                "session_id": session_id,
                "created_at": time.time(),
            }

        logger.info(
            "Agent container %s started (session=%s, port=%d).",
            cid[:12], session_id, port,
        )
        return cid

    except Exception as exc:
        logger.error("Failed to create agent container: %s", exc, exc_info=True)
        return None


def destroy_agent_container(container_id: str) -> bool:
    """
    Stop and remove an agent container.

    Safe to call even if the container has already exited.

    Returns:
        True if successfully destroyed, False otherwise.
    """
    client = _get_client()
    if client is None:
        return False

    try:
        import docker  # type: ignore

        try:
            container = client.containers.get(container_id)
        except docker.errors.NotFound:
            logger.debug("Container %s already gone.", container_id[:12])
            _deregister(container_id)
            return True

        container.stop(timeout=5)
        container.remove(force=True)
        _deregister(container_id)
        logger.info("Agent container %s destroyed.", container_id[:12])
        return True

    except Exception as exc:
        logger.warning("Could not destroy container %s: %s", container_id[:12], exc)
        return False


def destroy_all_agent_containers() -> int:
    """
    Destroy every container currently tracked in the registry.

    Called at server shutdown to ensure no orphans are left behind.
    Returns the number of containers destroyed.
    """
    with _registry_lock:
        ids = list(_registry.keys())

    count = 0
    for cid in ids:
        if destroy_agent_container(cid):
            count += 1
    logger.info("Destroyed %d agent container(s) at shutdown.", count)
    return count


def get_container_status(container_id: str) -> Optional[str]:
    """Return the Docker status string for a container, or None if not found."""
    client = _get_client()
    if client is None:
        return None
    try:
        import docker  # type: ignore
        c = client.containers.get(container_id)
        return c.status   # 'running', 'exited', 'created', …
    except Exception:
        return None


# ── Orphan cleanup ─────────────────────────────────────────────────────────────

def _deregister(container_id: str) -> None:
    with _registry_lock:
        _registry.pop(container_id, None)


def _cleanup_orphans() -> None:
    """
    Background thread: remove any tracked containers that have exited
    without being explicitly destroyed (e.g. after a crash).
    """
    while True:
        time.sleep(_CLEANUP_INTERVAL)
        with _registry_lock:
            ids = list(_registry.keys())

        for cid in ids:
            status = get_container_status(cid)
            if status is None or status in ("exited", "dead", "removing"):
                logger.info("Cleaning up orphaned container %s (status=%s).", cid[:12], status)
                destroy_agent_container(cid)


# Start the background cleanup thread as a daemon so it doesn't block shutdown
_cleanup_thread = threading.Thread(target=_cleanup_orphans, daemon=True, name="container-cleanup")
_cleanup_thread.start()