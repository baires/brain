from pathlib import Path

from brain.config import BrainConfig
from brain.ingest import ingest_document
from brain.parser import ParseError, parse_document
from brain.prompts import STRUCTURE_TRANSCRIPT_SYSTEM_PROMPT, build_structure_transcript_prompt
from brain.providers import get_embedder, get_provider
from brain.providers.base import LLMProvider
from brain.store import BrainStore


def _wrap_raw_markdown(
    raw_text: str,
    *,
    title: str,
    doc_date: str,
    doc_type: str,
    tags: list[str] | None = None,
    author: str | None = None,
) -> str:
    lines = ["---"]
    lines.append(f'title: "{title}"')
    lines.append(f"date: {doc_date}")
    lines.append(f"type: {doc_type}")
    if tags:
        lines.append(f"tags: [{', '.join(tags)}]")
    if author:
        lines.append(f'author: "{author}"')
    lines.append("---")
    lines.append("")
    lines.append(raw_text)
    return "\n".join(lines)


def _structure_raw_markdown(
    raw_text: str,
    *,
    title: str,
    doc_date: str,
    doc_type: str,
    tags: list[str] | None,
    author: str | None,
    llm: LLMProvider,
    chat_model: str,
) -> str:
    prompt = build_structure_transcript_prompt(
        title=title,
        doc_date=doc_date,
        doc_type=doc_type,
        tags=tags,
        author=author,
        raw_text=raw_text,
    )
    structured = "".join(
        llm.chat(
            prompt=prompt,
            model=chat_model,
            system=STRUCTURE_TRANSCRIPT_SYSTEM_PROMPT,
        )
    ).strip()
    if structured.startswith("```"):
        structured = (
            structured.removeprefix("```markdown").removeprefix("```").removesuffix("```").strip()
        )
    return structured


def run_import_raw(
    path: str,
    title: str,
    doc_date: str,
    doc_type: str,
    tags: list[str] | None = None,
    author: str | None = None,
    structure: bool = False,
) -> None:
    if not title or not doc_date or not doc_type:
        raise ValueError("--title, --date, and --type are required")

    raw_text = Path(path).read_text(encoding="utf-8")
    cfg = BrainConfig.load_from()
    store = BrainStore(db_path=cfg.db_path)
    llm = get_provider(cfg)
    embedder = get_embedder(cfg)

    if structure:
        wrapped = _structure_raw_markdown(
            raw_text,
            title=title,
            doc_date=doc_date,
            doc_type=doc_type,
            tags=tags,
            author=author,
            llm=llm,
            chat_model=cfg.chat_model,
        )
        print("Structured raw transcript with local model.")
    else:
        wrapped = _wrap_raw_markdown(
            raw_text,
            title=title,
            doc_date=doc_date,
            doc_type=doc_type,
            tags=tags,
            author=author,
        )

    try:
        doc = parse_document(wrapped, source_path=path)
    except ParseError as e:
        raise ValueError(f"Structured document did not validate: {e}") from e

    chunk_count = ingest_document(
        doc,
        store,
        embedder,
        embed_model=cfg.embed_model,
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
    )
    if not chunk_count:
        print("No chunks generated.")
        return
    print(f"Ingested {path} ({chunk_count} chunks)")
