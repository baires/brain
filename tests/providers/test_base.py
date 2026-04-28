from collections.abc import Generator

from brain.providers.base import LLMProvider, ProviderError


def test_provider_error_is_exception():
    err = ProviderError("something went wrong")
    assert isinstance(err, Exception)
    assert str(err) == "something went wrong"


def test_llm_provider_protocol_embed():
    class MyProvider:
        def embed(self, text: str, model: str) -> list[float]:
            return [1.0, 2.0]

        def chat(
            self, prompt: str, model: str, system: str | None = None
        ) -> Generator[str, None, None]:
            yield "hi"

    provider: LLMProvider = MyProvider()
    assert provider.embed("test", "model") == [1.0, 2.0]


def test_llm_provider_protocol_chat():
    class MyProvider:
        def embed(self, text: str, model: str) -> list[float]:
            return []

        def chat(
            self, prompt: str, model: str, system: str | None = None
        ) -> Generator[str, None, None]:
            yield "hello"
            yield " world"

    provider: LLMProvider = MyProvider()
    tokens = list(provider.chat("hi", "model"))
    assert tokens == ["hello", " world"]


def test_llm_provider_protocol_chat_accepts_system():
    class MyProvider:
        def embed(self, text: str, model: str) -> list[float]:
            return []

        def chat(
            self, prompt: str, model: str, system: str | None = None
        ) -> Generator[str, None, None]:
            if system:
                yield f"[sys={system}]"
            yield prompt

    provider: LLMProvider = MyProvider()
    tokens = list(provider.chat("hi", "model", system="be concise"))
    assert tokens[0] == "[sys=be concise]"
