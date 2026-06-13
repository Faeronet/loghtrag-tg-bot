from __future__ import annotations

import httpx

from config import settings


class EmbeddingClient:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client
        self._base = settings.embedding_url.rstrip("/")
        self._model = settings.embedding_model

    async def embed(self, text: str) -> list[float]:
        payload = {"input": text, "model": self._model}
        response = await self._client.post(
            f"{self._base}/v1/embeddings",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]
