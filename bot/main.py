from __future__ import annotations

import asyncio
import logging
import sys

import httpx
from aiogram import Dispatcher
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import ErrorEvent
from aiogram.utils.token import TokenValidationError, validate_token

from config import settings
from db.repository import ChatRepository
from handlers.chat import router as chat_router
from middlewares.deps import LoggingMiddleware, MemoryMiddleware
from services.embedding import EmbeddingClient
from services.http_clients import HttpClients
from services.lightrag import LightRAGClient
from services.memory import MemoryService
from services.qdrant_store import QdrantMemoryStore
from services.telegram_bot import create_bot

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


async def _wait_for_bot_api() -> None:
    if not settings.telegram_api_base:
        return
    base = settings.telegram_api_base.rstrip("/")
    for attempt in range(1, 31):
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.get(base)
            logger.info("Telegram Bot API is up at %s", base)
            return
        except Exception:
            logger.info("Waiting for Telegram Bot API at %s (%s/30)...", base, attempt)
            await asyncio.sleep(2)
    logger.error(
        "Telegram Bot API at %s did not start. "
        "Check TELEGRAM_API_ID/TELEGRAM_API_HASH in .env and run: docker compose logs telegram-bot-api",
        base,
    )
    raise SystemExit(1)


async def _connect_telegram(token: str):
    bot = create_bot(token)
    for attempt in range(1, settings.telegram_connect_retries + 1):
        logger.info(
            "Connecting to Telegram (attempt %s/%s, timeout %ss)...",
            attempt,
            settings.telegram_connect_retries,
            settings.telegram_request_timeout,
        )
        try:
            me = await bot.get_me()
            logger.info("Authorized as @%s (id=%s)", me.username, me.id)
            return bot
        except TelegramNetworkError as exc:
            logger.warning("Telegram connect failed: %s", exc)
            if attempt < settings.telegram_connect_retries:
                logger.info(
                    "Retrying in %ss...",
                    settings.telegram_connect_retry_delay,
                )
                await asyncio.sleep(settings.telegram_connect_retry_delay)

    await bot.session.close()
    logger.error(
        "Cannot connect to Telegram.\n"
        "Local Bot API is up, but TDLib cannot reach Telegram servers.\n"
        "Set TELEGRAM_PROXY in .env (used by telegram-bot-api container), e.g.:\n"
        "  TELEGRAM_PROXY=socks5://host:port\n"
        "Then: docker compose up -d --force-recreate telegram-bot-api bot\n"
        "Check: docker compose logs telegram-bot-api"
    )
    raise SystemExit(1)


async def main() -> None:
    token = _require_telegram_token()
    await _wait_for_bot_api()
    bot = await _connect_telegram(token)

    http = HttpClients()
    repo = await ChatRepository.create()
    embedding = EmbeddingClient(http.embedding)
    qdrant = QdrantMemoryStore(embedding)
    await qdrant.connect()
    lightrag = LightRAGClient(http.lightrag)
    memory = MemoryService(repo, qdrant, lightrag)

    dp = Dispatcher()
    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(MemoryMiddleware(memory))
    dp.include_router(chat_router)

    @dp.errors()
    async def on_error(event: ErrorEvent) -> None:
        logger.exception("Unhandled error while processing update: %s", event.exception)

    webhook = await bot.get_webhook_info()
    if webhook.url:
        logger.warning("Webhook was set to %s — removing for polling mode", webhook.url)
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        logger.info(
            "Bot started (async, postgres pool %s-%s, http connections up to %s, qdrant=%s)",
            settings.postgres_pool_min,
            settings.postgres_pool_max,
            settings.http_max_connections,
            "on" if qdrant.enabled else "off",
        )
        await dp.start_polling(bot)
    finally:
        await repo.close()
        await qdrant.close()
        await http.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
