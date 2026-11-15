"""Environment-based application settings."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

# backend/.env, resolved independent of the working directory.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

BACKEND_DIR = ENV_FILE.parent
DEFAULT_POLICY_FILE = BACKEND_DIR / "app" / "authorization" / "policies.json"

MIN_JWT_SECRET_LENGTH = 32  # HS256 needs a key of at least 256 bits


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

    # JSON file with the authorization policies (validated at startup). Relative paths are
    # resolved against the backend directory.
    policy_file: Path = DEFAULT_POLICY_FILE

    # ---- authentication ------------------------------------------------------------------
    # Signing key for access and refresh JWTs. Required, never exposed to the frontend.
    jwt_secret_key: SecretStr
    jwt_issuer: str = "fintasks-api"
    access_token_expire_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=30)

    # ---- cookies, CSRF and CORS ------------------------------------------------------------
    cookie_secure: bool = False  # must be true in production (HTTPS)
    cookie_samesite: Literal["lax", "strict"] = "lax"
    cookie_domain: str | None = None  # None = host-only cookies
    # Browser origins allowed to call the API with credentials (CORS) and to send
    # state-changing requests (CSRF Origin check). Comma separated in the environment.
    allowed_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    @field_validator("policy_file")
    @classmethod
    def resolve_policy_file(cls, value: Path) -> Path:
        return value if value.is_absolute() else (BACKEND_DIR / value).resolve()

    @field_validator("cookie_domain", mode="before")
    @classmethod
    def empty_cookie_domain_means_host_only(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("allowed_origins")
    @classmethod
    def validate_allowed_origins(cls, origins: list[str]) -> list[str]:
        cleaned: list[str] = []
        for origin in origins:
            parts = urlsplit(origin)
            if origin == "*" or parts.scheme not in {"http", "https"} or not parts.netloc:
                raise ValueError("ALLOWED_ORIGINS entries must look like https://host[:port]")
            if parts.path not in {"", "/"} or parts.query or parts.fragment:
                raise ValueError("ALLOWED_ORIGINS entries must not contain a path")
            cleaned.append(f"{parts.scheme}://{parts.netloc}")
        return cleaned

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

    @model_validator(mode="after")
    def validate_security_settings(self) -> Self:
        secret = self.jwt_secret_key.get_secret_value()
        if len(secret) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(f"JWT_SECRET_KEY must be at least {MIN_JWT_SECRET_LENGTH} characters")
        if self.is_production:
            if "CHANGE_ME" in secret:
                raise ValueError("JWT_SECRET_KEY is still the placeholder value")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance (override or clear the cache in tests)."""
    return Settings()  # secrets are read from the environment
