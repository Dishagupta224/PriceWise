"""Configuration for the inventory service."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    kafka_bootstrap_servers: str = "kafka:9092"
    inventory_consumer_group: str = "inventory-service"
    low_stock_threshold: int = 15
    log_level: str = "INFO"
    healthcheck_file: str = "/tmp/inventory-service.healthy"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings."""
    return Settings()
