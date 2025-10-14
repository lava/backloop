"""Configuration management for the backloop application."""

import os
import warnings
from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator, model_validator
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
        extra="ignore",  # Ignore unknown environment variables
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

    @model_validator(mode="after")
    def warn_unknown_backloop_vars(self) -> "Settings":
        """Warn about unknown BACKLOOP_ prefixed environment variables."""
        known_fields = {name.upper() for name in self.model_fields.keys()}

        for env_var in os.environ:
            if env_var.startswith("BACKLOOP_"):
                field_name = env_var[9:]

                if field_name.upper() not in known_fields:
                    warnings.warn(
                        f"Unknown environment variable '{env_var}' will be ignored. "
                        f"Valid BACKLOOP_ variables are: {', '.join(sorted('BACKLOOP_' + name.upper() for name in self.model_fields.keys()))}",
                        UserWarning,
                        stacklevel=2,
                    )

        return self


settings = Settings()
