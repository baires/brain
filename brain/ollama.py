import json
from collections.abc import Generator

import requests


class OllamaError(Exception):
    pass


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")

    def embed(self, text: str, model: str) -> list[float]:
        url = f"{self.base_url}/api/embeddings"
        payload = {"model": model, "prompt": text}
        try:
            resp = requests.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("embedding", [])
        except requests.exceptions.ConnectionError as e:
            raise OllamaError(
                f"Ollama not reachable at {self.base_url}. Start it with: ollama serve"
            ) from e
        except requests.exceptions.RequestException as e:
            raise OllamaError(f"Ollama request failed: {e}") from e

    def chat(
        self,
        prompt: str,
        model: str,
        system: str | None = None,
    ) -> Generator[str, None, None]:
        url = f"{self.base_url}/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": True}
        if system:
            payload["system"] = system
        try:
            resp = requests.post(url, json=payload, stream=True)
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("done"):
                    break
                if "response" in data:
                    yield data["response"]
        except requests.exceptions.ConnectionError as e:
            raise OllamaError(
                f"Ollama not reachable at {self.base_url}. Start it with: ollama serve"
            ) from e
        except requests.exceptions.RequestException as e:
            raise OllamaError(f"Ollama request failed: {e}") from e
