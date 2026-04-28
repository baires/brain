"""End-to-end integration tests: each provider driver wired through QueryEngine."""

import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import MagicMock

from brain.config import BrainConfig
from brain.providers import get_provider
from brain.providers.ollama import OllamaProvider
from brain.query import QueryEngine

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _fake_store(text: str = "The answer is 42.", distance: float = 0.1):
    store = MagicMock()
    store.query.return_value = [
        {
            "id": "doc#0",
            "text": text,
            "metadata": {"title": "Test Doc", "source_path": "test.md"},
            "distance": distance,
        }
    ]
    return store


# ---------------------------------------------------------------------------
# Ollama driver integration
# ---------------------------------------------------------------------------


def test_ollama_driver_retrieve_and_ask(monkeypatch):
    """OllamaProvider wired through QueryEngine: retrieve + ask return expected output."""
    import requests

    embed_resp = MagicMock()
    embed_resp.json.return_value = {"embedding": [0.5] * 384}
    embed_resp.raise_for_status = MagicMock()

    def fake_post(url, **kwargs):
        if "embeddings" in url:
            return embed_resp
        # chat
        import json

        lines = [
            json.dumps({"response": "The"}).encode(),
            json.dumps({"response": " answer"}).encode(),
            json.dumps({"response": " is 42."}).encode(),
            json.dumps({"done": True}).encode(),
        ]
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.iter_lines.return_value = lines
        return resp

    monkeypatch.setattr(requests, "post", fake_post)

    cfg = BrainConfig(provider="ollama", base_url="http://localhost:11434")
    provider = get_provider(cfg)
    assert isinstance(provider, OllamaProvider)

    engine = QueryEngine(
        store=_fake_store(),
        llm=provider,
        embed_model=cfg.embed_model,
        chat_model=cfg.chat_model,
    )

    results = engine.retrieve("what is the answer?")
    assert len(results) == 1
    assert results[0].text == "The answer is 42."

    answer = "".join(engine.ask("what is the answer?"))
    assert "answer" in answer.lower()


# ---------------------------------------------------------------------------
# LiteLLM driver integration
# ---------------------------------------------------------------------------


def _make_litellm_module(embed_vector=None, chat_tokens=None):
    mod = types.ModuleType("litellm")

    embed_item = MagicMock()
    embed_item.embedding = embed_vector or ([0.5] * 384)
    embed_resp = MagicMock()
    embed_resp.data = [embed_item]
    mod.embedding = MagicMock(return_value=embed_resp)

    tokens = chat_tokens or ["The", " answer", " is 42."]
    chunks = []
    for t in tokens:
        delta = MagicMock()
        delta.content = t
        choice = MagicMock()
        choice.delta = delta
        chunk = MagicMock()
        chunk.choices = [choice]
        chunks.append(chunk)
    done_delta = MagicMock()
    done_delta.content = None
    done_choice = MagicMock()
    done_choice.delta = done_delta
    done_chunk = MagicMock()
    done_chunk.choices = [done_choice]
    chunks.append(done_chunk)
    mod.completion = MagicMock(return_value=iter(chunks))

    return mod


def test_litellm_driver_retrieve_and_ask():
    """LiteLLMProvider wired through QueryEngine: retrieve + ask return expected output."""
    fake_litellm = _make_litellm_module()
    with __import__("unittest.mock", fromlist=["patch"]).patch.dict(
        sys.modules, {"litellm": fake_litellm}
    ):
        cfg = BrainConfig(provider="litellm", api_key="sk-test", chat_model="openai/gpt-4o")
        provider = get_provider(cfg)

        engine = QueryEngine(
            store=_fake_store(),
            llm=provider,
            embed_model="openai/text-embedding-3-small",
            chat_model=cfg.chat_model,
        )

        results = engine.retrieve("what is the answer?")
        assert len(results) == 1
        assert results[0].text == "The answer is 42."

        answer = "".join(engine.ask("what is the answer?"))
        assert "answer" in answer.lower()


def test_litellm_driver_ask_passes_system_prompt():
    """System prompt from BrainConfig is forwarded to LiteLLM chat call."""
    fake_litellm = _make_litellm_module()
    with __import__("unittest.mock", fromlist=["patch"]).patch.dict(
        sys.modules, {"litellm": fake_litellm}
    ):
        cfg = BrainConfig(provider="litellm", api_key="sk-test", chat_model="openai/gpt-4o")
        provider = get_provider(cfg)

        engine = QueryEngine(
            store=_fake_store(),
            llm=provider,
            embed_model="openai/text-embedding-3-small",
            chat_model=cfg.chat_model,
            system_prompt="be concise",
        )
        list(engine.ask("what is the answer?"))

    _, kwargs = fake_litellm.completion.call_args
    system_msgs = [m for m in kwargs["messages"] if m["role"] == "system"]
    assert system_msgs[0]["content"] == "be concise"


