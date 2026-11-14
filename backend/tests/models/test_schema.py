"""Migration and schema-level tests: the migration, the models and the docs must agree."""

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect, text
from sqlalchemy.orm import Session

from app.database.base import Base
from tests.conftest import alembic_config

EXPECTED_TABLES = {
    "users",
    "projects",
    "project_members",
    "tasks",
    "activity_logs",
    "refresh_tokens",
}


def test_migration_creates_all_tables(engine: Engine) -> None:
    tables = set(inspect(engine).get_table_names()) - {"alembic_version"}

    assert tables == EXPECTED_TABLES


def test_models_and_migration_describe_the_same_schema(engine: Engine) -> None:
    """Alembic autogenerate finds no difference between the models and the migrated database."""
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})

        differences = compare_metadata(context, Base.metadata)

    assert differences == []


def test_migration_can_be_reverted_and_reapplied(engine: Engine) -> None:
    config = alembic_config()
    try:
        command.downgrade(config, "base")
        assert set(inspect(engine).get_table_names()) - {"alembic_version"} == set()
    finally:
        command.upgrade(config, "head")

    assert set(inspect(engine).get_table_names()) - {"alembic_version"} == EXPECTED_TABLES


def test_pg_trgm_extension_is_installed(db_session: Session) -> None:
    installed = db_session.execute(
        text("select count(*) from pg_extension where extname = 'pg_trgm'")
    ).scalar_one()

    assert installed == 1


def test_expected_indexes_exist(engine: Engine) -> None:
    inspector = inspect(engine)
    expected = {
        "users": {"uq_users_email"},
        "projects": {"ix_projects_owner_id", "ix_projects_status"},
        "project_members": {"uq_project_members_project_user", "ix_project_members_user_id"},
        "tasks": {
            "ix_tasks_project_status_position",
            "ix_tasks_project_created_at",
            "ix_tasks_project_due_date",
            "ix_tasks_assignee_id",
            "ix_tasks_title_trgm",
            "ix_tasks_description_trgm",
        },
        "activity_logs": {
            "ix_activity_logs_project_created",
            "ix_activity_logs_user_created",
            "ix_activity_logs_task_created",
        },
        "refresh_tokens": {
            "uq_refresh_tokens_token_hash",
            "ix_refresh_tokens_user_id",
            "ix_refresh_tokens_family_id",
        },
    }

    for table, names in expected.items():
        # Unique constraints appear as unique indexes in PostgreSQL.
        actual = {index["name"] for index in inspector.get_indexes(table)}
        assert names <= actual, f"{table}: missing {names - actual}"


def test_search_indexes_use_trigram_gin(db_session: Session) -> None:
    definitions = (
        db_session.execute(
            text(
                "select indexdef from pg_indexes "
                "where tablename = 'tasks' and indexname like '%trgm'"
            )
        )
        .scalars()
        .all()
    )

    assert len(definitions) == 2
    assert all("USING gin" in d and "gin_trgm_ops" in d for d in definitions)


def test_all_timestamp_columns_are_timezone_aware(engine: Engine) -> None:
    inspector = inspect(engine)
    timestamp_columns = [
        (table, column["name"], column["type"])
        for table in EXPECTED_TABLES
        for column in inspector.get_columns(table)
        if column["name"].endswith("_at") or column["name"] == "joined_at"
    ]

    assert timestamp_columns
    for table, name, column_type in timestamp_columns:
        assert getattr(column_type, "timezone", False), f"{table}.{name} is not timestamptz"


def test_all_primary_keys_are_uuid(engine: Engine) -> None:
    inspector = inspect(engine)

    for table in EXPECTED_TABLES:
        key = inspector.get_pk_constraint(table)["constrained_columns"]
        assert key == ["id"], table
        id_column = next(c for c in inspector.get_columns(table) if c["name"] == "id")
        assert str(id_column["type"]).upper() == "UUID", table


def test_activity_logs_have_no_foreign_keys_and_a_metadata_column(engine: Engine) -> None:
    inspector = inspect(engine)

    assert inspector.get_foreign_keys("activity_logs") == []
    assert "metadata" in {c["name"] for c in inspector.get_columns("activity_logs")}
