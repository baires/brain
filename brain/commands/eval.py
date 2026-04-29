from pathlib import Path

from brain.commands.add import run_add
from brain.config import BrainConfig
from brain.ollama import OllamaClient
from brain.query import QueryEngine
from brain.store import BrainStore

EVAL_QUESTIONS = [
    (
        "What did Bob need to do for Acme?",
        ["revised proposal", "April 28"],
        "Sales Meeting with Acme Corp",
    ),
    ("What is blocking engineering?", ["staging", "OAuth"], "Engineering Daily Standup"),
    ("What decision was made about CRDT?", ["Operational Transform", "CRDT"], "Product Decisions"),
    ("What was the Acme ARR?", ["240K ARR"], "Sales Meeting with Acme Corp"),
]


def run_eval(path: str, run_ollama: bool = False) -> None:
    if not run_ollama:
        raise ValueError("Local Ollama eval is opt-in. Re-run with --run-ollama.")

    if not Path(path).exists():
        raise ValueError(f"Eval path does not exist: {path}")

    run_add(path)
    cfg = BrainConfig.load_from()
    ollama = OllamaClient(base_url=cfg.ollama_url)
    engine = QueryEngine(
        store=BrainStore(db_path=cfg.db_path),
        llm=ollama,
        embedder=ollama,
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

    failures = []
    for question, expected_terms, expected_title in EVAL_QUESTIONS:
        answer = "".join(engine.ask(question, filters=None))
        results = engine.retrieve(question, filters=None)
        cited_title_found = any(expected_title in result.title for result in results)
        has_citation = "[" in answer and "]" in answer
        missing_terms = [term for term in expected_terms if term.lower() not in answer.lower()]
        if missing_terms or not cited_title_found or not has_citation:
            failures.append((question, answer, missing_terms, cited_title_found, has_citation))
        print(f"Q: {question}")
        print(f"A: {answer}")
        print()

    if failures:
        for question, answer, missing_terms, cited_title_found, has_citation in failures:
            print(f"FAILED: {question}")
            print(f"  missing_terms={missing_terms}")
            print(f"  cited_title_found={cited_title_found}")
            print(f"  has_citation={has_citation}")
            print(f"  answer={answer}")
        raise SystemExit(1)
    print("Eval passed.")
