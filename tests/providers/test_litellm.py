import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from brain.providers.base import ProviderError


def _make_fake_litellm():
    """Return a minimal fake litellm module for patching."""
    mod = types.ModuleType("litellm")
    mod.embedding = MagicMock()
    mod.completion = MagicMock()
    return mod


def _make_embed_response(vector: list[float]):
    item = MagicMock()
    item.embedding = vector
    resp = MagicMock()
    resp.data = [item]
    return resp


def _make_chunk(content: str):
    delta = MagicMock()
    delta.content = content
    choice = MagicMock()
    choice.delta = delta
    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


def _make_done_chunk():
    delta = MagicMock()
    delta.content = None
    choice = MagicMock()
    choice.delta = delta
    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


def test_embed_returns_vector():
    fake = _make_fake_litellm()
    fake.embedding.return_value = _make_embed_response([0.1, 0.2, 0.3])
    with patch.dict(sys.modules, {"litellm": fake}):
        from brain.providers.litellm import LiteLLMProvider
        provider = LiteLLMProvider(api_key="sk-test")
        result = provider.embed("hello", model="openai/text-embedding-3-small")
    assert result == [0.1, 0.2, 0.3]


def test_embed_passes_api_key_and_model():
    fake = _make_fake_litellm()
    fake.embedding.return_value = _make_embed_response([0.0])
    with patch.dict(sys.modules, {"litellm": fake}):
        from brain.providers.litellm import LiteLLMProvider
        provider = LiteLLMProvider(api_key="sk-test")
        provider.embed("hello", model="openai/text-embedding-3-small")
    _, kwargs = fake.embedding.call_args
    assert kwargs["model"] == "openai/text-embedding-3-small"
    assert kwargs["input"] == ["hello"]
    assert kwargs["api_key"] == "sk-test"


def test_embed_passes_base_url_when_set():
    fake = _make_fake_litellm()
    fake.embedding.return_value = _make_embed_response([0.0])
    with patch.dict(sys.modules, {"litellm": fake}):
        from brain.providers.litellm import LiteLLMProvider
        provider = LiteLLMProvider(api_key="sk-test", base_url="https://openrouter.ai/api/v1")
        provider.embed("hello", model="openrouter/openai/text-embedding-3-small")
    _, kwargs = fake.embedding.call_args
    assert kwargs["api_base"] == "https://openrouter.ai/api/v1"


def test_chat_yields_tokens():
    fake = _make_fake_litellm()
    chunks = [_make_chunk("Hello"), _make_chunk(" world"), _make_done_chunk()]
    fake.completion.return_value = iter(chunks)
    with patch.dict(sys.modules, {"litellm": fake}):
        from brain.providers.litellm import LiteLLMProvider
        provider = LiteLLMProvider(api_key="sk-test")
        tokens = list(provider.chat("say hi", model="openai/gpt-4o"))
    assert "".join(tokens) == "Hello world"


def test_chat_passes_prompt_model_and_stream():
    fake = _make_fake_litellm()
    fake.completion.return_value = iter([_make_done_chunk()])
    with patch.dict(sys.modules, {"litellm": fake}):
        from brain.providers.litellm import LiteLLMProvider
        provider = LiteLLMProvider(api_key="sk-test")
        list(provider.chat("say hi", model="openai/gpt-4o"))
    _, kwargs = fake.completion.call_args
    assert kwargs["model"] == "openai/gpt-4o"
    assert kwargs["stream"] is True
    assert kwargs["messages"][0]["role"] == "user"
    assert kwargs["messages"][0]["content"] == "say hi"


def test_chat_includes_system_message():
    fake = _make_fake_litellm()
    fake.completion.return_value = iter([_make_done_chunk()])
    with patch.dict(sys.modules, {"litellm": fake}):
        from brain.providers.litellm import LiteLLMProvider
        provider = LiteLLMProvider(api_key="sk-test")
        list(provider.chat("hi", model="openai/gpt-4o", system="be brief"))
    _, kwargs = fake.completion.call_args
    messages = kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "be brief"
    assert messages[1]["role"] == "user"


def test_chat_passes_base_url_when_set():
    fake = _make_fake_litellm()
    fake.completion.return_value = iter([_make_done_chunk()])
    with patch.dict(sys.modules, {"litellm": fake}):
        from brain.providers.litellm import LiteLLMProvider
        provider = LiteLLMProvider(api_key="sk-or-test", base_url="https://openrouter.ai/api/v1")
        list(provider.chat("hi", model="openrouter/anthropic/claude-sonnet-4"))
    _, kwargs = fake.completion.call_args
    assert kwargs["api_base"] == "https://openrouter.ai/api/v1"


def test_embed_wraps_exception_as_provider_error():
    fake = _make_fake_litellm()
    fake.embedding.side_effect = Exception("auth failed")
    with patch.dict(sys.modules, {"litellm": fake}):
        from brain.providers.litellm import LiteLLMProvider
        provider = LiteLLMProvider(api_key="sk-test")
        with pytest.raises(ProviderError) as exc_info:
            provider.embed("hello", model="openai/text-embedding-3-small")
    assert "auth failed" in str(exc_info.value)


def test_chat_wraps_exception_as_provider_error():
    fake = _make_fake_litellm()
    fake.completion.side_effect = Exception("rate limit")
    with patch.dict(sys.modules, {"litellm": fake}):
        from brain.providers.litellm import LiteLLMProvider
        provider = LiteLLMProvider(api_key="sk-test")
        with pytest.raises(ProviderError) as exc_info:
            list(provider.chat("hi", model="openai/gpt-4o"))
    assert "rate limit" in str(exc_info.value)


def test_no_api_key_not_passed_to_litellm():
    fake = _make_fake_litellm()
    fake.embedding.return_value = _make_embed_response([0.0])
    with patch.dict(sys.modules, {"litellm": fake}):
        from brain.providers.litellm import LiteLLMProvider
        provider = LiteLLMProvider()
        provider.embed("hello", model="ollama/llama3.1")
    _, kwargs = fake.embedding.call_args
    assert "api_key" not in kwargs
