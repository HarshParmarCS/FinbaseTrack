import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.database.base import Base
from app.database.session import get_db, get_engine


def test_test_database_is_postgresql(db_session: Session) -> None:
    version = db_session.execute(text("select version()")).scalar_one()

    assert version.startswith("PostgreSQL")


def test_get_db_yields_a_working_session_and_closes_it() -> None:
    generator = get_db()
    session = next(generator)
    session.execute(text("select 1"))
    assert session.in_transaction()

    generator.close()

    assert not session.in_transaction()
    assert get_engine().pool.checkedout() == 0  # type: ignore[attr-defined]


def test_get_db_rolls_back_and_closes_when_the_request_fails() -> None:
    generator = get_db()
    session = next(generator)
    session.execute(text("select 1"))

    with pytest.raises(RuntimeError, match="boom"):
        generator.throw(RuntimeError("boom"))

    assert not session.in_transaction()
    assert get_engine().pool.checkedout() == 0  # type: ignore[attr-defined]


def test_db_session_fixture_never_persists_committed_work(
    db_session: Session, engine: Engine
) -> None:
    db_session.execute(text("create table isolation_probe (id int)"))
    db_session.commit()

    with engine.connect() as other_connection:
        visible = other_connection.execute(text("select to_regclass('isolation_probe')")).scalar()

    assert visible is None


def test_base_metadata_uses_deterministic_naming_convention() -> None:
    assert Base.metadata.naming_convention["pk"] == "pk_%(table_name)s"
    assert "fk" in Base.metadata.naming_convention
