"""Application configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql://manualstudio:manualstudio@localhost:5432/manualstudio"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # S3/MinIO Storage
    s3_endpoint_url: str = "http://localhost:9000"
    s3_bucket: str = "manualstudio"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"

    # OpenAI
    openai_api_key: str | None = None

    # Anthropic (optional)
    anthropic_api_key: str | None = None

    # Provider settings
    llm_provider: str = "openai"
    transcribe_provider: str = "openai"

    # Application settings
    max_video_minutes: int = 15
    max_video_size_mb: int = 1024
    secret_key: str = "dev-secret-key-change-in-production"

    # Logging
    log_level: str = "INFO"

    # Derived settings
    @property
    def max_video_duration_seconds(self) -> int:
        return self.max_video_minutes * 60

    @property
    def max_video_size_bytes(self) -> int:
        return self.max_video_size_mb * 1024 * 1024

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
