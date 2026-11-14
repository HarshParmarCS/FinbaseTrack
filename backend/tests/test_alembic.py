from alembic import command
from alembic.script import ScriptDirectory

from tests.conftest import BACKEND_DIR, alembic_config


def test_alembic_ini_contains_no_database_url() -> None:
    ini = (BACKEND_DIR / "alembic.ini").read_text()
    active_urls = [line for line in ini.splitlines() if line.strip().startswith("sqlalchemy.url")]

    assert active_urls == []


def test_migration_history_has_exactly_one_head() -> None:
    heads = ScriptDirectory.from_config(alembic_config()).get_heads()

    assert len(heads) == 1


def test_alembic_connects_to_the_database_from_settings() -> None:
    # Raises if env.py cannot build the engine from DATABASE_URL or cannot connect.
    command.current(alembic_config())
