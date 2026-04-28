import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from brain.providers.base import ProviderError
from brain.providers.ollama import OllamaProvider


def test_embed_returns_vector():
    mock_response = MagicMock()
    mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
    mock_response.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_response) as mock_post:
        provider = OllamaProvider(base_url="http://localhost:11434")
        result = provider.embed("hello", model="nomic-embed-text")
        assert result == [0.1, 0.2, 0.3]
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "http://localhost:11434/api/embeddings"
        assert kwargs["json"]["model"] == "nomic-embed-text"
        assert kwargs["json"]["prompt"] == "hello"


def test_chat_streams_tokens():
    def mock_iter_lines():
        yield json.dumps({"response": "Hello"})
        yield json.dumps({"response": " world"})
        yield json.dumps({"done": True})

    mock_response = MagicMock()
    mock_response.iter_lines.return_value = mock_iter_lines()
    mock_response.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_response):
        provider = OllamaProvider(base_url="http://localhost:11434")
        tokens = list(provider.chat("say hi", model="gemma4:e4b"))
        assert "".join(tokens) == "Hello world"


def test_connection_error_raises_provider_error():
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("refused")):
        provider = OllamaProvider(base_url="http://localhost:11434")
        with pytest.raises(ProviderError) as exc_info:
            provider.embed("hello", model="nomic-embed-text")
        assert "not reachable" in str(exc_info.value)


def test_chat_connection_error_raises_provider_error():
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("refused")):
        provider = OllamaProvider(base_url="http://localhost:11434")
        with pytest.raises(ProviderError) as exc_info:
            list(provider.chat("hi", model="gemma4:e4b"))
        assert "not reachable" in str(exc_info.value)


def test_request_error_raises_provider_error():
    with patch("requests.post", side_effect=requests.exceptions.RequestException("timeout")):
        provider = OllamaProvider(base_url="http://localhost:11434")
        with pytest.raises(ProviderError) as exc_info:
            provider.embed("hello", model="nomic-embed-text")
        assert "request failed" in str(exc_info.value)


def test_chat_with_system_prompt():
    def mock_iter_lines():
        yield json.dumps({"response": "ok"})
        yield json.dumps({"done": True})

    mock_response = MagicMock()
    mock_response.iter_lines.return_value = mock_iter_lines()
    mock_response.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_response) as mock_post:
        provider = OllamaProvider(base_url="http://localhost:11434")
        list(provider.chat("hello", model="gemma4:e4b", system="be brief"))
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["system"] == "be brief"


def test_provider_error_is_subclass_of_provider_error_base():
    """OllamaProvider raises ProviderError, not a custom OllamaError."""
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("x")):
        provider = OllamaProvider()
        with pytest.raises(ProviderError):
            provider.embed("x", model="m")


def test_default_base_url():
    provider = OllamaProvider()
    assert provider.base_url == "http://localhost:11434"
