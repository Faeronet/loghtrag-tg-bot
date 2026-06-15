from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from errors import user_facing_error
from services.memory import MemoryService

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    logger.info("Handling /start for chat_id=%s", message.chat.id if message.chat else None)
    await message.answer(
        "Привет! Задавай вопросы — я отвечу на основе базы знаний LightRAG.\n"
        "Команды:\n"
        "/reset — очистить память этого чата"
    )


@router.message(Command("reset"))
async def cmd_reset(message: Message, memory: MemoryService) -> None:
    if message.chat is None:
        return
    await memory.reset_chat(message.chat.id)
    await message.answer("Память чата очищена.")


@router.message(F.text)
async def handle_text(message: Message, bot: Bot, memory: MemoryService) -> None:
    if message.chat is None or not message.text:
        return

    chat_id = message.chat.id
    user_text = message.text.strip()
    if not user_text:
        return

    logger.info("Processing question for chat_id=%s", chat_id)
    waiting = await message.answer("...")

    try:
        answer = await memory.ask(chat_id, user_text)
        await waiting.edit_text(answer)
    except Exception as exc:
        logger.exception("Failed to process message for chat %s", chat_id)
        error_text = user_facing_error(exc)
        try:
            await waiting.edit_text(error_text)
        except Exception:
            await message.answer(error_text)
