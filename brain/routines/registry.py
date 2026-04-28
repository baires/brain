from __future__ import annotations

import importlib.metadata

from brain.routines.models import RoutineAction, RoutineResult

BUILTIN_ACTIONS: dict[str, type[RoutineAction]] = {}


def register_builtin(action_cls: type[RoutineAction]) -> type[RoutineAction]:
    BUILTIN_ACTIONS[action_cls.name] = action_cls
    return action_cls


def _load_entry_points() -> dict[str, type[RoutineAction]]:
    actions: dict[str, type[RoutineAction]] = {}
    try:
        eps = importlib.metadata.entry_points(group="brain.routines")
    except TypeError:
        # Python < 3.10 compat
        eps = importlib.metadata.entry_points().get("brain.routines", ())
    for ep in eps:
        try:
            action_cls = ep.load()
            actions[action_cls.name] = action_cls
        except Exception:
            continue
    return actions


def list_actions() -> dict[str, type[RoutineAction]]:
    # Ensure built-in actions are registered
    from brain.routines import builtins  # noqa: F401

    actions = dict(BUILTIN_ACTIONS)
    actions.update(_load_entry_points())
    return actions


def get_action(name: str) -> type[RoutineAction] | None:
    return list_actions().get(name)


def run_action(name: str, context, params: dict) -> RoutineResult:
    action_cls = get_action(name)
    if action_cls is None:
        raise ValueError(f"Unknown routine action: {name}")
    instance = action_cls()
    return instance.run(context, params)
