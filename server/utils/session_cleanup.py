"""
Session lifecycle cleanup utilities.

Addresses issue #42: session deactivation now terminates the associated
agent process and removes the instance directory.
"""

import os
import shutil
import signal
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def terminate_agent_process(pid: int, instance_dir: str) -> bool:
    """
    Terminate an agent process by PID.

    Tries SIGTERM first, then SIGKILL after 3 seconds if the process
    does not exit gracefully.

    Args:
        pid: Process ID to terminate
        instance_dir: Instance directory name (used for logging only)

    Returns:
        True if process was terminated, False if it was already gone
    """
    if not pid:
        return False

    try:
        # Check if process exists
        os.kill(pid, 0)
    except ProcessLookupError:
        logger.debug(f"Agent process {pid} (dir={instance_dir}) already exited")
        return False
    except PermissionError:
        # Process exists but we can't signal it — log and move on
        logger.warning(f"No permission to terminate agent process {pid}")
        return False

    try:
        logger.info(f"Sending SIGTERM to agent process {pid} (dir={instance_dir})")
        os.kill(pid, signal.SIGTERM)

        # Give the process up to 3 seconds to exit gracefully
        import time
        for _ in range(6):
            time.sleep(0.5)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                logger.info(f"Agent process {pid} exited after SIGTERM")
                return True

        # Process still alive — force kill
        logger.warning(f"Agent process {pid} did not exit after SIGTERM, sending SIGKILL")
        os.kill(pid, signal.SIGKILL)
        return True

    except ProcessLookupError:
        logger.debug(f"Agent process {pid} exited between SIGTERM and SIGKILL")
        return True
    except Exception as e:
        logger.error(f"Failed to terminate agent process {pid}: {e}")
        return False


def cleanup_instance_directory(instance_dir: str) -> bool:
    """
    Remove an agent instance directory from the filesystem.

    Args:
        instance_dir: Relative or absolute path to the instance directory

    Returns:
        True if removed, False if it didn't exist or removal failed
    """
    if not instance_dir:
        return False

    path = os.path.abspath(instance_dir)

    if not os.path.exists(path):
        logger.debug(f"Instance directory already removed: {path}")
        return False

    # Safety check: only remove directories matching the expected pattern
    dirname = os.path.basename(path)
    if not (dirname.startswith("instance") and "_user" in dirname):
        logger.warning(
            f"Refusing to remove directory with unexpected name: {dirname}. "
            "Expected pattern: instance<N>_user<ID>"
        )
        return False

    try:
        shutil.rmtree(path, ignore_errors=False)
        logger.info(f"Removed instance directory: {path}")
        return True
    except Exception as e:
        logger.error(f"Failed to remove instance directory {path}: {e}")
        return False


def cleanup_session_resources(
    session_id: int,
    pid: Optional[int],
    instance_dir: Optional[str],
) -> dict:
    """
    Full lifecycle cleanup for a deactivated session.

    Terminates the agent process and removes the instance directory.
    Both steps are attempted independently so a failure in one does not
    prevent the other.

    Args:
        session_id: Database session ID (used for logging)
        pid: Agent process PID (may be None if not tracked)
        instance_dir: Instance directory path (may be None)

    Returns:
        Dict with keys "process_terminated" and "directory_removed"
    """
    result = {"process_terminated": False, "directory_removed": False}

    logger.info(
        f"Starting cleanup for session {session_id} "
        f"(pid={pid}, dir={instance_dir})"
    )

    if pid:
        result["process_terminated"] = terminate_agent_process(
            pid, instance_dir or ""
        )

    if instance_dir:
        result["directory_removed"] = cleanup_instance_directory(instance_dir)

    logger.info(
        f"Cleanup complete for session {session_id}: "
        f"process_terminated={result['process_terminated']}, "
        f"directory_removed={result['directory_removed']}"
    )

    return result
