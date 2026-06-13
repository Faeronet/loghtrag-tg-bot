from __future__ import annotations

import httpx

from config import settings


class HttpClients:
    """Shared async HTTP clients with connection pooling for concurrent requests."""

    def __init__(self) -> None:
        limits = httpx.Limits(
            max_connections=settings.http_max_connections,
            max_keepalive_connections=settings.http_max_keepalive,
        )
        self.lightrag = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.lightrag_timeout),
            limits=limits,
        )
        self.embedding = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=limits,
        )

    async def close(self) -> None:
        await self.lightrag.aclose()
        await self.embedding.aclose()
