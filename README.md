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
| PostgreSQL | Docker | `127.0.0.1:5432` |
| Qdrant | Docker | `127.0.0.1:6333` |
| LightRAG API | хост | `10.24.0.101:9621` |
| bge-m3 embeddings | хост | `10.24.0.101:8010` |

Бот запускается с `network_mode: host` и локальным **telegram-bot-api** (порт 8081).

### Настройка Telegram (обязательно)

1. Токен бота от [@BotFather](https://t.me/BotFather) → `TELEGRAM_BOT_TOKEN`
2. `TELEGRAM_API_ID` и `TELEGRAM_API_HASH` с [my.telegram.org/apps](https://my.telegram.org/apps)
3. Если Telegram заблокирован на сервере — `TELEGRAM_PROXY=socks5://host:port`
