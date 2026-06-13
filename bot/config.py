from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str

    lightrag_url: str = "http://10.24.0.101:9621"
    lightrag_api_key: str
    lightrag_query_mode: str = "mix"
    lightrag_timeout: float = 120.0

    embedding_url: str = "http://10.24.0.101:8010"
    embedding_model: str = "BAAI/bge-m3"

    qdrant_url: str = "http://10.24.0.101:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "telegram_chat_memory"

    postgres_host: str = "postgres"
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
