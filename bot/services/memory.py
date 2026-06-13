from __future__ import annotations

import asyncio
from dataclasses import dataclass

from config import settings
from db.repository import ChatRepository, Message
from services.lightrag import LightRAGClient
from services.qdrant_store import QdrantMemoryStore


@dataclass
class PreparedContext:
    query: str
    user_prompt: str
    conversation_history: list[dict[str, str]]


def _truncate(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _pair_messages(messages: list[Message]) -> list[tuple[Message, Message | None]]:
    pairs: list[tuple[Message, Message | None]] = []
    i = 0
    while i < len(messages):
        if messages[i].role == "user":
            assistant = messages[i + 1] if i + 1 < len(messages) and messages[i + 1].role == "assistant" else None
            pairs.append((messages[i], assistant))
            i += 2 if assistant else 1
        else:
            i += 1
    return pairs


def _condense_pair(user_msg: str, assistant_msg: str) -> str:
    return (
        f"Пользователь: {_truncate(user_msg, 180)}\n"
        f"Ассистент: {_truncate(assistant_msg, 180)}"
    )


class MemoryService:
    def __init__(
        self,
        repo: ChatRepository,
        qdrant: QdrantMemoryStore,
        lightrag: LightRAGClient,
    ) -> None:
        self._repo = repo
        self._qdrant = qdrant
        self._lightrag = lightrag
        self._system_prompt = settings.load_system_prompt()
        self._chat_locks: dict[int, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def _chat_lock(self, chat_id: int) -> asyncio.Lock:
        async with self._locks_guard:
            lock = self._chat_locks.get(chat_id)
            if lock is None:
                lock = asyncio.Lock()
                self._chat_locks[chat_id] = lock
            return lock

    async def prepare_context(self, chat_id: int, user_message: str) -> PreparedContext:
        await self._repo.ensure_session(chat_id)
        await self._compress_buffer_if_needed(chat_id)

        buffer = await self._repo.get_buffer_messages(chat_id)
        summary = await self._repo.get_summary(chat_id)

        conversation_history = self._build_conversation_history(buffer)
        memory_block = await self._build_memory_block(chat_id, user_message, summary)
        user_prompt = self._build_user_prompt(memory_block)

        return PreparedContext(
            query=user_message,
            user_prompt=user_prompt,
            conversation_history=conversation_history,
        )

    async def save_exchange(self, chat_id: int, user_message: str, assistant_message: str) -> None:
        await self._repo.add_message(chat_id, "user", user_message)
        await self._repo.add_message(chat_id, "assistant", assistant_message)
        await self._compress_buffer_if_needed(chat_id)
        try:
            await self._qdrant.store_turn(chat_id, user_message, assistant_message)
        except Exception:
            # Long-term memory is best-effort; chat must still work without Qdrant.
            pass

    async def reset_chat(self, chat_id: int) -> None:
        async with await self._chat_lock(chat_id):
            await self._repo.reset_chat(chat_id)
            try:
                await self._qdrant.delete_chat(chat_id)
            except Exception:
                pass

    async def ask(self, chat_id: int, user_message: str) -> str:
        async with await self._chat_lock(chat_id):
            context = await self.prepare_context(chat_id, user_message)
            answer = await self._lightrag.query(
                context.query,
                user_prompt=context.user_prompt,
                conversation_history=context.conversation_history or None,
            )
            await self.save_exchange(chat_id, user_message, answer)
            return answer

    async def _compress_buffer_if_needed(self, chat_id: int) -> None:
        rows = await self._repo.get_buffer_message_ids(chat_id)
        messages = [Message(role=role, content=content) for _, role, content in rows]
        pairs = _pair_messages(messages)

        max_turns = settings.max_recent_turns
        while len(pairs) > max_turns:
            oldest_user, oldest_assistant = pairs.pop(0)
            if oldest_assistant is None:
                continue
            summary = await self._repo.get_summary(chat_id)
            addition = _condense_pair(oldest_user.content, oldest_assistant.content)
            if summary:
                summary = f"{summary}\n\n{addition}"
            else:
                summary = addition
            summary = _truncate(summary, settings.max_summary_chars)
            await self._repo.set_summary(chat_id, summary)

        # Re-fetch and archive everything not in the last max_turns pairs.
        rows = await self._repo.get_buffer_message_ids(chat_id)
        messages = [Message(role=role, content=content) for _, role, content in rows]
        pairs = _pair_messages(messages)
        if len(pairs) <= max_turns:
            return

        keep_count = max_turns * 2
        all_ids = [row_id for row_id, _, _ in rows]
        archive_ids = all_ids[: len(all_ids) - keep_count]
        await self._repo.archive_messages(archive_ids)

    def _build_conversation_history(self, buffer: list[Message]) -> list[dict[str, str]]:
        history: list[dict[str, str]] = []
        total_chars = 0

        for msg in buffer:
            entry = {"role": msg.role, "content": msg.content}
            projected = total_chars + len(msg.content)
            if projected > settings.max_recent_chars:
                break
            history.append(entry)
            total_chars = projected

        # Drop oldest entries until within turn limit.
        max_messages = settings.max_recent_turns * 2
        if len(history) > max_messages:
            history = history[-max_messages:]

        return history

    async def _build_memory_block(self, chat_id: int, user_message: str, summary: str) -> str:
        parts: list[str] = []

        if summary.strip():
            parts.append(
                "Краткое содержание более раннего диалога:\n"
                + _truncate(summary.strip(), settings.max_summary_chars)
            )

        try:
            memories = await self._qdrant.search_relevant(
                chat_id,
                user_message,
                settings.max_retrieved_memories,
            )
        except Exception:
            memories = []

        if memories:
            formatted = "\n---\n".join(
                _truncate(memory, 400) for memory in memories
            )
            parts.append(
                "Релевантные фрагменты из прошлых обсуждений:\n" + formatted
            )

        if not parts:
            return ""

        block = "\n\n".join(parts)
        return _truncate(block, settings.max_memory_context_chars)

    def _build_user_prompt(self, memory_block: str) -> str:
        if not memory_block:
            return self._system_prompt
        return (
            f"{self._system_prompt}\n\n"
            "---\n"
            "Контекст диалога (используй только для понимания вопроса, "
            "не как источник фактов — факты бери из базы знаний):\n"
            f"{memory_block}"
        )
