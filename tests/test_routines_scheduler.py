import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from brain.routines.models import RoutineConfig, RoutineState, TriggerSpec
from brain.routines.scheduler import compute_next_run, parse_interval, should_run
from brain.routines.state import StateStore


def test_parse_interval():
    assert parse_interval("interval:5m") == timedelta(minutes=5)
    assert parse_interval("interval:2h") == timedelta(hours=2)
    assert parse_interval("interval:1d") == timedelta(days=1)
    assert parse_interval("interval:30s") == timedelta(seconds=30)


def test_compute_next_run_interval():
    now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    result = compute_next_run("interval:1h", now=now)
    assert result == now + timedelta(hours=1)


def test_compute_next_run_cron():
    now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    result = compute_next_run("0 14 * * *", now=now)
    assert result == datetime(2024, 1, 1, 14, 0, 0, tzinfo=UTC)


def test_should_run_disabled():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(Path(tmpdir) / "state.db")
        routine = RoutineConfig(
            name="test",
            action="echo",
            trigger=TriggerSpec(type="schedule", value="0 9 * * *"),
            enabled=False,
        )
        assert should_run(routine, store) is False


def test_should_run_no_state_schedules_next_run_without_running():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(Path(tmpdir) / "state.db")
        routine = RoutineConfig(
            name="test",
            action="echo",
            trigger=TriggerSpec(type="schedule", value="0 9 * * *"),
            enabled=True,
        )
        assert should_run(routine, store) is False
        state = store.get("test")
        assert state is not None
        assert state.next_run is not None
        assert state.next_run > datetime.now(UTC)


def test_should_run_stops_after_retry_limit():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(Path(tmpdir) / "state.db")
        past = datetime.now(UTC) - timedelta(minutes=5)
        store.upsert(RoutineState(name="test", next_run=past, failures=3))
        routine = RoutineConfig(
            name="test",
            action="echo",
            trigger=TriggerSpec(type="schedule", value="0 9 * * *"),
            enabled=True,
            retries=3,
        )
        assert should_run(routine, store) is False


def test_should_run_not_due():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(Path(tmpdir) / "state.db")
        future = datetime.now(UTC) + timedelta(hours=1)
        store.upsert(RoutineState(name="test", next_run=future))
        routine = RoutineConfig(
            name="test",
            action="echo",
            trigger=TriggerSpec(type="schedule", value="0 9 * * *"),
            enabled=True,
        )
        assert should_run(routine, store) is False


def test_should_run_due():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(Path(tmpdir) / "state.db")
        past = datetime.now(UTC) - timedelta(minutes=5)
        store.upsert(RoutineState(name="test", next_run=past))
        routine = RoutineConfig(
            name="test",
            action="echo",
            trigger=TriggerSpec(type="schedule", value="0 9 * * *"),
            enabled=True,
        )
        assert should_run(routine, store) is True
