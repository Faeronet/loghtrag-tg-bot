from pathlib import Path
from urllib.parse import quote

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str

    @field_validator("telegram_bot_token", mode="before")
    @classmethod
    def strip_telegram_token(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().strip('"').strip("'")
        return value

    # Telegram network
    telegram_request_timeout: float = Field(default=20.0, ge=5.0)
    telegram_connect_retries: int = Field(default=5, ge=1)
    telegram_connect_retry_delay: float = Field(default=3.0, ge=1.0)
    telegram_proxy: str | None = None
    telegram_proxy_type: str = "socks5"
    telegram_proxy_host: str | None = None
    telegram_proxy_port: int | None = None
    telegram_proxy_login: str | None = None
    telegram_proxy_password: str | None = None
    # Обычно не нужен — бот ходит на https://api.telegram.org
    telegram_api_base: str | None = None

    @model_validator(mode="after")
    def build_proxy_url(self) -> "Settings":
        if self.telegram_proxy or not self.telegram_proxy_host or not self.telegram_proxy_port:
            return self
        scheme = self.telegram_proxy_type.strip().lower() or "socks5"
        if scheme == "socks5":
            # Как curl socks5h — резолвим api.telegram.org на стороне прокси.
            scheme = "socks5h"
        auth = ""
        if self.telegram_proxy_login:
            user = quote(self.telegram_proxy_login, safe="")
            password = quote(self.telegram_proxy_password or "", safe="")
            auth = f"{user}:{password}@"
        self.telegram_proxy = (
            f"{scheme}://{auth}{self.telegram_proxy_host}:{self.telegram_proxy_port}"
        )
        return self

    lightrag_url: str = "http://10.24.0.101:9621"
    lightrag_api_key: str
    lightrag_query_mode: str = "mix"
    lightrag_timeout: float = 120.0

    embedding_url: str = "http://10.24.0.101:8010"
    embedding_model: str = "BAAI/bge-m3"

    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "telegram_chat_memory"
    qdrant_connect_retries: int = Field(default=5, ge=1)
    qdrant_connect_retry_delay: float = Field(default=2.0, ge=0.5)

    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "lightrag_bot"
    postgres_user: str = "lightrag_bot"
    postgres_password: str

    system_prompt_path: str = "/app/prompts/system_prompt.txt"

    # Working memory: recent turns sent as conversation_history to LightRAG.
    max_recent_turns: int = Field(default=6, ge=2, le=20)
    max_recent_chars: int = Field(default=4000, ge=500)

    # Rolling summary of older turns (injected into user_prompt, not query).
    max_summary_chars: int = Field(default=1500, ge=200)

    # Long-term semantic memory via Qdrant.
    max_retrieved_memories: int = Field(default=3, ge=0, le=10)
    memory_score_threshold: float = Field(default=0.55, ge=0.0, le=1.0)

    # Total cap for user_prompt additions (summary + retrieved memories).
    max_memory_context_chars: int = Field(default=2500, ge=500)

    # Concurrency: DB pool and shared HTTP connection limits.
    postgres_pool_min: int = Field(default=10, ge=1)
    postgres_pool_max: int = Field(default=100, ge=5)
    http_max_connections: int = Field(default=200, ge=10)
    http_max_keepalive: int = Field(default=50, ge=5)

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def load_system_prompt(self) -> str:
        path = Path(self.system_prompt_path)
        return path.read_text(encoding="utf-8").strip()


settings = Settings()
