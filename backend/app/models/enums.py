"""Enumerations stored as constrained varchar columns (not native PostgreSQL enums)."""

from enum import StrEnum
from typing import Any

from sqlalchemy import Enum


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def enum_column_type(enum_class: type[StrEnum]) -> Enum:
    """Column type that stores the enum VALUE ("in_progress") as varchar(20).

    The CHECK constraint is declared explicitly on each table (see ``in_values_check``)
    so that it is visible in the model and in the migration.
    """

    def values(members: type[Any]) -> list[str]:
        return [member.value for member in members]

    return Enum(
        enum_class,
        native_enum=False,
        create_constraint=False,
        length=20,
        values_callable=values,
        validate_strings=True,
    )


def in_values_check(column: str, enum_class: type[StrEnum]) -> str:
    """SQL text for ``column IN ('a', 'b')``. Values come from our own enums, never from users."""
    quoted = ", ".join(f"'{member.value}'" for member in enum_class)
    return f"{column} IN ({quoted})"


class ActivityAction(StrEnum):
    """Actions recorded in activity_logs (see docs/database-design.md)."""

    USER_REGISTERED = "user.registered"
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_REFRESH_REUSE_DETECTED = "auth.refresh_reuse_detected"
    PROJECT_CREATED = "project.created"
    PROJECT_UPDATED = "project.updated"
    PROJECT_DELETED = "project.deleted"
    MEMBER_ADDED = "member.added"
    MEMBER_REMOVED = "member.removed"
    TASK_CREATED = "task.created"
    TASK_UPDATED = "task.updated"
    TASK_STATUS_CHANGED = "task.status_changed"
    TASK_ASSIGNED = "task.assigned"
    TASK_UNASSIGNED = "task.unassigned"
    TASK_DELETED = "task.deleted"
