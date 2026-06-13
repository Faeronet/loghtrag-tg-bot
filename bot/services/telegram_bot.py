from __future__ import annotations

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from config import settings


def create_bot(token: str) -> Bot:
    session_kwargs: dict = {"timeout": settings.telegram_request_timeout}
    if settings.telegram_proxy:
        session_kwargs["proxy"] = settings.telegram_proxy
    if settings.telegram_api_base:
        session_kwargs["api"] = TelegramAPIServer.from_base(
            settings.telegram_api_base.rstrip("/")
        )
    session = AiohttpSession(**session_kwargs)
    return Bot(
        token=token,
        session=session,
        default=DefaultBotProperties(parse_mode=None),
    )
