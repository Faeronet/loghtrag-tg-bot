from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from config import settings
from db.repository import ChatRepository
from handlers.chat import router as chat_router
from services.embedding import EmbeddingClient
from services.lightrag import LightRAGClient
from services.memory import MemoryService
from services.qdrant_store import QdrantMemoryStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    repo = await ChatRepository.create()
    embedding = EmbeddingClient()
    qdrant = QdrantMemoryStore(embedding)
    await qdrant.ensure_collection()
    lightrag = LightRAGClient()
    memory = MemoryService(repo, qdrant, lightrag)

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )
    dp = Dispatcher()
    dp.include_router(chat_router)
    dp["memory"] = memory

    try:
        logger.info("Bot started")
        await dp.start_polling(bot, memory=memory)
    finally:
        await repo.close()
        await qdrant.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
