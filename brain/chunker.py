import re
from collections.abc import Callable
from dataclasses import dataclass, field
from types import SimpleNamespace

from brain.schema import BrainDocument


@dataclass
class Chunk:
    id: str
    text: str
    meta: object
    breadcrumbs: list[str] = field(default_factory=list)


@dataclass
class Section:
    breadcrumbs: list[str]
    heading: str
    body: str


def _split_by_headers(text: str) -> list[Section]:
    """Split markdown into sections while preserving # through ###### breadcrumbs."""
    lines = text.splitlines()
    sections: list[Section] = []
    heading_stack: list[tuple[int, str]] = []
    current_breadcrumbs: list[str] = []
    current_heading = ""
    current_lines = []

    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            if current_lines:
                sections.append(
                    Section(
                        breadcrumbs=current_breadcrumbs.copy(),
                        heading=current_heading,
                        body="\n".join(current_lines).strip(),
                    )
                )
            level = len(match.group(1))
            heading = match.group(2).strip()
            heading_stack = [(lvl, text) for lvl, text in heading_stack if lvl < level]
            heading_stack.append((level, heading))
            current_breadcrumbs = [text for _, text in heading_stack]
            current_heading = heading
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines or current_heading:
        sections.append(
            Section(
                breadcrumbs=current_breadcrumbs.copy(),
                heading=current_heading,
                body="\n".join(current_lines).strip(),
            )
        )

    if not sections:
        sections.append(Section(breadcrumbs=[], heading="", body=text.strip()))
    return sections


def _split_by_paragraphs(text: str) -> list[str]:
    """Split text into block-ish units without splitting lists, tables, quotes, or code blocks."""
    blocks: list[str] = []
    current: list[str] = []
    in_code = False

    def flush() -> None:
        nonlocal current
        if current:
            block = "\n".join(current).strip()
            if block:
                blocks.append(block)
            current = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            current.append(line)
            in_code = not in_code
            continue
        if not stripped and not in_code:
            flush()
            continue
        current.append(line)
    flush()
    return blocks


def _default_token_count(text: str) -> int:
    return len(text) // 4


def _split_oversized(text: str, max_tokens: int, count_tokens: Callable[[str], int]) -> list[str]:
    """Split text into pieces under max_tokens by sentences, or words if no sentences."""
    if count_tokens(text) <= max_tokens:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if len(sentences) <= 1:
        # No sentence boundaries — split by words
        words = text.split()
        # approximate chars limit based on max_tokens to prevent very slow iterations
        max_chars = max_tokens * 4
        pieces = []
        current = ""
        for word in words:
            if len(current) + 1 + len(word) > max_chars and current:
                pieces.append(current.strip())
                current = word
            else:
                current = (current + " " + word).strip() if current else word
        if current:
            pieces.append(current.strip())
        return pieces
    pieces = []
    current = ""
    for sent in sentences:
        if count_tokens(current + " " + sent) > max_tokens and current:
            pieces.append(current.strip())
            current = sent
        else:
            current = (current + " " + sent).strip() if current else sent
    if current:
        pieces.append(current.strip())
    return pieces


def _overlap_text(text: str, overlap_tokens: int) -> str:
    if overlap_tokens <= 0:
        return ""
    max_chars = overlap_tokens * 4
    words = text.split()
    selected: list[str] = []
    total = 0
    for word in reversed(words):
        added = len(word) + (1 if selected else 0)
        if total + added > max_chars:
            break
        selected.append(word)
        total += added
    return " ".join(reversed(selected))


def _merge_chunks(
    parts: list[str],
    max_tokens: int,
    overlap_tokens: int = 0,
    count_tokens: Callable[[str], int] = _default_token_count,
) -> list[str]:
    """Merge small parts into chunks under max_tokens."""
    split_parts = []
    for part in parts:
        split_parts.extend(_split_oversized(part, max_tokens, count_tokens))

    chunks = []
    current = ""
    for part in split_parts:
        if count_tokens(current + "\n\n" + part) > max_tokens and current:
            chunks.append(current.strip())
            overlap = _overlap_text(current, overlap_tokens)
            current = (overlap + "\n\n" + part).strip() if overlap else part
        else:
            current = (current + "\n\n" + part).strip() if current else part
    if current:
        chunks.append(current.strip())
    return chunks


def _has_structured_headers(text: str) -> bool:
    return bool(re.search(r"^#{1,6}\s+", text, re.MULTILINE))


def chunk_document(
    doc: BrainDocument,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    count_tokens: Callable[[str], int] | None = None,
) -> list[Chunk]:
    text = doc.content
    structured = _has_structured_headers(text)
    chunks = []
    counter = count_tokens or _default_token_count

    base_meta = {
        "source_path": doc.source_path or "",
        "title": doc.meta.title,
        "doc_type": doc.meta.type.value,
        "date": str(doc.meta.date),
        "tags": ",".join(doc.meta.tags),
        "author": doc.meta.author or "",
        "source": doc.meta.source or "",
        "heading": "",
        "chunk_index": 0,
    }

    if structured:
        sections = _split_by_headers(text)
        for section in sections:
            if not section.body:
                continue
            parts = _split_by_paragraphs(section.body)
            merged = _merge_chunks(parts, chunk_size, chunk_overlap, count_tokens=counter)
            for _idx, m in enumerate(merged):
                chunk_id = f"{doc.source_path or 'raw'}#{len(chunks)}"
                breadcrumbs = [doc.meta.title] + section.breadcrumbs
                chunk_text = (
                    f"{'#' * max(2, len(section.breadcrumbs))} {section.heading}\n\n{m}"
                    if section.heading
                    else m
                )
                meta = SimpleNamespace(**base_meta)
                meta.heading = section.heading
                meta.chunk_index = len(chunks)
                chunks.append(
                    Chunk(
                        id=chunk_id,
                        text=chunk_text,
                        meta=meta,
                        breadcrumbs=breadcrumbs,
                    )
                )
    else:
        parts = _split_by_paragraphs(text)
        merged = _merge_chunks(parts, chunk_size, chunk_overlap, count_tokens=counter)
        for _idx, m in enumerate(merged):
            chunk_id = f"{doc.source_path or 'raw'}#{len(chunks)}"
            meta = SimpleNamespace(**base_meta)
            meta.chunk_index = len(chunks)
            chunks.append(
                Chunk(
                    id=chunk_id,
                    text=m,
                    meta=meta,
                    breadcrumbs=[doc.meta.title],
                )
            )

    return chunks
