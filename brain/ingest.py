from typing import Any

from brain.providers.base import EmbeddingProvider, TokenizerProvider


def ingest_document(
    doc: Any,
    store: Any,
    embedder: EmbeddingProvider,
    *,
    embed_model: str,
    chunk_size: int,
    chunk_overlap: int,
    tokenizer: TokenizerProvider | None = None,
) -> int:
    from brain.chunker import chunk_document

    count_tokens = tokenizer.count_tokens if tokenizer else None
    chunks = chunk_document(
        doc, chunk_size=chunk_size, chunk_overlap=chunk_overlap, count_tokens=count_tokens
    )
    if not chunks:
        return 0
    embeddings = [embedder.embed(_embedding_text(chunk), model=embed_model) for chunk in chunks]
    store.replace_source_chunks(doc.source_path or "raw", chunks, embeddings)
    return len(chunks)


def _embedding_text(chunk) -> str:
    breadcrumbs = " > ".join(chunk.breadcrumbs) if chunk.breadcrumbs else ""
    raw_tags = getattr(chunk.meta, "tags", "")
    tags = " ".join(t.strip() for t in raw_tags.split(",") if t.strip()) if raw_tags else ""

    parts = []
    if title := getattr(chunk.meta, "title", ""):
        parts.append(f"Title: {title}")
    if doc_type := getattr(chunk.meta, "doc_type", ""):
        parts.append(f"Type: {doc_type}")
    if date := getattr(chunk.meta, "date", ""):
        parts.append(f"Date: {date}")
    if author := getattr(chunk.meta, "author", ""):
        parts.append(f"Author: {author}")
    if source := getattr(chunk.meta, "source", ""):
        parts.append(f"Source: {source}")
    if tags:
        parts.append(f"Tags: {tags}")
    if breadcrumbs:
        parts.append(f"Section: {breadcrumbs}")

    parts.append(f"Content:\n{chunk.text}")
    return "\n".join(parts)
