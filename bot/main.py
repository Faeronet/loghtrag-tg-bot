from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from config import settings
from db.repository import ChatRepository
from handlers.chat import router as chat_router
from services.embedding import EmbeddingClient
from services.http_clients import HttpClients
from services.lightrag import LightRAGClient
from services.memory import MemoryService
from services.qdrant_store import QdrantMemoryStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    http = HttpClients()
    repo = await ChatRepository.create()
    embedding = EmbeddingClient(http.embedding)
    qdrant = QdrantMemoryStore(embedding)
    await qdrant.connect()
    lightrag = LightRAGClient(http.lightrag)
    memory = MemoryService(repo, qdrant, lightrag)

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )
    dp = Dispatcher()
    dp.include_router(chat_router)
    dp["memory"] = memory

    try:
        logger.info(
            "Bot started (async, postgres pool %s-%s, http connections up to %s, qdrant=%s)",
            settings.postgres_pool_min,
            settings.postgres_pool_max,
            settings.http_max_connections,
            "on" if qdrant.enabled else "off",
        )
        await dp.start_polling(bot, memory=memory)
    finally:
        await repo.close()
        await qdrant.close()
        await http.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
