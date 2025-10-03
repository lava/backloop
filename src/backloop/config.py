"""Configuration management for the reviewer application."""

import os
from pathlib import Path
from pydantic import BaseModel
from typing import Optional


class ServerConfig(BaseModel):
    """Server configuration."""

    host: str = "127.0.0.1"
    port: Optional[int] = None
    debug: bool = False
    reload: bool = False


class ReviewConfig(BaseModel):
    """Review configuration."""

    default_since: str = "HEAD"
    auto_refresh_interval: int = 30  # seconds
    max_diff_size: int = 1000000  # bytes


class StaticConfig(BaseModel):
    """Static files configuration."""

    static_dir: Optional[Path] = None
    templates_dir: Optional[Path] = None


class Config(BaseModel):
    """Main application configuration."""

    server: ServerConfig = ServerConfig()
    review: ReviewConfig = ReviewConfig()
    static: StaticConfig = StaticConfig()

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from environment variables."""
        config = cls()

        # Server config from environment
        if port := os.getenv("REVIEWER_PORT"):
            config.server.port = int(port)
        if host := os.getenv("REVIEWER_HOST"):
            config.server.host = host
        if debug := os.getenv("REVIEWER_DEBUG"):
            config.server.debug = debug.lower() in ("true", "1", "yes")
        if reload := os.getenv("REVIEWER_RELOAD"):
            config.server.reload = reload.lower() in ("true", "1", "yes")

        # Review config from environment
        if since := os.getenv("REVIEWER_DEFAULT_SINCE"):
            config.review.default_since = since
        if interval := os.getenv("REVIEWER_REFRESH_INTERVAL"):
            config.review.auto_refresh_interval = int(interval)
        if max_size := os.getenv("REVIEWER_MAX_DIFF_SIZE"):
            config.review.max_diff_size = int(max_size)

        return config


# Global configuration instance
config = Config.load()