# ---------------------------------------------------------------------------
# OpenAI-compat driver integration
# ---------------------------------------------------------------------------


def _make_openai_module(embed_vector=None, chat_tokens=None):
    mod = types.ModuleType("openai")

    embed_item = MagicMock()
    embed_item.embedding = embed_vector or ([0.5] * 384)
    embed_resp = MagicMock()
    embed_resp.data = [embed_item]

    tokens = chat_tokens or ["The", " answer", " is 42."]
    chunks = []
    for t in tokens:
        delta = MagicMock()
        delta.content = t
        choice = MagicMock()
        choice.delta = delta
        chunk = MagicMock()
        chunk.choices = [choice]
        chunks.append(chunk)
    done_delta = MagicMock()
    done_delta.content = None
    done_choice = MagicMock()
    done_choice.delta = done_delta
    done_chunk = MagicMock()
    done_chunk.choices = [done_choice]
    chunks.append(done_chunk)

    client = MagicMock()
    client.embeddings.create.return_value = embed_resp
    client.chat.completions.create.return_value = iter(chunks)
    mod.OpenAI = MagicMock(return_value=client)
    mod._client = client
    return mod


def test_openai_compat_driver_retrieve_and_ask():
    """OpenAICompatProvider wired through QueryEngine: retrieve + ask return expected output."""
    fake_openai = _make_openai_module()
    with __import__("unittest.mock", fromlist=["patch"]).patch.dict(
        sys.modules, {"openai": fake_openai}
    ):
        cfg = BrainConfig(provider="openai_compat", api_key="sk-test", chat_model="gpt-4o")
        provider = get_provider(cfg)

        engine = QueryEngine(
            store=_fake_store(),
            llm=provider,
            embed_model="text-embedding-3-small",
            chat_model=cfg.chat_model,
        )

        results = engine.retrieve("what is the answer?")
        assert len(results) == 1
        assert results[0].text == "The answer is 42."

        answer = "".join(engine.ask("what is the answer?"))
        assert "answer" in answer.lower()


def test_openai_compat_driver_ask_passes_system_prompt():
    """System prompt is forwarded to OpenAI chat call."""
    fake_openai = _make_openai_module()
    with __import__("unittest.mock", fromlist=["patch"]).patch.dict(
        sys.modules, {"openai": fake_openai}
    ):
        cfg = BrainConfig(provider="openai_compat", api_key="sk-test", chat_model="gpt-4o")
        provider = get_provider(cfg)

        engine = QueryEngine(
            store=_fake_store(),
            llm=provider,
            embed_model="text-embedding-3-small",
            chat_model=cfg.chat_model,
            system_prompt="be concise",
        )
        list(engine.ask("what is the answer?"))

    _, kwargs = fake_openai._client.chat.completions.create.call_args
    system_msgs = [m for m in kwargs["messages"] if m["role"] == "system"]
    assert system_msgs[0]["content"] == "be concise"


# ---------------------------------------------------------------------------
# Provider config round-trip: load from TOML
# ---------------------------------------------------------------------------


def test_litellm_config_loads_from_toml():
    """BrainConfig correctly reads provider/api_key/base_url from a TOML file."""
    toml_content = (
        'provider = "litellm"\n'
        'api_key = "sk-openai-test"\n'
        'base_url = "https://api.openai.com/v1"\n'
        'chat_model = "openai/gpt-4o"\n'
        'embed_model = "openai/text-embedding-3-small"\n'
    )
    with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as f:
        f.write(toml_content)
        tmp_path = f.name

    cfg = BrainConfig.load_from(tmp_path)
    assert cfg.provider == "litellm"
    assert cfg.api_key == "sk-openai-test"
    assert cfg.base_url == "https://api.openai.com/v1"
    assert cfg.chat_model == "openai/gpt-4o"

    Path(tmp_path).unlink()


def test_ollama_default_config_unchanged():
    """Existing users with no provider field in TOML keep working as before."""
    toml_content = 'chat_model = "gemma4:e4b"\nembed_model = "nomic-embed-text"\n'
    with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as f:
        f.write(toml_content)
        tmp_path = f.name

    cfg = BrainConfig.load_from(tmp_path)
    assert cfg.provider == "ollama"
    assert cfg.api_key is None
    assert cfg.base_url is None

    Path(tmp_path).unlink()
