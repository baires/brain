import pytest

from brain.config import BrainConfig
from brain.providers import get_provider
from brain.providers.base import ProviderError
from brain.providers.ollama import OllamaProvider


def test_default_config_returns_ollama_provider():
    cfg = BrainConfig()
    provider = get_provider(cfg)
    assert isinstance(provider, OllamaProvider)


def test_ollama_provider_uses_ollama_url():
    cfg = BrainConfig(ollama_url="http://myhost:11434")
    provider = get_provider(cfg)
    assert isinstance(provider, OllamaProvider)
    assert provider.base_url == "http://myhost:11434"


def test_unknown_provider_raises_provider_error():
    cfg = BrainConfig(provider="nonexistent")
    with pytest.raises(ProviderError) as exc_info:
        get_provider(cfg)
    assert "Unknown provider" in str(exc_info.value)
    assert "nonexistent" in str(exc_info.value)


def test_litellm_without_dep_raises_provider_error_on_use(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "litellm", None)
    cfg = BrainConfig(provider="litellm")
    provider = get_provider(cfg)
    with pytest.raises(ProviderError) as exc_info:
        provider.embed("test", model="openai/text-embedding-3-small")
    assert "litellm" in str(exc_info.value).lower()


def test_openai_compat_without_dep_raises_provider_error_on_use(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "openai", None)
    cfg = BrainConfig(provider="openai_compat")
    provider = get_provider(cfg)
    with pytest.raises(ProviderError) as exc_info:
        provider.embed("test", model="text-embedding-3-small")
    assert "openai" in str(exc_info.value).lower()
