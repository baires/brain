from datetime import date, timedelta
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.status import Status

from brain.config import BrainConfig
from brain.ollama import OllamaClient
from brain.query import QueryEngine
from brain.store import BrainStore

console = Console()


def _today() -> date:
    return date.today()


def build_filters(
    doc_type: str | None = None, last_ndays: int | None = None
) -> dict[str, Any] | None:
    clauses: list[dict[str, Any]] = []
    if doc_type:
        clauses.append({"doc_type": doc_type})
    if last_ndays is not None:
        since = _today() - timedelta(days=last_ndays)
        clauses.append({"date_num": {"$gte": int(since.strftime("%Y%m%d"))}})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _collect_and_render(tokens, console: Console) -> None:
    parts: list[str] = []
    with Status("[dim]Thinking…[/dim]", console=console):
        for token in tokens:
            parts.append(token)
    console.print(Markdown("".join(parts)))


def run_ask(
    question: str,
    doc_type: str | None = None,
    last_ndays: int | None = None,
    show_context: bool = False,
) -> None:
    cfg = BrainConfig.load_from()
    store = BrainStore(db_path=cfg.db_path)
    ollama = OllamaClient(base_url=cfg.ollama_url)
    engine = QueryEngine(
        store=store,
        ollama=ollama,
        embed_model=cfg.embed_model,
        chat_model=cfg.chat_model,
        fetch_k=cfg.retrieval_fetch_k,
        top_k=cfg.retrieval_top_k,
        mmr_lambda=cfg.retrieval_mmr_lambda,
        max_context_chars=cfg.retrieval_max_context_chars,
        max_best_distance=cfg.retrieval_max_best_distance,
        relative_distance_margin=cfg.retrieval_relative_distance_margin,
        system_prompt=cfg.agent.system_prompt,
        query_expansion=cfg.retrieval_query_expansion,
    )

    filters = build_filters(doc_type, last_ndays)

    if show_context:
        results = engine.retrieve(question, filters=filters)
        console.print("[dim]Retrieved context:[/dim]")
        if results:
            for result in results:
                section = " > ".join(result.breadcrumbs)
                console.print(
                    f"[dim][[{result.citation}] distance={result.distance:.4f} "
                    f'title="{result.title}" date="{result.date}" type="{result.doc_type}" '
                    f'section="{section}" source="{result.source_path}" chunk="{result.id}"][/dim]'
                )
        else:
            console.print("[dim](none)[/dim]")
        console.print()
        if not results:
            console.print("I don't know based on your notes.")
            return
        context = engine.build_context(results)
        prompt = engine.build_prompt(question, context)
        _collect_and_render(
            ollama.chat(prompt=prompt, model=cfg.chat_model, system=cfg.agent.system_prompt),
            console,
        )
        return

    _collect_and_render(engine.ask(question, filters=filters), console)
