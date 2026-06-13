from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from services.memory import MemoryService

logger = logging.getLogger(__name__)


class MemoryMiddleware(BaseMiddleware):
    def __init__(self, memory: MemoryService) -> None:
        self._memory = memory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["memory"] = self._memory
        return await handler(event, data)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            logger.info(
                "Incoming message chat_id=%s user_id=%s text=%r",
                event.chat.id if event.chat else None,
                event.from_user.id if event.from_user else None,
                event.text,
            )
        return await handler(event, data)
