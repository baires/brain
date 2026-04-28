def ingest_document(
    doc, store, ollama, *, embed_model: str, chunk_size: int, chunk_overlap: int
) -> int:
    from brain.chunker import chunk_document

    chunks = chunk_document(doc, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not chunks:
        return 0
    embeddings = [ollama.embed(_embedding_text(chunk), model=embed_model) for chunk in chunks]
    store.replace_source_chunks(doc.source_path or "raw", chunks, embeddings)
    return len(chunks)


def _embedding_text(chunk) -> str:
    breadcrumbs = " > ".join(chunk.breadcrumbs) if chunk.breadcrumbs else ""
    meta_bits = [
        getattr(chunk.meta, "title", ""),
        getattr(chunk.meta, "doc_type", ""),
        getattr(chunk.meta, "date", ""),
        getattr(chunk.meta, "tags", ""),
        breadcrumbs,
    ]
    return "\n".join(bit for bit in meta_bits + [chunk.text] if bit)
