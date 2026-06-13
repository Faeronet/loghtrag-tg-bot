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
