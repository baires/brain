import pytest

import brain.cli as _brain_cli

# Capture the real implementation before any test patches it
_real_maybe_auto_backup = _brain_cli._maybe_auto_backup


@pytest.fixture(autouse=True)
def disable_auto_backup(monkeypatch):
    """Prevent tests from triggering auto-backups in the real ~/.brain directory."""
    monkeypatch.setattr(_brain_cli, "_maybe_auto_backup", lambda: None)


@pytest.fixture
def real_maybe_auto_backup():
    """Return the real _maybe_auto_backup function, bypassing the autouse no-op patch."""
    return _real_maybe_auto_backup
