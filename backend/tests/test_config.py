import pytest
from pydantic import ValidationError

from app.core.config import Settings

PG_URL = "postgresql+psycopg://user:pw@localhost:5432/db"


def make_settings(**overrides: object) -> Settings:
    # _env_file=None: ignore any local backend/.env so tests are deterministic.
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_settings_read_values_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", PG_URL)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("LOG_LEVEL", "ERROR")

    settings = make_settings()

    assert settings.environment == "production"
    assert settings.is_production
    assert settings.log_level == "ERROR"
    assert settings.database_url.get_secret_value() == PG_URL


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        make_settings()

    assert "database_url" in str(exc_info.value)


def test_plain_postgresql_scheme_is_normalized_to_psycopg3() -> None:
    settings = make_settings(database_url="postgresql://user:pw@localhost/db")

    assert settings.database_url.get_secret_value().startswith("postgresql+psycopg://")


@pytest.mark.parametrize(
    "url", ["sqlite:///app.db", "sqlite://", "mysql+pymysql://u:p@h/db", "not a url"]
)
def test_non_postgresql_database_urls_are_rejected(url: str) -> None:
    with pytest.raises(ValidationError):
        make_settings(database_url=url)


def test_password_is_not_exposed_in_repr_or_validation_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(database_url="postgresql://user:topsecretpw@localhost/db")
    assert "topsecretpw" not in repr(settings)

    # Same path as a real misconfiguration: the bad URL arrives through the environment.
    monkeypatch.setenv("DATABASE_URL", "mysql://u:topsecretpw@h/db")
    with pytest.raises(ValidationError) as exc_info:
        make_settings()
    assert "topsecretpw" not in str(exc_info.value)


def test_invalid_environment_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(database_url=PG_URL, environment="staging")
