from unittest.mock import MagicMock

import pytest

from brain.commands.chat import ChatApp, _build_chat_prompt


def test_build_chat_prompt_with_context_and_history():
    history = [("User", "Hello"), ("Assistant", "Hi there")]
    prompt = _build_chat_prompt(
        user_message="What about the meeting?",
        context="[Meeting] Action items discussed",
        history=history,
    )
    assert "Context:" in prompt
    assert "[Meeting] Action items discussed" in prompt
    assert "Conversation:" in prompt
    assert "User: Hello" in prompt
    assert "Assistant: Hi there" in prompt
    assert "User: What about the meeting?" in prompt
    assert "Assistant:" in prompt


def test_chat_prompt_keeps_context_before_history():
    prompt = _build_chat_prompt(
        user_message="What did Bob do?",
        context='[1] title="Sales Meeting"\nBob sends proposal.',
        history=[("User", "Earlier"), ("Assistant", "Earlier answer")],
    )
    assert prompt.index("Context:") < prompt.index("Conversation:")
    assert "citation number and source file path" in prompt


def test_build_chat_prompt_no_context():
    prompt = _build_chat_prompt(
        user_message="Hello",
        context="",
        history=[],
    )
    assert "Context:" not in prompt
    assert "Conversation:" not in prompt
    assert "User: Hello" in prompt
    assert "Assistant:" in prompt


def test_build_chat_prompt_no_history():
    prompt = _build_chat_prompt(
        user_message="Hello",
        context="Some context",
        history=[],
    )
    assert "Context:" in prompt
    assert "Conversation:" not in prompt
    assert "User: Hello" in prompt


@pytest.mark.anyio
async def test_chat_app_welcome_message():
    """Smoke test: app composes and shows welcome message."""
    app = ChatApp()

    # Mock config-dependent objects to avoid real Ollama calls
    app.cfg = MagicMock()
    app.cfg.chat_model = "test-model"
    app.cfg.agent.tone = "testy"
    app.cfg.agent.goals = "test goals"
    app.cfg.agent.system_prompt = "You are a test."
    app.cfg.embed_model = "test-embed"
    app.cfg.ollama_url = "http://test"

    async with app.run_test() as _pilot:
        # Welcome message should be mounted
        chat_view = app.query_one("#chat-view")
        assert len(chat_view.children) > 0
