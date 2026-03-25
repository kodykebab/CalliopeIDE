import sys
import pytest

_STUBBED_MODS = ["server.utils.auth_utils", "server.models", "server.utils.monitoring"]
_original_mods = {}

@pytest.fixture(autouse=True, scope="session")
def restore_stubbed_modules():
    """Restore any stubbed modules after soroban test collection."""
    yield
    for mod in _STUBBED_MODS:
        sys.modules.pop(mod, None)
