import sys
import pytest

_STUB_MODS = [
    "server.utils.auth_utils",
    "server.models",
    "server.utils.monitoring",
    "server.middleware.database",
    "server.utils.db_utils",
]

@pytest.fixture(autouse=True)
def restore_stubs():
    """Restore stubbed modules before AND after each test to prevent contamination."""
    # Cleanup BEFORE test runs
    for mod in _STUB_MODS:
        sys.modules.pop(mod, None)
    yield
    # Cleanup AFTER test runs
    for mod in _STUB_MODS:
        sys.modules.pop(mod, None)
