import sys
import types
from unittest.mock import MagicMock

import pytest

from brain.providers.base import ProviderError


def _make_fake_openai(embed_vector: list[float] | None = None, chat_tokens: list[str] | None = None):
    """Return a fake openai module with a configurable client."""
    mod = types.ModuleType("openai")

    # Fake embeddings response
    embed_item = MagicMock()
    embed_item.embedding = embed_vector or [0.1, 0.2, 0.3]
    embed_resp = MagicMock()
    embed_resp.data = [embed_item]

    # Fake streaming chat chunks
    def _make_chunk(content):
        delta = MagicMock()
        delta.content = content
        choice = MagicMock()
        choice.delta = delta
        chunk = MagicMock()
        chunk.choices = [choice]
        return chunk

    tokens = chat_tokens or ["Hi", " there"]
    chunks = [_make_chunk(t) for t in tokens] + [_make_chunk(None)]

    client_instance = MagicMock()
    client_instance.embeddings.create.return_value = embed_resp
    client_instance.chat.completions.create.return_value = iter(chunks)

    mod.OpenAI = MagicMock(return_value=client_instance)
    mod._client_instance = client_instance
    return mod


def test_embed_returns_vector():
    fake = _make_fake_openai(embed_vector=[0.1, 0.2, 0.3])
    with __import__("unittest.mock", fromlist=["patch"]).patch.dict(sys.modules, {"openai": fake}):
        from brain.providers.openai_compat import OpenAICompatProvider
        provider = OpenAICompatProvider(api_key="sk-test")
        result = provider.embed("hello", model="text-embedding-3-small")
    assert result == [0.1, 0.2, 0.3]


def test_embed_calls_client_with_model_and_text():
    fake = _make_fake_openai()
    with __import__("unittest.mock", fromlist=["patch"]).patch.dict(sys.modules, {"openai": fake}):
        from brain.providers.openai_compat import OpenAICompatProvider
        provider = OpenAICompatProvider(api_key="sk-test")
        provider.embed("hello world", model="text-embedding-3-small")
    fake._client_instance.embeddings.create.assert_called_once_with(
        model="text-embedding-3-small",
        input="hello world",
    )


def test_chat_yields_tokens():
    fake = _make_fake_openai(chat_tokens=["Hello", " world"])
    with __import__("unittest.mock", fromlist=["patch"]).patch.dict(sys.modules, {"openai": fake}):
        from brain.providers.openai_compat import OpenAICompatProvider
        provider = OpenAICompatProvider(api_key="sk-test")
        tokens = list(provider.chat("say hi", model="gpt-4o"))
    assert "".join(tokens) == "Hello world"


def test_chat_passes_stream_true():
    fake = _make_fake_openai()
    with __import__("unittest.mock", fromlist=["patch"]).patch.dict(sys.modules, {"openai": fake}):
        from brain.providers.openai_compat import OpenAICompatProvider
        provider = OpenAICompatProvider(api_key="sk-test")
        list(provider.chat("hi", model="gpt-4o"))
    _, kwargs = fake._client_instance.chat.completions.create.call_args
    assert kwargs["stream"] is True
    assert kwargs["model"] == "gpt-4o"


def test_chat_includes_user_message():
    fake = _make_fake_openai()
    with __import__("unittest.mock", fromlist=["patch"]).patch.dict(sys.modules, {"openai": fake}):
        from brain.providers.openai_compat import OpenAICompatProvider
        provider = OpenAICompatProvider(api_key="sk-test")
        list(provider.chat("what is X?", model="gpt-4o"))
    _, kwargs = fake._client_instance.chat.completions.create.call_args
    messages = kwargs["messages"]
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "what is X?"


def test_chat_includes_system_message():
    fake = _make_fake_openai()
    with __import__("unittest.mock", fromlist=["patch"]).patch.dict(sys.modules, {"openai": fake}):
        from brain.providers.openai_compat import OpenAICompatProvider
        provider = OpenAICompatProvider(api_key="sk-test")
        list(provider.chat("hi", model="gpt-4o", system="be terse"))
    _, kwargs = fake._client_instance.chat.completions.create.call_args
    messages = kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "be terse"


def test_client_constructed_with_api_key_and_base_url():
    fake = _make_fake_openai()
    with __import__("unittest.mock", fromlist=["patch"]).patch.dict(sys.modules, {"openai": fake}):
        from brain.providers.openai_compat import OpenAICompatProvider
        provider = OpenAICompatProvider(api_key="sk-test", base_url="https://openrouter.ai/api/v1")
        provider.embed("x", model="text-embedding-3-small")
    fake.OpenAI.assert_called_once_with(api_key="sk-test", base_url="https://openrouter.ai/api/v1")


def test_embed_wraps_exception_as_provider_error():
    fake = _make_fake_openai()
    fake._client_instance.embeddings.create.side_effect = Exception("invalid key")
    with __import__("unittest.mock", fromlist=["patch"]).patch.dict(sys.modules, {"openai": fake}):
        from brain.providers.openai_compat import OpenAICompatProvider
        provider = OpenAICompatProvider(api_key="sk-bad")
        with pytest.raises(ProviderError) as exc_info:
            provider.embed("hello", model="text-embedding-3-small")
    assert "invalid key" in str(exc_info.value)


def test_chat_wraps_exception_as_provider_error():
    fake = _make_fake_openai()
    fake._client_instance.chat.completions.create.side_effect = Exception("timeout")
    with __import__("unittest.mock", fromlist=["patch"]).patch.dict(sys.modules, {"openai": fake}):
        from brain.providers.openai_compat import OpenAICompatProvider
        provider = OpenAICompatProvider(api_key="sk-test")
        with pytest.raises(ProviderError) as exc_info:
            list(provider.chat("hi", model="gpt-4o"))
    assert "timeout" in str(exc_info.value)
