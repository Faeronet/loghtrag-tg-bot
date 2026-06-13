from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from config import settings

logger = logging.getLogger(__name__)


def create_bot(token: str) -> Bot:
    timeout = settings.telegram_request_timeout
    if settings.telegram_api_base:
        # Local Bot API + TDLib may need more time on first connect.
        timeout = max(timeout, 60.0)

    session_kwargs: dict = {"timeout": timeout}
    if settings.telegram_proxy:
        session_kwargs["proxy"] = settings.telegram_proxy
    if settings.telegram_api_base:
        base = settings.telegram_api_base.rstrip("/")
        session_kwargs["api"] = TelegramAPIServer.from_base(
            base,
            is_local=settings.telegram_api_local,
        )
        logger.info("Using local Telegram Bot API at %s", base)
    elif settings.telegram_proxy:
        logger.info("Using Telegram API via proxy %s", settings.telegram_proxy)
    else:
        logger.info("Using Telegram API at api.telegram.org (direct)")

    session = AiohttpSession(**session_kwargs)
    return Bot(
        token=token,
        session=session,
        default=DefaultBotProperties(parse_mode=None),
    )
