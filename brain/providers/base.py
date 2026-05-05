import abc
from collections.abc import Generator


class EmbeddingProvider(abc.ABC):
    @abc.abstractmethod
    def embed(self, text: str, model: str) -> list[float]:
        pass


class LLMProvider(abc.ABC):
    @abc.abstractmethod
    def chat(
        self, prompt: str, model: str, system: str | None = None
    ) -> Generator[str, None, None]:
        pass


class RerankerProvider(abc.ABC):
    @abc.abstractmethod
    def rerank(self, query: str, texts: list[str], top_n: int | None = None) -> list[dict]:
        pass


class TokenizerProvider(abc.ABC):
    @abc.abstractmethod
    def count_tokens(self, text: str) -> int:
        pass


class ProviderError(Exception):
    """Unified exception raised by all providers."""
