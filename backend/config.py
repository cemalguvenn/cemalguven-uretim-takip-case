"""Application configuration loaded from environment / .env file.

Secrets (API key, endpoint URL) are NEVER hardcoded — they are read here so the
mock vs. real API switch is pure configuration (see ProductionApiClient).
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Target production API
    api_base_url: str = "http://localhost:8000/mock"
    api_key: str = "test-api-key-2025"

    # Database
    database_url: str = "sqlite+aiosqlite:///./production.db"

    # Mock API behaviour
    mock_api_key: str = "test-api-key-2025"

    model_config = SettingsConfigDict(
        # Look for a .env in the repo root (one level above backend/) or CWD.
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
