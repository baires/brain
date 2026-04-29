"""Tests verifying QueryEngine accepts `llm` parameter (renamed from `ollama`)."""

from unittest.mock import MagicMock

from brain.query import QueryEngine


def test_query_engine_accepts_llm_parameter():
    mock_llm = MagicMock()
    mock_llm.embed.return_value = [0.1] * 384
    mock_llm.chat.return_value = iter(["answer"])
    mock_store = MagicMock()
    mock_store.query.return_value = [
        {"id": "x#0", "text": "Some context.", "metadata": {"title": "T"}, "distance": 0.1}
    ]

    engine = QueryEngine(
        store=mock_store,
        llm=mock_llm,
        embedder=mock_llm,
        embed_model="nomic-embed-text",
        chat_model="gemma4:e4b",
    )
    result = "".join(engine.ask("question?"))
    assert result == "answer"
    mock_llm.embed.assert_called_once()
    mock_llm.chat.assert_called_once()


def test_query_engine_llm_stored_as_llm_attribute():
    mock_llm = MagicMock()
    engine = QueryEngine(
        store=MagicMock(),
        llm=mock_llm,
        embedder=mock_llm,
        embed_model="e",
        chat_model="c",
    )
    assert engine.llm is mock_llm
