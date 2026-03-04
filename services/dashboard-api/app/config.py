"""Application configuration."""

import json
from functools import lru_cache

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    kafka_bootstrap_servers: str = "kafka:9092"
    api_title: str = "Smart Pricing Agent Dashboard API"
    api_version: str = "0.1.0"
    allowed_origins: list[AnyHttpUrl | str] = ["http://localhost:3000", "http://localhost:5173"]
    websocket_queue_size: int = 200
    websocket_ping_interval_seconds: int = 20
    websocket_pong_timeout_seconds: int = 45

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        """Allow JSON strings or comma-separated origins."""
        if isinstance(value, str):
            if value.startswith("["):
                return json.loads(value)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
