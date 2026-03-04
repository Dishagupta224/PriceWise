"""Configuration for the pricing agent service."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings for the pricing agent."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    kafka_bootstrap_servers: str = "kafka:9092"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    openai_retry_attempts: int = 3
    openai_retry_base_delay_seconds: float = 1.5
    openai_max_tool_rounds: int = 8
    max_concurrent_decisions: int = 3
    processing_queue_size: int = 100
    metrics_log_interval_seconds: int = 60
    healthcheck_file: str = "/tmp/pricing-agent.healthy"
    strategic_drop_min_gap_percent: float = 3.0
    strategic_increase_min_gap_percent: float = 5.0
    competitor_price_buffer_percent: float = 1.5
    max_price_drop_percent_per_action: float = 5.0
    max_price_increase_percent_per_action: float = 8.0
    pricing_cooldown_minutes: int = 10
    low_stock_threshold: int = 15
    min_significant_price_change_percent: float = 2.0
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings."""
    return Settings()
