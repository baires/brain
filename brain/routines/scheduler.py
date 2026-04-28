from __future__ import annotations

import re
import signal
import threading
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from croniter import croniter

from brain.config import BrainConfig
from brain.routines.models import RoutineState
from brain.routines.paths import state_db_path
from brain.routines.runner import run_routine
from brain.routines.state import StateStore

if TYPE_CHECKING:
    from brain.routines.models import RoutineConfig

_INTERVAL_RE = re.compile(r"^interval:(\d+)([smhd])$")


def parse_interval(value: str) -> timedelta:
    match = _INTERVAL_RE.match(value)
    if not match:
        raise ValueError(f"Invalid interval format: {value}")
    amount = int(match.group(1))
    unit = match.group(2)
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return timedelta(seconds=amount * multipliers[unit])


def compute_next_run(trigger_value: str, now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    if trigger_value.startswith("interval:"):
        delta = parse_interval(trigger_value)
        return now + delta
    # Assume cron expression
    itr = croniter(trigger_value, now)
    return itr.get_next(datetime)


def should_run(routine: RoutineConfig, state_store: StateStore) -> bool:
    if not routine.enabled:
        return False
    if routine.trigger.type != "schedule":
        return False

    state = state_store.get(routine.name)
    if state is None:
        try:
            next_run = compute_next_run(routine.trigger.value or "")
        except Exception:
            return False
        state_store.upsert(RoutineState(name=routine.name, next_run=next_run))
        return False

    if state.failures >= routine.retries:
        return False

    next_run = state.next_run
    if next_run is None:
        # No next_run set yet; compute it
        try:
            next_run = compute_next_run(routine.trigger.value or "")
        except Exception:
            return False
        state.next_run = next_run
        state_store.upsert(state)

    return datetime.now(UTC) >= next_run


class RoutineDaemon:
    def __init__(
        self,
        cfg: BrainConfig | None = None,
        state_store: StateStore | None = None,
        tick_interval: int = 10,
    ):
        self.cfg = cfg or BrainConfig.load_from()
        self.state_store = state_store or self._default_state_store()
        self.tick_interval = tick_interval
        self._stop_event = threading.Event()

    def _default_state_store(self) -> StateStore:
        return StateStore(state_db_path(self.cfg))

    def start(self) -> None:
        signal.signal(signal.SIGTERM, self._on_signal)
        signal.signal(signal.SIGINT, self._on_signal)

        print(f"Routine daemon started. Tick every {self.tick_interval}s.")
        print(f"Configured routines: {len(self.cfg.routines)}")

        while not self._stop_event.is_set():
            self._tick()
            self._stop_event.wait(self.tick_interval)

        print("Routine daemon stopped.")

    def _tick(self) -> None:
        for routine in self.cfg.routines:
            if should_run(routine, self.state_store):
                print(f"[{datetime.now(UTC).isoformat()}] Running routine: {routine.name}")
                result = run_routine(routine.name, cfg=self.cfg, state_store=self.state_store)
                if result.success:
                    # Recompute next_run based on schedule
                    state = self.state_store.get(routine.name)
                    if state is not None:
                        try:
                            state.next_run = compute_next_run(routine.trigger.value or "")
                        except Exception:
                            state.next_run = None
                        self.state_store.upsert(state)
                    print(f"  -> succeeded: {result.message}")
                else:
                    print(f"  -> failed: {result.message}")

    def _on_signal(self, signum, frame) -> None:
        print(f"\nReceived signal {signum}, shutting down...")
        self._stop_event.set()

    def stop(self) -> None:
        self._stop_event.set()
