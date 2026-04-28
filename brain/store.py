import contextlib
from datetime import date
from typing import Any

import chromadb
from chromadb.config import Settings


class BrainStore:
    def __init__(self, db_path: str, collection_name: str = "brain"):
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def add_chunks(self, chunks: list[Any], embeddings: list[list[float]]) -> None:
        ids = [c.id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = []
        for c in chunks:
            meta = {
                "source_path": getattr(c.meta, "source_path", ""),
                "title": getattr(c.meta, "title", ""),
                "doc_type": getattr(c.meta, "doc_type", ""),
                "date": getattr(c.meta, "date", ""),
                "date_num": self._date_num(getattr(c.meta, "date", "")),
                "tags": getattr(c.meta, "tags", ""),
                "author": getattr(c.meta, "author", ""),
                "source": getattr(c.meta, "source", ""),
                "breadcrumbs": " > ".join(c.breadcrumbs) if c.breadcrumbs else "",
                "heading": getattr(c.meta, "heading", ""),
                "chunk_index": getattr(c.meta, "chunk_index", 0),
            }
            metadatas.append(meta)
        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def replace_source_chunks(
        self, source_path: str, chunks: list[Any], embeddings: list[list[float]]
    ) -> None:
        with contextlib.suppress(Exception):
            self.collection.delete(where={"source_path": source_path})
        if chunks:
            self.add_chunks(chunks, embeddings)

    def query(
        self,
        embedding: list[float],
        filters: dict[str, Any] | None = None,
        n_results: int = 5,
    ) -> list[dict[str, Any]]:
        where = filters if filters else None
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances", "embeddings"],
        )
        output = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                output.append(
                    {
                        "id": doc_id,
                        "text": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i],
                        "embedding": (
                            results.get("embeddings", [[]])[0][i]
                            if results.get("embeddings")
                            else None
                        ),
                    }
                )
        return output

    def count(self) -> int:
        return self.collection.count()

    def _date_num(self, value: str) -> int:
        try:
            return int(date.fromisoformat(value).strftime("%Y%m%d"))
        except (TypeError, ValueError):
            return 0
