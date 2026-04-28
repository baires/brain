from brain.providers.base import LLMProvider, ProviderError
from brain.providers.ollama import OllamaProvider


def get_provider(config) -> LLMProvider:
    """Return the configured provider instance."""
    driver = config.provider.lower()

    if driver == "ollama":
        return OllamaProvider(base_url=config.ollama_url)

    if driver == "litellm":
        try:
            from brain.providers.litellm import LiteLLMProvider
        except ImportError as e:
            raise ProviderError(
                "LiteLLM is not installed. Run: pip install litellm"
            ) from e
        return LiteLLMProvider(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    if driver == "openai_compat":
        try:
            from brain.providers.openai_compat import OpenAICompatProvider
        except ImportError as e:
            raise ProviderError(
                "OpenAI SDK is not installed. Run: pip install openai"
            ) from e
        return OpenAICompatProvider(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    raise ProviderError(f"Unknown provider: {config.provider}")


__all__ = ["get_provider", "LLMProvider", "ProviderError"]
