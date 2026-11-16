"""Apply Alembic migrations once, safely, before the API starts (used by the container entrypoint).

* Waits until PostgreSQL accepts connections (the compose health check covers the normal case;
  this also covers a database that is restarting).
* Takes a PostgreSQL advisory lock for the duration of the upgrade, so two backend containers
  started at the same time never run competing migrations: the second one waits, then finds
  nothing to do.
* Only ever runs `alembic upgrade head`: it never drops or recreates tables.

Run from the backend directory: `python -m scripts.migrate`.
"""

import logging
import sys
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings

# Any fixed 64-bit number works; it only has to be the same for every backend process.
MIGRATION_LOCK_ID = 727_001_2026
LOCK = text("SELECT pg_advisory_lock(:id)")
UNLOCK = text("SELECT pg_advisory_unlock(:id)")
ATTEMPTS = 30
DELAY_SECONDS = 2

logger = logging.getLogger("migrate")
# Alembic's logging config (alembic.ini) sets the root logger to WARNING; keep this one at INFO.
logger.setLevel(logging.INFO)
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def main() -> int:
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    engine = create_engine(get_settings().database_url.get_secret_value(), pool_pre_ping=True)
    try:
        for attempt in range(1, ATTEMPTS + 1):
            try:
                connection = engine.connect()
                break
            except OperationalError:
                logger.info("Database not ready (attempt %d of %d), retrying", attempt, ATTEMPTS)
                time.sleep(DELAY_SECONDS)
        else:
            logger.error("Database is not reachable; giving up")
            return 1

        with connection:
            logger.info("Waiting for the migration lock")
            connection.execute(LOCK, {"id": MIGRATION_LOCK_ID})
            try:
                logger.info("Applying migrations (alembic upgrade head)")
                command.upgrade(Config(str(ALEMBIC_INI)), "head")
                logger.info("Database schema is up to date")
            finally:
                connection.execute(UNLOCK, {"id": MIGRATION_LOCK_ID})
                connection.commit()
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
