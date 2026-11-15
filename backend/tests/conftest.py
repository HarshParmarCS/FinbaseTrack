"""Pytest configuration: real PostgreSQL, per-test rollback, isolated app instances.

Environment is prepared BEFORE any ``app`` module is imported, so settings and the
engine always point at the test database.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from sqlalchemy import Engine, create_engine, make_url
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(BACKEND_DIR / ".env").get(
        "TEST_DATABASE_URL"
    )
    if not url:
        pytest.exit(
            "TEST_DATABASE_URL is not set. Create a PostgreSQL database whose name ends with "
            "'_test' and set TEST_DATABASE_URL (environment or backend/.env). See README.",
            returncode=2,
        )
    database = make_url(url).database or ""
    if not database.endswith("_test"):
        pytest.exit("TEST_DATABASE_URL must point to a database whose name ends with '_test'.", 2)
    return url


TEST_DATABASE_URL = _test_database_url()
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["ENVIRONMENT"] = "test"
os.environ["LOG_LEVEL"] = "WARNING"
# Fixed, test-only values (never real secrets). Environment variables beat backend/.env.
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-at-least-32-characters-long"
os.environ["JWT_ISSUER"] = "fintasks-api"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "15"
os.environ["REFRESH_TOKEN_EXPIRE_DAYS"] = "7"
os.environ["COOKIE_SECURE"] = "false"
os.environ["COOKIE_SAMESITE"] = "lax"
os.environ["COOKIE_DOMAIN"] = ""
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.database.session import get_db, get_engine, get_session_factory  # noqa: E402
from app.main import create_app  # noqa: E402


def alembic_config() -> Config:
    """Alembic configuration for programmatic use (keeps the test logging configuration)."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Engine bound to the test database."""
    test_engine = create_engine(get_settings().database_url.get_secret_value(), pool_pre_ping=True)
    yield test_engine
    test_engine.dispose()
    get_engine().dispose()


@pytest.fixture(scope="session", autouse=True)
def _migrated_database(engine: Engine) -> None:
    """Bring the test database to the latest schema once per test run."""
    command.upgrade(alembic_config(), "head")


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    """Session whose work is rolled back at the end of the test (savepoint-based)."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def app(db_session: Session) -> FastAPI:
    """A fresh application whose DB dependency uses the rolled-back test session."""
    application = create_app()

    def override_get_db() -> Iterator[Session]:
        # Mirrors the real get_db: roll back uncommitted work when the request fails.
        try:
            yield db_session
        except Exception:
            db_session.rollback()
            raise

    application.dependency_overrides[get_db] = override_get_db
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # raise_server_exceptions=False lets tests observe the 500 envelope.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _clear_caches() -> Iterator[None]:
    """Keep settings/engine caches from leaking between tests that change the environment."""
    yield
    get_settings.cache_clear()
    get_session_factory.cache_clear()
