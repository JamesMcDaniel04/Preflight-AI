from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    database_url: str = "sqlite:///./preflight.db"
    redis_url: str = "redis://localhost:6379/0"
    default_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    max_concurrent_llm_calls: int = 5
    allow_origins: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
