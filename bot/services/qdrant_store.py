from __future__ import annotations

import asyncio
import logging
import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from config import settings
from services.embedding import EmbeddingClient

logger = logging.getLogger(__name__)
VECTOR_SIZE = 1024


class QdrantMemoryStore:
    def __init__(self, embedding: EmbeddingClient) -> None:
        self._embedding = embedding
        self._enabled = False
        client_kwargs: dict = {"url": settings.qdrant_url.rstrip("/")}
        if settings.qdrant_api_key:
            client_kwargs["api_key"] = settings.qdrant_api_key
        self._client = AsyncQdrantClient(**client_kwargs)
        self._collection = settings.qdrant_collection

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def connect(self) -> bool:
        for attempt in range(1, settings.qdrant_connect_retries + 1):
            try:
                await self._ensure_collection()
                self._enabled = True
                logger.info("Qdrant connected: %s", settings.qdrant_url)
                return True
            except Exception as exc:
                logger.warning(
                    "Qdrant connect attempt %s/%s failed (%s): %s",
                    attempt,
                    settings.qdrant_connect_retries,
                    settings.qdrant_url,
                    exc,
                )
                if attempt < settings.qdrant_connect_retries:
                    await asyncio.sleep(settings.qdrant_connect_retry_delay)

        logger.warning(
            "Qdrant unavailable — long-term memory disabled, bot continues with PostgreSQL only"
        )
        self._enabled = False
        return False

    async def _ensure_collection(self) -> None:
        exists = await self._client.collection_exists(self._collection)
        if exists:
            return
        await self._client.create_collection(
            collection_name=self._collection,
            vectors_config=qmodels.VectorParams(
                size=VECTOR_SIZE,
                distance=qmodels.Distance.COSINE,
            ),
        )

    async def store_turn(self, chat_id: int, user_text: str, assistant_text: str) -> None:
        if not self._enabled:
            return
        text = f"User: {user_text}\nAssistant: {assistant_text}"
        vector = await self._embedding.embed(text)
        point_id = str(uuid.uuid4())
        await self._client.upsert(
            collection_name=self._collection,
            points=[
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "chat_id": chat_id,
                        "text": text,
                        "user": user_text,
                        "assistant": assistant_text,
                    },
                )
            ],
        )

    async def search_relevant(self, chat_id: int, query: str, limit: int) -> list[str]:
        if not self._enabled or limit <= 0:
            return []
        vector = await self._embedding.embed(query)
        results = await self._client.search(
            collection_name=self._collection,
            query_vector=vector,
            query_filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="chat_id",
                        match=qmodels.MatchValue(value=chat_id),
                    )
                ]
            ),
            limit=limit,
            score_threshold=settings.memory_score_threshold,
        )
        return [hit.payload["text"] for hit in results if hit.payload]

    async def delete_chat(self, chat_id: int) -> None:
        if not self._enabled:
            return
        await self._client.delete(
            collection_name=self._collection,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="chat_id",
                            match=qmodels.MatchValue(value=chat_id),
                        )
                    ]
                )
            ),
        )

    async def close(self) -> None:
        await self._client.close()
