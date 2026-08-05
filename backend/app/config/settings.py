from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    log_level: str = "INFO"

    # TradingAgents
    tradingagents_provider: str = "openai"
    tradingagents_deep_think_llm: str = "gpt-5.2"
    tradingagents_quick_think_llm: str = "gpt-5-mini"
    tradingagents_backend_url: Optional[str] = None

    # Default models per agent role
    default_technical_model: str = "gpt-5.2"
    default_news_model: str = "gpt-5-mini"
    default_social_model: str = "gpt-5-mini"
    default_fundamentals_model: str = "gpt-5-mini"

    # Daily limit
    free_daily_limit: int = 4

    # Personalized news feed
    news_refresh_interval_hours: int = 4

    # CORS
    cors_origins_str: str = "*"

    @field_validator("cors_origins_str", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            if v == "*":
                return "*"
            return v
        return "*"

    @property
    def cors_origins(self) -> list[str]:
        if self.cors_origins_str == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins_str.split(",")]

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()