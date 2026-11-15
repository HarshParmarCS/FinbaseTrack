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
    monkeypatch.setenv("COOKIE_SECURE", "true")
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


# ---- authentication, cookie and CORS settings -------------------------------------------------


def test_jwt_secret_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        make_settings(database_url=PG_URL)

    assert "jwt_secret_key" in str(exc_info.value)


def test_short_jwt_secret_is_rejected_and_never_echoed() -> None:
    with pytest.raises(ValidationError) as exc_info:
        make_settings(database_url=PG_URL, jwt_secret_key="too-short-secret")

    assert "at least 32" in str(exc_info.value)
    assert "too-short-secret" not in str(exc_info.value)


def test_jwt_secret_is_masked_in_repr() -> None:
    settings = make_settings(database_url=PG_URL, jwt_secret_key="a-very-long-secret-" + "x" * 30)

    assert "a-very-long-secret" not in repr(settings)


def test_production_requires_secure_cookies() -> None:
    with pytest.raises(ValidationError, match="COOKIE_SECURE"):
        make_settings(database_url=PG_URL, environment="production", cookie_secure=False)


def test_production_rejects_the_placeholder_secret() -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        make_settings(
            database_url=PG_URL,
            environment="production",
            cookie_secure=True,
            jwt_secret_key="CHANGE_ME_GENERATE_A_LONG_RANDOM_SECRET",
        )


def test_allowed_origins_are_parsed_from_a_comma_separated_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000, https://app.example.com/")

    settings = make_settings(database_url=PG_URL)

    assert settings.allowed_origins == ["http://localhost:3000", "https://app.example.com"]


@pytest.mark.parametrize(
    "origin", ["*", "localhost:3000", "ftp://host", "https://app.example.com/path", ""]
)
def test_invalid_allowed_origins_are_rejected(origin: str) -> None:
    with pytest.raises(ValidationError):
        make_settings(database_url=PG_URL, allowed_origins=[origin])


def test_cookie_defaults_and_empty_domain() -> None:
    settings = make_settings(database_url=PG_URL, cookie_domain="")

    assert settings.cookie_domain is None
    assert settings.cookie_samesite == "lax"
    assert settings.access_token_expire_minutes == 15
    assert settings.refresh_token_expire_days == 7


def test_samesite_none_is_not_allowed() -> None:
    with pytest.raises(ValidationError):
        make_settings(database_url=PG_URL, cookie_samesite="none")
