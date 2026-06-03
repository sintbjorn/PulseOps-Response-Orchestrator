from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PulseOps Response Orchestrator"
    environment: str = "local"
    log_level: str = "INFO"

    database_url: str = "sqlite+pysqlite:///./pulseops.db"
    auto_create_schema: bool = True
    seed_demo_data: bool = True

    pulsewatch_base_url: str | None = None
    pulsewatch_api_key: str | None = None
    pulsewatch_callback_enabled: bool = False
    pulsewatch_summary_path: str = "/api/v1/incidents/{incident_id}/comments"

    notification_service_url: str | None = None
    notification_service_api_key: str | None = None
    notification_callback_enabled: bool = False

    http_timeout_seconds: float = Field(default=5.0, gt=0)

    model_config = SettingsConfigDict(
        env_prefix="PULSEOPS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
