"""initial schema

Creates users, projects, project_members, tasks, activity_logs and refresh_tokens.
Design: docs/database-design.md. Generated with `alembic revision --autogenerate`, then edited by
hand for what autogenerate cannot express: the pg_trgm extension, the circular
projects <-> project_members constraint (created last, deferrable) and creation order.

Revision ID: 4138ca71fcc2
Revises:
Create Date: 2026-11-15 02:06:50
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "4138ca71fcc2"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_DEFAULT = sa.text("gen_random_uuid()")
NOW = sa.text("now()")


def upgrade() -> None:
    # Trigram indexes for task search. Trusted extension (PostgreSQL 13+), usable by db owners.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ---- users -------------------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_users_name_not_blank")),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_users_email_lowercase")),
    )

    # ---- projects (the owner-is-a-member constraint is added after project_members) ----------
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_projects_owner_id_users"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_projects_name_not_blank")),
        sa.CheckConstraint(
            "status IN ('active', 'archived')", name=op.f("ck_projects_status_valid")
        ),
    )
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])
    op.create_index("ix_projects_status", "projects", ["status"])

    # ---- project_members ---------------------------------------------------------------------
    op.create_table(
        "project_members",
        sa.Column("id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("added_by", sa.Uuid(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_members")),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_members_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_project_members_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["added_by"],
            ["users.id"],
            name=op.f("fk_project_members_added_by_users"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),
    )
    op.create_index("ix_project_members_user_id", "project_members", ["user_id"])

    # The owner must be a member. Deferred: the project and the owner's membership row are
    # inserted in one transaction in either order, and the rule is checked at COMMIT.
    op.create_foreign_key(
        "fk_projects_owner_member",
        "projects",
        "project_members",
        ["id", "owner_id"],
        ["project_id", "user_id"],
        deferrable=True,
        initially="DEFERRED",
    )

    # ---- tasks -------------------------------------------------------------------------------
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="todo", nullable=False),
        sa.Column("priority", sa.String(length=20), server_default="medium", nullable=False),
        sa.Column("creator_id", sa.Uuid(), nullable=False),
        sa.Column("assignee_id", sa.Uuid(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("position", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_tasks_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["users.id"],
            name=op.f("fk_tasks_creator_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"],
            ["users.id"],
            name=op.f("fk_tasks_assignee_id_users"),
            ondelete="RESTRICT",
        ),
        # An assignee must be a member of the task's project (not checked while assignee_id is NULL).
        sa.ForeignKeyConstraint(
            ["project_id", "assignee_id"],
            ["project_members.project_id", "project_members.user_id"],
            name="fk_tasks_assignee_member",
        ),
        sa.CheckConstraint("length(trim(title)) > 0", name=op.f("ck_tasks_title_not_blank")),
        sa.CheckConstraint(
            "status IN ('todo', 'in_progress', 'completed')", name=op.f("ck_tasks_status_valid")
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high')", name=op.f("ck_tasks_priority_valid")
        ),
        sa.CheckConstraint(
            "(status = 'completed') = (completed_at IS NOT NULL)",
            name=op.f("ck_tasks_completed_at_matches_status"),
        ),
    )
    op.create_index(
        "ix_tasks_project_status_position", "tasks", ["project_id", "status", "position"]
    )
    op.create_index(
        "ix_tasks_project_created_at", "tasks", ["project_id", sa.text("created_at DESC")]
    )
    op.create_index("ix_tasks_project_due_date", "tasks", ["project_id", "due_date"])
    op.create_index("ix_tasks_assignee_id", "tasks", ["assignee_id"])
    op.create_index(
        "ix_tasks_title_trgm",
        "tasks",
        ["title"],
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_tasks_description_trgm",
        "tasks",
        ["description"],
        postgresql_using="gin",
        postgresql_ops={"description": "gin_trgm_ops"},
    )

    # ---- activity_logs (no foreign keys on purpose: history survives hard deletes) -----------
    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activity_logs")),
        sa.CheckConstraint(
            "length(trim(action)) > 0", name=op.f("ck_activity_logs_action_not_blank")
        ),
    )
    op.create_index(
        "ix_activity_logs_project_created",
        "activity_logs",
        ["project_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_activity_logs_user_created", "activity_logs", ["user_id", sa.text("created_at DESC")]
    )
    op.create_index(
        "ix_activity_logs_task_created", "activity_logs", ["task_id", sa.text("created_at DESC")]
    )

    # ---- refresh_tokens (only the SHA-256 hash of a token is stored) -------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("replaced_by", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by"],
            ["refresh_tokens.id"],
            name=op.f("fk_refresh_tokens_replaced_by_refresh_tokens"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
        sa.CheckConstraint(
            "length(token_hash) = 64", name=op.f("ck_refresh_tokens_token_hash_sha256_hex")
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_refresh_tokens_expires_after_creation")
        ),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])


def downgrade() -> None:
    # Dropping a table drops its indexes. The pg_trgm extension is shared and left in place.
    op.drop_table("refresh_tokens")
    op.drop_table("activity_logs")
    op.drop_table("tasks")
    op.drop_constraint("fk_projects_owner_member", "projects", type_="foreignkey")
    op.drop_table("project_members")
    op.drop_table("projects")
    op.drop_table("users")
