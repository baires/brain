from brain.config import BrainConfig


def test_default_provider_is_ollama():
    cfg = BrainConfig()
    assert cfg.provider == "ollama"


def test_default_api_key_is_none():
    cfg = BrainConfig()
    assert cfg.api_key is None


def test_default_base_url_is_none():
    cfg = BrainConfig()
    assert cfg.base_url is None


def test_provider_can_be_set():
    cfg = BrainConfig(provider="litellm", api_key="sk-abc", base_url="https://api.example.com")
    assert cfg.provider == "litellm"
    assert cfg.api_key == "sk-abc"
    assert cfg.base_url == "https://api.example.com"


def test_ollama_url_alias_migrates_to_base_url():
    """Setting ollama_url promotes it into base_url for backward compatibility."""
    cfg = BrainConfig(ollama_url="http://myhost:11434")
    assert cfg.ollama_url == "http://myhost:11434"
    assert cfg.base_url == "http://myhost:11434"


def test_default_ollama_url_does_not_override_base_url():
    """Default ollama_url must not clobber an explicitly unset base_url."""
    cfg = BrainConfig()
    assert cfg.base_url is None
