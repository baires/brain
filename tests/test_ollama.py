import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from brain.providers.base import ProviderError as OllamaError
from brain.providers.ollama import OllamaProvider as OllamaClient


def test_embed_returns_vector():
    mock_response = MagicMock()
    mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
    mock_response.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_response) as mock_post:
        client = OllamaClient(base_url="http://localhost:11434")
        result = client.embed("hello", model="nomic-embed-text")
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
        client = OllamaClient(base_url="http://localhost:11434")
        tokens = list(client.chat("say hi", model="gemma4:e4b"))
        assert "".join(tokens) == "Hello world"


def test_connection_error_raises_ollama_error():
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("refused")):
        client = OllamaClient(base_url="http://localhost:11434")
        with pytest.raises(OllamaError) as exc_info:
            client.embed("hello", model="nomic-embed-text")
        assert "not reachable" in str(exc_info.value)
