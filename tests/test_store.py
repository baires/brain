import tempfile

import pytest

from brain.store import BrainStore


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield BrainStore(db_path=tmpdir)


def test_add_chunks_increases_count(store):
    chunks = [
        type(
            "Chunk",
            (),
            {
                "id": "a#0",
                "text": "hello world",
                "meta": type(
                    "obj",
                    (),
                    {"source_path": "a.md", "title": "A", "doc_type": "note", "date": "2026-04-26"},
                )(),
                "breadcrumbs": ["A"],
            },
        )(),
        type(
            "Chunk",
            (),
            {
                "id": "a#1",
                "text": "foo bar",
                "meta": type(
                    "obj",
                    (),
                    {"source_path": "a.md", "title": "A", "doc_type": "note", "date": "2026-04-26"},
                )(),
                "breadcrumbs": ["A"],
            },
        )(),
    ]
    embeddings = [[0.1] * 384, [0.2] * 384]
    store.add_chunks(chunks, embeddings)
    assert store.count() == 2


def test_query_returns_top_k(store):
    chunks = [
        type(
            "Chunk",
            (),
            {
                "id": "a#0",
                "text": "hello world",
                "meta": type(
                    "obj",
                    (),
                    {"source_path": "a.md", "title": "A", "doc_type": "note", "date": "2026-04-26"},
                )(),
                "breadcrumbs": ["A"],
            },
        )(),
        type(
            "Chunk",
            (),
            {
                "id": "b#0",
                "text": "something else",
                "meta": type(
                    "obj",
                    (),
                    {
                        "source_path": "b.md",
                        "title": "B",
                        "doc_type": "meeting",
                        "date": "2026-04-26",
                    },
                )(),
                "breadcrumbs": ["B"],
            },
        )(),
    ]
    embeddings = [[0.1] * 384, [0.9] * 384]
    store.add_chunks(chunks, embeddings)
    results = store.query(embedding=[0.95] * 384, n_results=2)
    assert len(results) == 2
    # closest should be b#0
    assert results[0]["id"] == "b#0"
    assert "something else" in results[0]["text"]


def test_filter_by_type(store):
    chunks = [
        type(
            "Chunk",
            (),
            {
                "id": "a#0",
                "text": "note text",
                "meta": type(
                    "obj",
                    (),
                    {"source_path": "a.md", "title": "A", "doc_type": "note", "date": "2026-04-26"},
                )(),
                "breadcrumbs": ["A"],
            },
        )(),
        type(
            "Chunk",
            (),
            {
                "id": "b#0",
                "text": "meeting text",
                "meta": type(
                    "obj",
                    (),
                    {
                        "source_path": "b.md",
                        "title": "B",
                        "doc_type": "meeting",
                        "date": "2026-04-26",
                    },
                )(),
                "breadcrumbs": ["B"],
            },
        )(),
    ]
    embeddings = [[0.1] * 384, [0.2] * 384]
    store.add_chunks(chunks, embeddings)
    results = store.query(embedding=[0.1] * 384, filters={"doc_type": "meeting"}, n_results=10)
    assert len(results) == 1
    assert results[0]["id"] == "b#0"


def test_reingesting_source_removes_stale_chunks(store):
    old_chunks = [
        type(
            "Chunk",
            (),
            {
                "id": "a.md#0",
                "text": "old action item",
                "meta": type(
                    "obj",
                    (),
                    {
                        "source_path": "a.md",
                        "title": "A",
                        "doc_type": "note",
                        "date": "2026-04-26",
                        "tags": "",
                        "author": "",
                        "source": "",
                        "heading": "",
                        "chunk_index": 0,
                    },
                )(),
                "breadcrumbs": ["A"],
            },
        )(),
        type(
            "Chunk",
            (),
            {
                "id": "a.md#1",
                "text": "stale chunk",
                "meta": type(
                    "obj",
                    (),
                    {
                        "source_path": "a.md",
                        "title": "A",
                        "doc_type": "note",
                        "date": "2026-04-26",
                        "tags": "",
                        "author": "",
                        "source": "",
                        "heading": "",
                        "chunk_index": 1,
                    },
                )(),
                "breadcrumbs": ["A"],
            },
        )(),
    ]
    new_chunks = [
        type(
            "Chunk",
            (),
            {
                "id": "a.md#0",
                "text": "new action item",
                "meta": type(
                    "obj",
                    (),
                    {
                        "source_path": "a.md",
                        "title": "A",
                        "doc_type": "note",
                        "date": "2026-04-26",
                        "tags": "",
                        "author": "",
                        "source": "",
                        "heading": "",
                        "chunk_index": 0,
                    },
                )(),
                "breadcrumbs": ["A"],
            },
        )(),
    ]
    store.add_chunks(old_chunks, [[0.1] * 384, [0.2] * 384])
    store.replace_source_chunks("a.md", new_chunks, [[0.3] * 384])
    results = store.query(embedding=[0.3] * 384, n_results=10)
    assert store.count() == 1
    assert results[0]["id"] == "a.md#0"
    assert results[0]["text"] == "new action item"
