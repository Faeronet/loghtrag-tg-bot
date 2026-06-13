# LightRAG Telegram Bot

Telegram-бот для общения с [LightRAG](https://github.com/HKUDS/LightRAG) через REST API с многоуровневой памятью чата.

## Архитектура памяти

Память спроектирована так, чтобы **не мешать поиску в LightRAG**:

| Слой | Где хранится | Куда попадает в LightRAG |
|------|--------------|--------------------------|
| Текущий вопрос | — | поле `query` (только он участвует в retrieval) |
| Недавний диалог | PostgreSQL (буфер) | `conversation_history` (только для LLM) |
| Сжатая история | PostgreSQL (summary) | `user_prompt` |
| Долгая память | Qdrant (эмбеддинги bge-m3) | `user_prompt` |

Лимиты (`MAX_RECENT_TURNS`, `MAX_RECENT_CHARS` и др.) защищают от переполнения контекста.

## Быстрый старт

```bash
cp .env.example .env
# заполните TELEGRAM_BOT_TOKEN, LIGHTRAG_API_KEY, POSTGRES_PASSWORD

docker compose up -d --build
```

Промпт редактируется в `prompts/system_prompt.txt` без изменения `.env`.

## Команды бота

- `/start` — приветствие
- `/reset` — очистить память текущего чата (PostgreSQL + Qdrant)

## Сервисы

| Сервис | Где | Адрес |
|--------|-----|-------|
| PostgreSQL | Docker | `postgres:5432` |
| Qdrant | Docker | `qdrant:6333` |
| LightRAG API | хост | `host.docker.internal:9621` |
| bge-m3 embeddings | хост | `host.docker.internal:8010` |

PostgreSQL и Qdrant поднимаются в Docker; LightRAG и embedding — на сервере.
