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
    session_secret: str = "change-me"
    session_cookie_name: str = "preflight_session"
    csrf_cookie_name: str = "preflight_csrf"
    session_ttl_seconds: int = 60 * 60 * 24 * 7
    cookie_secure: bool = False
    # Permits HTTP agent adapters to call private/loopback addresses.
    # Off by default — only flip on if the operator runs their agent on the
    # same network as the API server (e.g., self-hosted setups).
    agent_endpoint_allow_private: bool = False

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allow_origins.split(",") if o.strip()]

    @property
    def cookie_samesite(self) -> str:
        return "none" if self.cookie_secure else "lax"


@lru_cache
def get_settings() -> Settings:
    return Settings()
