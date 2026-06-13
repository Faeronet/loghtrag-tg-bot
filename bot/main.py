from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.token import TokenValidationError, validate_token

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

_PLACEHOLDER_TOKENS = {
    "",
    "your_telegram_bot_token",
    "changeme",
}


def _require_telegram_token() -> str:
    token = settings.telegram_bot_token
    if token.lower() in _PLACEHOLDER_TOKENS:
        logger.error(
            "TELEGRAM_BOT_TOKEN is not set. "
            "Create a bot via @BotFather and add to .env:\n"
            "  TELEGRAM_BOT_TOKEN=123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        )
        raise SystemExit(1)
    try:
        validate_token(token)
    except TokenValidationError:
        logger.error(
            "TELEGRAM_BOT_TOKEN has invalid format. "
            "It must look like 123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx "
            "(no quotes, no spaces)."
        )
        raise SystemExit(1)
    return token


async def main() -> None:
    token = _require_telegram_token()

    http = HttpClients()
    repo = await ChatRepository.create()
    embedding = EmbeddingClient(http.embedding)
    qdrant = QdrantMemoryStore(embedding)
    await qdrant.connect()
    lightrag = LightRAGClient(http.lightrag)
    memory = MemoryService(repo, qdrant, lightrag)

    bot = Bot(
        token=token,
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
