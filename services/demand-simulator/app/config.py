"""Configuration for the demand simulator service."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    kafka_bootstrap_servers: str = "kafka:9092"
    simulation_min_interval_seconds: int = 30
    simulation_max_interval_seconds: int = 300
    simulation_speed: float = 1.0
    demo_simulation_min_interval_seconds: int = 5
    demo_simulation_max_interval_seconds: int = 20
    demo_simulation_speed: float = 2.0
    compose_profiles: str = ""
    demo_flag_file: str = "/runtime/demo-profile.flag"
    log_level: str = "INFO"
    healthcheck_file: str = "/tmp/demand-simulator.healthy"

    @property
    def is_demo_profile(self) -> bool:
        """Return True when Docker Compose demo profile is active."""
        profile_set = {profile.strip() for profile in self.compose_profiles.split(",") if profile.strip()}
        return "demo" in profile_set or Path(self.demo_flag_file).exists()

    @property
    def effective_min_interval_seconds(self) -> int:
        """Return interval min based on active profile."""
        return self.demo_simulation_min_interval_seconds if self.is_demo_profile else self.simulation_min_interval_seconds

    @property
    def effective_max_interval_seconds(self) -> int:
        """Return interval max based on active profile."""
        return self.demo_simulation_max_interval_seconds if self.is_demo_profile else self.simulation_max_interval_seconds

    @property
    def effective_simulation_speed(self) -> float:
        """Return simulation speed based on active profile."""
        return self.demo_simulation_speed if self.is_demo_profile else self.simulation_speed


@lru_cache
def get_settings() -> Settings:
    """Return cached settings."""
    return Settings()
