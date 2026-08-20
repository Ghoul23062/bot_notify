"""Application configuration using Pydantic Settings."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = "123456789:YOUR_TELEGRAM_BOT_TOKEN"
    database_url: str = "sqlite+aiosqlite:///./bot_notify.db"
    
    ai_api_key: Optional[str] = None
    ai_provider: str = "gemini"  # "gemini", "openai", "groq"
    groq_api_key: Optional[str] = None
    
    default_timezone: str = "Europe/Moscow"
    log_level: str = "INFO"
    
    # Poll interval in seconds for the persistent background scheduler
    scheduler_poll_interval: int = 15

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
