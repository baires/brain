from collections.abc import Generator

from brain.providers.base import ProviderError


class OpenAICompatProvider:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key
        self.base_url = base_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import openai
            except ImportError as e:
                raise ProviderError("OpenAI SDK is not installed. Run: pip install openai") from e
            self._client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def embed(self, text: str, model: str) -> list[float]:
        client = self._get_client()
        try:
            resp = client.embeddings.create(model=model, input=text)
            return resp.data[0].embedding
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(f"OpenAI embedding failed: {e}") from e

    def chat(
        self,
        prompt: str,
        model: str,
        system: str | None = None,
    ) -> Generator[str, None, None]:
        client = self._get_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            for chunk in client.chat.completions.create(
                model=model, messages=messages, stream=True
            ):
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(f"OpenAI completion failed: {e}") from e
