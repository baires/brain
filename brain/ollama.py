# DEPRECATED: use brain.providers.ollama instead. Will be removed in a future release.
from brain.providers.base import ProviderError as OllamaError
from brain.providers.ollama import OllamaProvider as OllamaClient

__all__ = ["OllamaClient", "OllamaError"]
