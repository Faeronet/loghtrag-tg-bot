from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import asyncpg

from config import settings


@dataclass
class Message:
    role: str
    content: str
    created_at: datetime | None = None


class ChatRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @classmethod
    async def create(cls) -> ChatRepository:
        pool = await asyncpg.create_pool(
            settings.postgres_dsn,
            min_size=settings.postgres_pool_min,
            max_size=settings.postgres_pool_max,
        )
        async with pool.acquire() as conn:
            await conn.execute(_SCHEMA_SQL)
        return cls(pool)

    async def close(self) -> None:
        await self._pool.close()

    async def ensure_session(self, chat_id: int) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chat_sessions (chat_id)
                VALUES ($1)
                ON CONFLICT (chat_id) DO NOTHING
                """,
                chat_id,
            )

    async def add_message(self, chat_id: int, role: str, content: str) -> None:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO chat_sessions (chat_id)
                    VALUES ($1)
                    ON CONFLICT (chat_id) DO NOTHING
                    """,
                    chat_id,
                )
                await conn.execute(
                    """
                    INSERT INTO chat_messages (chat_id, role, content, in_buffer)
                    VALUES ($1, $2, $3, TRUE)
                    """,
                    chat_id,
                    role,
                    content,
                )
                await conn.execute(
                    "UPDATE chat_sessions SET updated_at = NOW() WHERE chat_id = $1",
                    chat_id,
                )

    async def get_buffer_messages(self, chat_id: int) -> list[Message]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT role, content, created_at
                FROM chat_messages
                WHERE chat_id = $1 AND in_buffer = TRUE
                ORDER BY created_at ASC
                """,
                chat_id,
            )
        return [Message(role=r["role"], content=r["content"], created_at=r["created_at"]) for r in rows]

    async def get_summary(self, chat_id: int) -> str:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT summary FROM chat_sessions WHERE chat_id = $1",
                chat_id,
            )
        return (row["summary"] if row else "") or ""

    async def set_summary(self, chat_id: int, summary: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE chat_sessions
                SET summary = $2, updated_at = NOW()
                WHERE chat_id = $1
                """,
                chat_id,
                summary,
            )

    async def archive_messages(self, message_ids: list[int]) -> None:
        if not message_ids:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE chat_messages
                SET in_buffer = FALSE
                WHERE id = ANY($1::bigint[])
                """,
                message_ids,
            )

    async def get_buffer_message_ids(self, chat_id: int) -> list[tuple[int, str, str]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, role, content
                FROM chat_messages
                WHERE chat_id = $1 AND in_buffer = TRUE
                ORDER BY created_at ASC
                """,
                chat_id,
            )
        return [(r["id"], r["role"], r["content"]) for r in rows]

    async def reset_chat(self, chat_id: int) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM chat_messages WHERE chat_id = $1", chat_id)
            await conn.execute(
                """
                UPDATE chat_sessions
                SET summary = '', updated_at = NOW()
                WHERE chat_id = $1
                """,
                chat_id,
            )

    async def get_recent_archived_pairs(self, chat_id: int, limit: int = 20) -> list[Message]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT role, content, created_at
                FROM chat_messages
                WHERE chat_id = $1 AND in_buffer = FALSE
                ORDER BY created_at DESC
                LIMIT $2
                """,
                chat_id,
                limit,
            )
        rows = list(reversed(rows))
        return [Message(role=r["role"], content=r["content"], created_at=r["created_at"]) for r in rows]


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    chat_id BIGINT PRIMARY KEY,
    summary TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL REFERENCES chat_sessions(chat_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    in_buffer BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_buffer
    ON chat_messages (chat_id, in_buffer, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_created
    ON chat_messages (chat_id, created_at DESC);
"""
