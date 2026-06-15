from __future__ import annotations

import re

from aiogram.types import Message

# Лимит Telegram Bot API на одно сообщение.
TELEGRAM_MAX_MESSAGE_LENGTH = 4096

# Конец предложения: знак препинания, опционально закрывающая кавычка/скобка, пробел или конец.
_SENTENCE_END = re.compile(r'[.!?…][)\]"»\'’]*(?:\s+|$)')


def split_telegram_text(text: str, max_len: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> list[str]:
    """Разбивает текст на части ≤ max_len, стараясь не рвать слова и абзацы."""
    text = text or ""
    if len(text) <= max_len:
        return [text] if text else [""]

    parts: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_len:
            parts.append(remaining)
            break

        window = remaining[:max_len]
        split_at = _find_split_index(window)

        if split_at <= 0:
            # Одно «слово» длиннее лимита — единственный вариант жёсткий разрез.
            split_at = max_len

        chunk = remaining[:split_at].rstrip()
        if not chunk:
            chunk = remaining[:max_len]
            split_at = max_len

        parts.append(chunk)
        remaining = remaining[split_at:].lstrip("\n").lstrip()

    return parts


def _find_split_index(window: str) -> int:
    """Индекс разреза в window: абзац → предложение → строка → слово."""
    # Абзац: режем после последнего полного абзаца в окне.
    para = window.rfind("\n\n")
    if para > 0:
        return para

    # Предложение: последний завершённый конец предложения в окне.
    sentence_end = 0
    for match in _SENTENCE_END.finditer(window):
        sentence_end = match.end()
    if sentence_end > 0:
        return sentence_end

    # Строка.
    line = window.rfind("\n")
    if line > 0:
        return line + 1

    # Слово.
    space = window.rfind(" ")
    if space > 0:
        return space + 1

    return 0


async def send_long_text(
    message: Message,
    waiting: Message,
    text: str,
    *,
    max_len: int = TELEGRAM_MAX_MESSAGE_LENGTH,
) -> None:
    """Первую часть — edit «...», остальные — отдельные сообщения."""
    parts = split_telegram_text(text, max_len=max_len)
    await waiting.edit_text(parts[0])
    for part in parts[1:]:
        await message.answer(part)
