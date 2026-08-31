"""
Configuration management using pydantic-settings.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, validated on startup."""

    imap_host: str = Field(..., description="Host del servidor IMAP (ej. imap.gmail.com)", alias="CAJACLARAD_IMAP_HOST")
    imap_port: int = Field(default=993, description="Puerto del servidor IMAP", alias="CAJACLARAD_IMAP_PORT")
    imap_user: str = Field(..., description="Usuario de correo", alias="CAJACLARAD_IMAP_USER")
    imap_password: str | None = Field(default=None, description="Contraseña de aplicación", alias="CAJACLARAD_IMAP_PASSWORD")
    imap_oauth2_token: str | None = Field(default=None, description="Token OAuth2 si aplica", alias="CAJACLARAD_IMAP_OAUTH2_TOKEN")

    # Inteligencia Artificial
    ai_provider: str = Field(default="gemini", description="Proveedor del LLM (ej. gemini, openai)", alias="CAJACLARAD_AI_PROVIDER")
    ai_api_key: str | None = Field(default=None, description="API Key para el extractor cognitivo", alias="CAJACLARAD_AI_API_KEY")

    # Base de datos
    db_path: str = Field(default="cajaclarad.db", description="Ruta a la BD SQLite", alias="CAJACLARAD_DB_PATH")

    # Seguridad de la API REST
    api_key: str = Field(default="dev-secret-key", description="Llave maestra para acceder a la API", alias="CAJACLARAD_API_KEY")
    poll_interval: int = Field(default=120, alias="CAJACLARAD_POLL_INTERVAL", ge=10)
    log_level: str = Field(default="INFO", alias="CAJACLARAD_LOG_LEVEL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


# Instantiate config globally. If environment variables are missing,
# this will raise a ValidationError during module import, preventing startup.
config = Settings()
