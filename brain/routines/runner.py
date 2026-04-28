from __future__ import annotations

import traceback
from datetime import UTC, datetime, timedelta

from brain.config import BrainConfig
from brain.routines.models import RoutineContext, RoutineResult, RoutineState
from brain.routines.paths import state_db_path
from brain.routines.registry import get_action
from brain.routines.state import StateStore


def run_routine(
    name: str,
    cfg: BrainConfig | None = None,
    state_store: StateStore | None = None,
) -> RoutineResult:
    cfg = cfg or BrainConfig.load_from()
    routine_cfg = next((r for r in cfg.routines if r.name == name), None)
    state_store = state_store or _default_state_store(cfg)
    state = state_store.get(name) or RoutineState(name=name)
    now = datetime.now(UTC)

    if routine_cfg is None:
        result = RoutineResult(success=False, message=f"Routine '{name}' not found in config")
    elif not routine_cfg.enabled:
        result = RoutineResult(success=False, message=f"Routine '{name}' is disabled")
    else:
        action_cls = get_action(routine_cfg.action)
        if action_cls is None:
            result = RoutineResult(
                success=False,
                message=f"Unknown action '{routine_cfg.action}' for routine '{name}'",
            )
        else:
            context = RoutineContext(
                config=cfg,
                routine_name=name,
                trigger=routine_cfg.trigger,
                query=routine_cfg.query,
            )
            try:
                instance = action_cls()
                result = instance.run(context, routine_cfg.params)
            except Exception as exc:
                result = RoutineResult(
                    success=False,
                    message=f"{exc}\n{traceback.format_exc()}",
                )

    if result.success:
        state.last_run = now
        state.failures = 0
        state.last_error = None
        state.next_run = None  # scheduler will recompute for scheduled triggers
    else:
        state.failures += 1
        state.last_error = result.message
        if routine_cfg is not None and state.failures >= routine_cfg.retries:
            state.next_run = None
        else:
            backoff_seconds = min(2**state.failures * 60, 3600)
            state.next_run = now + timedelta(seconds=backoff_seconds)

    state_store.upsert(state)
    return result


def _default_state_store(cfg: BrainConfig) -> StateStore:
    return StateStore(state_db_path(cfg))
