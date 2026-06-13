from __future__ import annotations

import httpx

from config import settings


class LightRAGClient:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._client = http_client
        self._base = settings.lightrag_url.rstrip("/")
        self._api_key = settings.lightrag_api_key

    async def query(
        self,
        query: str,
        *,
        user_prompt: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        payload: dict = {
            "query": query,
            "mode": settings.lightrag_query_mode,
            "user_prompt": user_prompt,
            "include_references": False,
            "stream": False,
        }
        if conversation_history:
            payload["conversation_history"] = conversation_history

        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self._api_key,
        }

        response = await self._client.post(
            f"{self._base}/query",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

        answer = data.get("response")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Empty response from LightRAG")
        return answer.strip()
