from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from brain.config import BrainConfig


class TriggerSpec(BaseModel):
    type: str  # "schedule", "event", "manual"
    value: str | None = None


class RoutineConfig(BaseModel):
    name: str
    action: str
    trigger: TriggerSpec
    query: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    retries: int = 3


class RoutineState(BaseModel):
    name: str
    last_run: datetime | None = None
    next_run: datetime | None = None
    failures: int = 0
    last_error: str | None = None


@dataclass
class RoutineContext:
    config: BrainConfig
    routine_name: str
    trigger: TriggerSpec
    query: str | None = None
    _store: Any | None = field(default=None, repr=False)
    _ollama: Any | None = field(default=None, repr=False)

    def search(self, query: str | None = None, n_results: int = 5) -> list[dict[str, Any]]:
        """Run a vector search against the brain store."""
        query = query or self.query
        if not query:
            return []

        if self._store is None:
            from brain.providers import get_embedder
            from brain.store import BrainStore

            self._store = BrainStore(db_path=self.config.db_path)
            self._ollama = get_embedder(self.config)

        embedding = self._ollama.embed(query, model=self.config.embed_model)
        return self._store.query(embedding, n_results=n_results)


@dataclass
class RoutineResult:
    success: bool
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class RoutineAction(ABC):
    name: ClassVar[str]

    @abstractmethod
    def run(self, context: RoutineContext, params: dict[str, Any]) -> RoutineResult: ...


def format_query_results(results: list[dict[str, Any]], plain: bool = False) -> str:
    """Format search results into a readable markdown-like string.

    Args:
        results: Search results from BrainStore.query()
        plain: If True, strip markdown formatting for plain-text consumers.
    """
    if not results:
        return "No matching notes found." if plain else "_No matching notes found._"

    lines: list[str] = []
    for i, r in enumerate(results, 1):
        meta = r.get("metadata", {})
        title = meta.get("title", "Untitled")
        source = meta.get("source_path", "")
        date = meta.get("date", "")
        doc_type = meta.get("doc_type", "")
        text = r.get("text", "").strip()

        if plain:
            header = f"{i}. {title}"
            if doc_type:
                header += f" ({doc_type})"
            if date:
                header += f" - {date}"
            lines.append(header)
            if source:
                lines.append(source)
        else:
            header = f"**{i}. {title}**"
            if doc_type:
                header += f" ({doc_type})"
            if date:
                header += f" — {date}"
            lines.append(header)
            if source:
                lines.append(f"_{source}_")

        if text:
            # Truncate very long chunks
            snippet = text[:800] + "..." if len(text) > 800 else text
            lines.append(snippet)
        lines.append("")

    return "\n".join(lines)


def append_query_results(
    context: RoutineContext,
    params: dict[str, Any],
    content: str,
    *,
    plain: bool = False,
    default_n_results: int = 5,
) -> tuple[str, RoutineResult | None]:
    query = params.get("query") or context.query
    if not query:
        return content, None

    try:
        results = context.search(query, n_results=params.get("n_results", default_n_results))
    except Exception as exc:
        return content, RoutineResult(
            success=False,
            message=f"Query failed for routine '{context.routine_name}': {exc}",
        )

    recap = format_query_results(results, plain=plain)
    if content:
        return f"{content}\n\n{recap}", None
    return recap, None
