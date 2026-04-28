from __future__ import annotations

from brain.config import BrainConfig
from brain.routines.paths import state_db_path
from brain.routines.runner import run_routine
from brain.routines.state import StateStore


def emit(event_name: str, **kwargs) -> list[tuple[str, bool, str]]:
    """Emit an event and run any matching event-driven routines.

    Returns a list of (routine_name, success, message) tuples.
    """
    cfg = BrainConfig.load_from()
    results = []

    state_store = StateStore(state_db_path(cfg))

    for routine in cfg.routines:
        if (
            routine.enabled
            and routine.trigger.type == "event"
            and routine.trigger.value == event_name
        ):
            result = run_routine(routine.name, cfg=cfg, state_store=state_store)
            results.append((routine.name, result.success, result.message))

    return results
