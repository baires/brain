from unittest.mock import MagicMock

from brain.query import QueryEngine, RetrievalResult


def test_query_rag_builds_prompt_and_streams():
    mock_store = MagicMock()
    mock_store.query.return_value = [
        {
            "id": "a#0",
            "text": "Action item: fix the bug.",
            "metadata": {"title": "Meeting"},
            "distance": 0.1,
        },
        {
            "id": "a#1",
            "text": "Action item: update docs.",
            "metadata": {"title": "Meeting"},
            "distance": 0.2,
        },
    ]

    mock_ollama = MagicMock()
    mock_ollama.embed.return_value = [0.1] * 384
    mock_ollama.chat.return_value = iter(["You", " should", " fix", " the", " bug", "."])

    engine = QueryEngine(
        store=mock_store,
        ollama=mock_ollama,
        embed_model="nomic-embed-text",
        chat_model="gemma4:e4b",
    )
    result = "".join(engine.ask("what are the action items?"))

    assert result == "You should fix the bug."
    mock_ollama.embed.assert_called_once_with(
        "what are the action items?", model="nomic-embed-text"
    )
    mock_store.query.assert_called_once()
    args, kwargs = mock_store.query.call_args
    assert kwargs["n_results"] == 40

    # Check the prompt passed to chat contains retrieved context
    chat_call = mock_ollama.chat.call_args
    prompt = chat_call.kwargs["prompt"]
    assert "Action item: fix the bug" in prompt
    assert "what are the action items?" in prompt


def test_context_formatting_includes_citations_and_metadata():
    engine = QueryEngine(
        store=MagicMock(), ollama=MagicMock(), embed_model="embed", chat_model="chat"
    )
    context = engine.build_context(
        [
            RetrievalResult(
                id="meeting.md#2",
                text="- Bob: send revised proposal",
                source_path="/notes/meeting.md",
                title="Sales Meeting",
                date="2026-04-26",
                doc_type="meeting",
                breadcrumbs=["Sales Meeting", "Action Items"],
                distance=0.12,
                citation=1,
            )
        ]
    )
    assert "[1]" in context
    assert 'title="Sales Meeting"' in context
    assert 'date="2026-04-26"' in context
    assert 'section="Sales Meeting > Action Items"' in context
    assert 'source="/notes/meeting.md#2"' in context
    assert "- Bob: send revised proposal" in context


def test_prompt_requires_file_path_citations():
    engine = QueryEngine(
        store=MagicMock(), ollama=MagicMock(), embed_model="embed", chat_model="chat"
    )
    prompt = engine.build_prompt(
        "What did Bob do?",
        '[1] title="Sales Meeting" source="notes-demo/meeting.md#2"\nBob sends proposal.',
    )
    assert "citation number and source file path" in prompt
    assert "[1: notes-demo/meeting.md]" in prompt
    assert 'Use the source="..." field' in prompt


def test_retrieval_drops_weak_results_and_answer_is_conservative():
    mock_store = MagicMock()
    mock_store.query.return_value = [
        {"id": "a#0", "text": "unrelated", "metadata": {"title": "A"}, "distance": 9.0},
    ]
    mock_ollama = MagicMock()
    mock_ollama.embed.return_value = [0.1] * 384
    engine = QueryEngine(
        store=mock_store,
        ollama=mock_ollama,
        embed_model="embed",
        chat_model="chat",
        max_best_distance=2.0,
    )
    assert engine.retrieve("question") == []
    assert "".join(engine.ask("question")) == "I don't know based on your notes."
    mock_ollama.chat.assert_not_called()


def test_retrieval_limits_near_duplicate_sources_with_mmr():
    mock_store = MagicMock()
    mock_store.query.return_value = [
        {
            "id": "a#0",
            "text": "first",
            "metadata": {"source_path": "a.md", "title": "A", "breadcrumbs": "A"},
            "distance": 0.10,
        },
        {
            "id": "a#1",
            "text": "duplicate",
            "metadata": {"source_path": "a.md", "title": "A", "breadcrumbs": "A"},
            "distance": 0.11,
        },
        {
            "id": "b#0",
            "text": "second source",
            "metadata": {"source_path": "b.md", "title": "B", "breadcrumbs": "B"},
            "distance": 0.12,
        },
    ]
    mock_ollama = MagicMock()
    mock_ollama.embed.return_value = [0.1] * 384
    engine = QueryEngine(
        store=mock_store,
        ollama=mock_ollama,
        embed_model="embed",
        chat_model="chat",
        top_k=2,
        max_best_distance=2.0,
        relative_distance_margin=10.0,
    )
    results = engine.retrieve("question")
    assert [r.id for r in results] == ["a#0", "b#0"]


def test_retrieval_keeps_lexically_relevant_action_item_outside_distance_margin():
    mock_store = MagicMock()
    mock_store.query.return_value = [
        {
            "id": "book#0",
            "text": "Pair an action you want with an action you need.",
            "metadata": {
                "source_path": "book.md",
                "title": "Book",
                "breadcrumbs": "Book > Habits",
                "heading": "Habits",
            },
            "distance": 303.0,
        },
        {
            "id": "sales#4",
            "text": "## Action Items\n\n- **Alice**: Loop in legal for custom data residency clause",
            "metadata": {
                "source_path": "sales.md",
                "title": "Sales Meeting with Acme Corp",
                "doc_type": "meeting",
                "breadcrumbs": "Sales Meeting with Acme Corp > Action Items",
                "heading": "Action Items",
            },
            "distance": 445.0,
        },
    ]
    mock_ollama = MagicMock()
    mock_ollama.embed.return_value = [0.1] * 384
    engine = QueryEngine(
        store=mock_store,
        ollama=mock_ollama,
        embed_model="embed",
        chat_model="chat",
        top_k=1,
        max_best_distance=500.0,
        relative_distance_margin=0.35,
    )
    results = engine.retrieve("What are Alice action items from last sales meeeting?")
    assert [r.id for r in results] == ["sales#4"]
