import sys
import pytest

_STUB_MODS = [
    "server.utils.auth_utils",
    "server.models", 
    "server.utils.monitoring",
]

@pytest.fixture(autouse=True)
def restore_stubs():
    """Restore stubbed modules before each test to prevent contamination."""
    yield
    # Cleanup setelah setiap test
    for mod in _STUB_MODS:
        sys.modules.pop(mod, None)
