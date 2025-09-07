"""Configuration settings for the loopback application."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""
    
    debug: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_prefix = "LOOPBACK_CI_"


settings = Settings()