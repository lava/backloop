"""Configuration management for the backloop application."""

from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Uses BACKLOOP_ prefix for all environment variables.
    Supports loading from .env file.

    Examples:
        BACKLOOP_DEBUG=true
        BACKLOOP_HOST=0.0.0.0
        BACKLOOP_PORT=8080
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="BACKLOOP_",
        case_sensitive=False,
    )

    # Server configuration
    host: str = Field(
        default="127.0.0.1",
        description="Server host address",
    )
    port: Optional[int] = Field(
        default=None,
        description="Server port (auto-assigned if not specified)",
        ge=1,
        le=65535,
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode with verbose logging",
    )
    reload: bool = Field(
        default=False,
        description="Enable auto-reload on code changes",
    )

    # Review configuration
    default_since: str = Field(
        default="HEAD",
        description="Default git reference for review diffs",
    )
    auto_refresh_interval: int = Field(
        default=30,
        description="Auto-refresh interval in seconds",
        ge=1,
        le=3600,
    )
    max_diff_size: int = Field(
        default=1000000,
        description="Maximum diff size in bytes",
        ge=1,
    )

    # Static files configuration
    static_dir: Optional[Path] = Field(
        default=None,
        description="Custom static files directory",
    )
    templates_dir: Optional[Path] = Field(
        default=None,
        description="Custom templates directory",
    )

    @field_validator("static_dir", "templates_dir", mode="before")
    @classmethod
    def validate_path(cls, v: Optional[str | Path]) -> Optional[Path]:
        """Convert string paths to Path objects."""
        if v is None or isinstance(v, Path):
            return v
        return Path(v)


# Global settings instance
settings = Settings()
