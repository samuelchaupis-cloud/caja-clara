"""
Configuration management using pydantic-settings.
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, validated on startup."""
    
    imap_host: str = Field(..., alias="CAJACLARAD_IMAP_HOST")
    imap_port: int = Field(default=993, alias="CAJACLARAD_IMAP_PORT")
    imap_user: str = Field(..., alias="CAJACLARAD_IMAP_USER")
    imap_password: str = Field(..., alias="CAJACLARAD_IMAP_PASSWORD")
    
    db_path: str = Field(..., alias="CAJACLARAD_DB_PATH")
    poll_interval: int = Field(default=120, alias="CAJACLARAD_POLL_INTERVAL", ge=10)
    log_level: str = Field(default="INFO", alias="CAJACLARAD_LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate config globally. If environment variables are missing,
# this will raise a ValidationError during module import, preventing startup.
config = Settings()
