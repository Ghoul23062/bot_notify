"""Application configuration using Pydantic Settings."""

import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = "8946298463:AAG4vUsGb__1Gx7pM-MWRPK8LR3cqitoOHA"
    database_url: str = "sqlite+aiosqlite:///./bot_notify.db"
    
    ai_api_key: Optional[str] = os.environ.get("AI_API_KEY")
    ai_provider: str = "gemini"  # "gemini", "openai", "groq"
    groq_api_key: Optional[str] = os.environ.get("GROQ_API_KEY")
    
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
