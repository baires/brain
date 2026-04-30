from __future__ import annotations

import re
from typing import Any

import typer

from brain.config import BrainConfig
from brain.providers import get_embedder, get_provider
from brain.query import QueryEngine
from brain.routines.models import RoutineContext
from brain.routines.registry import get_action
from brain.store import BrainStore

_ACTION_PATTERNS: list[tuple[str, str]] = [
    (r"send\s+(.+?)\s+to\s+slack", "slack"),
    (r"post\s+(.+?)\s+to\s+slack", "slack"),
    (r"slack\s+(.+)", "slack"),
    (r"email\s+me\s+(.+)", "email"),
    (r"email\s+(.+)", "email"),
    (r"create\s+a?\s*pdf\s+(?:of|with)?\s*(.+)", "pdf_export"),
    (r"save\s+(.+?)\s+as\s+pdf", "pdf_export"),
    (r"post\s+(.+?)\s+to\s+google\s*doc", "google_doc"),
    (r"save\s+(.+?)\s+to\s+google\s*doc", "google_doc"),
]


def _parse_instruction(instruction: str) -> tuple[str, str] | None:
    instruction_lower = instruction.lower().strip()
    for pattern, action in _ACTION_PATTERNS:
        match = re.search(pattern, instruction_lower)
        if match:
            query = match.group(1).strip()
            return action, query
    return None


def _find_defaults(action_name: str, cfg: BrainConfig) -> dict[str, Any]:
    """Find the first enabled routine with this action and return its params."""
    for routine in cfg.routines:
        if routine.action == action_name and routine.enabled:
            return dict(routine.params)
    return {}


def _ask_brain(question: str, cfg: BrainConfig) -> str:
    store = BrainStore(db_path=cfg.db_path)
    provider = get_provider(cfg)
    engine = QueryEngine(
        store=store,
        llm=provider,
        embedder=get_embedder(cfg),
        embed_model=cfg.embed_model,
        chat_model=cfg.chat_model,
        fetch_k=cfg.retrieval_fetch_k,
        top_k=cfg.retrieval_top_k,
        mmr_lambda=cfg.retrieval_mmr_lambda,
        max_context_tokens=cfg.retrieval_max_context_tokens,
        max_best_distance=cfg.retrieval_max_best_distance,
        relative_distance_margin=cfg.retrieval_relative_distance_margin,
        system_prompt=cfg.agent.system_prompt,
        query_expansion=cfg.retrieval_query_expansion,
    )
    parts: list[str] = []
    for token in engine.ask(question):
        parts.append(token)
    return "".join(parts).strip()


def _format_for_slack(text: str) -> str:
    """Convert markdown-like LLM output to Slack mrkdwn."""
    # Replace markdown bold **text** with Slack bold *text*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)

    # Replace markdown bullets '* ' at line start with '• '
    # Be careful not to touch '*text*' (Slack bold)
    lines = []
    for line in text.splitlines():
        if line.startswith("* "):
            lines.append("• " + line[2:])
        else:
            lines.append(line)
    text = "\n".join(lines)

    # Keep citation source but strip chunk hash: [N: path#chunk] → [N: path]
    text = re.sub(r"\[(\d+):\s*([^\]#]+)(?:#[^\]]*)?\]", r"[\1: \2]", text)

    return text


def run_do(instruction: str) -> None:
    parsed = _parse_instruction(instruction)
    if parsed is None:
        print(
            "Could not understand instruction. Try something like:\n"
            '  brain do "send yesterday meetings to slack"\n'
            '  brain do "email me action items from last week"\n'
            '  brain do "create a pdf of sales notes"'
        )
        return

    action_name, query = parsed
    cfg = BrainConfig.load_from()

    # Generate answer
    print(f"Thinking about: {query}")
    answer = _ask_brain(query, cfg)
    if not answer:
        print("I don't know based on your notes.")
        return

    # Find default params from configured routines
    defaults = _find_defaults(action_name, cfg)
    if not defaults:
        print(
            f"No default params found for '{action_name}'.\n"
            f"Configure a routine with action='{action_name}' in ~/.brain/config.toml first."
        )
        return

    # Build params with the answer injected
    params = dict(defaults)
    if action_name == "slack":
        formatted = _format_for_slack(answer)
        params["message"] = f":brain: *Recap: {query.capitalize()}*\n\n{formatted}"
    elif action_name == "email" or action_name == "pdf_export":
        params["body"] = f"{query.capitalize()}\n\n{answer}"
    elif action_name == "google_doc":
        params["content"] = f"{query.capitalize()}\n\n{answer}"

    action_cls = get_action(action_name)
    if action_cls is None:
        print(f"Action '{action_name}' is not available.")
        return

    context = RoutineContext(
        config=cfg,
        routine_name="do",
        trigger=__import__("brain.routines.models", fromlist=["TriggerSpec"]).TriggerSpec(
            type="manual"
        ),
    )

    instance = action_cls()
    result = instance.run(context, params)

    if result.success:
        print(f"Delivered via {action_name}: {result.message}")
    else:
        print(f"Delivery failed: {result.message}")
        raise typer.Exit(1)
