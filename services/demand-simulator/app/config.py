"""Configuration for the demand simulator service."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    kafka_bootstrap_servers: str = "kafka:9092"
    simulation_min_interval_seconds: int = 10
    simulation_max_interval_seconds: int = 30
    simulation_speed: float = 1.0
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings."""
    return Settings()
