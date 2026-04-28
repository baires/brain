from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from brain.routines.models import RoutineState

SCHEMA = """
CREATE TABLE IF NOT EXISTS routines_state (
    name TEXT PRIMARY KEY,
    last_run TEXT,
    next_run TEXT,
    failures INTEGER DEFAULT 0,
    last_error TEXT
);
"""


class StateStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        try:
            yield conn
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def get(self, name: str) -> RoutineState | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT name, last_run, next_run, failures, last_error FROM routines_state WHERE name = ?",
                (name,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_state(row)

    def upsert(self, state: RoutineState) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO routines_state (name, last_run, next_run, failures, last_error)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    last_run=excluded.last_run,
                    next_run=excluded.next_run,
                    failures=excluded.failures,
                    last_error=excluded.last_error
                """,
                self._state_to_row(state),
            )
            conn.commit()

    def list_all(self) -> list[RoutineState]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name, last_run, next_run, failures, last_error FROM routines_state"
            ).fetchall()
        return [self._row_to_state(r) for r in rows]

    @staticmethod
    def _row_to_state(row: tuple[Any, ...]) -> RoutineState:
        return RoutineState(
            name=row[0],
            last_run=_parse_iso(row[1]),
            next_run=_parse_iso(row[2]),
            failures=row[3] or 0,
            last_error=row[4],
        )

    @staticmethod
    def _state_to_row(state: RoutineState) -> tuple[Any, ...]:
        return (
            state.name,
            _format_iso(state.last_run),
            _format_iso(state.next_run),
            state.failures,
            state.last_error,
        )


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _format_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()
