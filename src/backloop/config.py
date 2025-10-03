"""Configuration management for the backloop application."""

import os
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

    @classmethod
    def load_with_legacy_support(cls) -> "Settings":
        """Load settings with support for legacy environment variable prefixes.

        Supports backward compatibility with:
        - REVIEWER_* prefix (old config.py)
        - LOOPBACK_CI_* prefix (old settings.py)

        Priority: BACKLOOP_* > REVIEWER_* > LOOPBACK_CI_*
        """
        # Create base settings from BACKLOOP_ variables
        settings = cls()

        # Legacy REVIEWER_* support
        legacy_mappings = {
            "REVIEWER_HOST": "host",
            "REVIEWER_PORT": "port",
            "REVIEWER_DEBUG": "debug",
            "REVIEWER_RELOAD": "reload",
            "REVIEWER_DEFAULT_SINCE": "default_since",
            "REVIEWER_REFRESH_INTERVAL": "auto_refresh_interval",
            "REVIEWER_MAX_DIFF_SIZE": "max_diff_size",
            "REVIEWER_STATIC_DIR": "static_dir",
            "REVIEWER_TEMPLATES_DIR": "templates_dir",
        }

        # Legacy LOOPBACK_CI_* support (only debug was used)
        legacy_mappings["LOOPBACK_CI_DEBUG"] = "debug"

        # Apply legacy values only if BACKLOOP_ version not set
        for legacy_var, field_name in legacy_mappings.items():
            value = os.getenv(legacy_var)
            if value and not os.getenv(f"BACKLOOP_{field_name.upper()}"):
                # Get current value from settings
                current = getattr(settings, field_name)

                # Convert based on field type
                if field_name in ("debug", "reload"):
                    setattr(settings, field_name, value.lower() in ("true", "1", "yes"))
                elif field_name in ("port", "auto_refresh_interval", "max_diff_size"):
                    setattr(settings, field_name, int(value))
                elif field_name in ("static_dir", "templates_dir"):
                    setattr(settings, field_name, Path(value))
                else:
                    setattr(settings, field_name, value)

        return settings


# Global settings instance with legacy support
settings = Settings.load_with_legacy_support()


# Backward compatibility aliases
config = settings  # For code that imports 'config'
Config = Settings  # For code that references 'Config' class
