import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from brain.routines.models import RoutineState
from brain.routines.runner import run_routine
from brain.routines.state import StateStore


def test_state_store_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(Path(tmpdir) / "state.db")

        assert store.get("missing") is None
        assert store.list_all() == []

        state = RoutineState(name="test", failures=2, last_error="boom")
        store.upsert(state)

        fetched = store.get("test")
        assert fetched is not None
        assert fetched.name == "test"
        assert fetched.failures == 2
        assert fetched.last_error == "boom"

        states = store.list_all()
        assert len(states) == 1


def test_run_routine_success():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.toml"
        config_path.write_text("""
ollama_url = "http://localhost:11434"

[[routines]]
name = "test-echo"
action = "echo"
trigger = { type = "manual" }
params = { message = "hello world" }
""")

        import brain.config as config_mod

        orig_default = config_mod.DEFAULT_CONFIG_PATH
        config_mod.DEFAULT_CONFIG_PATH = config_path
        try:
            result = run_routine("test-echo")
            assert result.success is True
            assert result.message == "hello world"
        finally:
            config_mod.DEFAULT_CONFIG_PATH = orig_default


def test_run_routine_not_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.toml"
        config_path.write_text('ollama_url = "http://localhost:11434"\n')

        import brain.config as config_mod

        orig_default = config_mod.DEFAULT_CONFIG_PATH
        config_mod.DEFAULT_CONFIG_PATH = config_path
        try:
            result = run_routine("missing")
            assert result.success is False
            assert "not found" in result.message
        finally:
            config_mod.DEFAULT_CONFIG_PATH = orig_default


def test_run_routine_failure_backoff():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.toml"
        config_path.write_text("""
ollama_url = "http://localhost:11434"

[[routines]]
name = "test-bad"
action = "nonexistent-action"
trigger = { type = "manual" }
""")

        import brain.config as config_mod

        orig_default = config_mod.DEFAULT_CONFIG_PATH
        config_mod.DEFAULT_CONFIG_PATH = config_path
        try:
            state_store = StateStore(Path(tmpdir) / "state.db")
            result = run_routine("test-bad", state_store=state_store)
            assert result.success is False

            state = state_store.get("test-bad")
            assert state is not None
            assert state.failures == 1
            assert state.last_error is not None
            assert state.next_run is not None
            # Backoff should be ~2 minutes
            assert state.next_run > datetime.now(UTC)
            assert state.next_run < datetime.now(UTC) + timedelta(minutes=5)
        finally:
            config_mod.DEFAULT_CONFIG_PATH = orig_default


def test_run_routine_stops_scheduling_after_retry_limit():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.toml"
        config_path.write_text("""
ollama_url = "http://localhost:11434"

[[routines]]
name = "test-bad"
action = "nonexistent-action"
trigger = { type = "schedule", value = "interval:1m" }
retries = 1
""")

        import brain.config as config_mod

        orig_default = config_mod.DEFAULT_CONFIG_PATH
        config_mod.DEFAULT_CONFIG_PATH = config_path
        try:
            state_store = StateStore(Path(tmpdir) / "state.db")
            result = run_routine("test-bad", state_store=state_store)

            assert result.success is False
            state = state_store.get("test-bad")
            assert state is not None
            assert state.failures == 1
            assert state.next_run is None
        finally:
            config_mod.DEFAULT_CONFIG_PATH = orig_default
