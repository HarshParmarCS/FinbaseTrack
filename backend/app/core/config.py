"""Environment-based application settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

# backend/.env, resolved independent of the working directory.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Application settings, read from environment variables (and backend/.env)."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Validation errors must never echo raw input: DATABASE_URL contains a password.
        hide_input_in_errors=True,
    )

    app_name: str = "FinTasks API"
    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Required, no default: credentials must never live in code.
    # SecretStr keeps the password out of reprs and validation error messages.
    database_url: SecretStr
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo: bool = False

    @model_validator(mode="after")
    def validate_database_url(self) -> Self:
        """Require PostgreSQL and make sure the psycopg 3 driver is used.

        This is an "after" model validator on purpose: pydantic reports the raw input of a
        failing field validator, which would put the password into the error message.
        Here the value is already wrapped in SecretStr, so it stays masked.
        """
        try:
            url = make_url(self.database_url.get_secret_value())
        except ArgumentError as exc:
            raise ValueError("DATABASE_URL is not a valid database URL") from exc
        if url.get_backend_name() != "postgresql":
            raise ValueError("DATABASE_URL must be a PostgreSQL URL (postgresql+psycopg://...)")
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        self.database_url = SecretStr(url.render_as_string(hide_password=False))
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance (override or clear the cache in tests)."""
    return Settings()  # database_url is read from the environment
