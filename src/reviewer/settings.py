"""Configuration settings for the reviewer application."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""
    
    debug: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_prefix = "BACKLOOP_CI_"


# Global settings instance
settings = Settings()