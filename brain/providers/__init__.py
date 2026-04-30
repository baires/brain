from brain.providers.base import LLMProvider, ProviderError
from brain.providers.ollama import OllamaProvider


def _build_provider(driver: str, api_key, base_url, ollama_url) -> LLMProvider:
    if driver == "ollama":
        return OllamaProvider(base_url=base_url or ollama_url)

    if driver == "litellm":
        from brain.providers.litellm import LiteLLMProvider

        return LiteLLMProvider(api_key=api_key, base_url=base_url)

    if driver == "openai_compat":
        from brain.providers.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(api_key=api_key, base_url=base_url)

    raise ProviderError(f"Unknown provider: {driver}")


def get_provider(config) -> LLMProvider:
    return _build_provider(
        config.provider.lower(),
        config.api_key,
        config.base_url,
        config.ollama_url,
    )


def get_embedder(config) -> LLMProvider:
    """Return the embedding provider, falling back to the main provider if no embed_provider is set."""
    if not config.embed_provider:
        return get_provider(config)
    return _build_provider(
        config.embed_provider.lower(),
        config.embed_api_key,
        config.embed_base_url,
        config.ollama_url,
    )


__all__ = ["get_provider", "get_embedder", "LLMProvider", "ProviderError"]
