from collections.abc import Generator

from brain.providers.base import ProviderError


class LiteLLMProvider:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key
        self.base_url = base_url

    def _litellm(self):
        try:
            import litellm as _litellm

            return _litellm
        except ImportError as e:
            raise ProviderError("LiteLLM is not installed. Run: pip install litellm") from e

    def embed(self, text: str, model: str) -> list[float]:
        litellm = self._litellm()
        kwargs: dict = {"model": model, "input": [text]}
        if self.api_key is not None:
            kwargs["api_key"] = self.api_key
        if self.base_url is not None:
            kwargs["api_base"] = self.base_url
        try:
            resp = litellm.embedding(**kwargs)
            return resp.data[0].embedding
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(f"LiteLLM embedding failed: {e}") from e

    def chat(
        self,
        prompt: str,
        model: str,
        system: str | None = None,
    ) -> Generator[str, None, None]:
        litellm = self._litellm()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {"model": model, "messages": messages, "stream": True}
        if self.api_key is not None:
            kwargs["api_key"] = self.api_key
        if self.base_url is not None:
            kwargs["api_base"] = self.base_url
        try:
            for chunk in litellm.completion(**kwargs):
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(f"LiteLLM completion failed: {e}") from e
