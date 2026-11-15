"""Activity log persistence. Append-only."""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session

from app.models import ActivityLog, ProjectMember, User
from app.models.enums import ActivityAction


class ActivityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        user_id: uuid.UUID,
        action: ActivityAction,
        project_id: uuid.UUID | None = None,
        task_id: uuid.UUID | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Add an entry in the caller's transaction (it commits or rolls back with the change).

        ``meta`` must be JSON-serializable and must never contain secrets.
        """
        self.db.add(
            ActivityLog(
                user_id=user_id,
                project_id=project_id,
                task_id=task_id,
                action=action.value,
                meta=meta or {},
            )
        )


@dataclass(frozen=True, slots=True)
class ActivityRow:
    """An activity entry with the user who acted (one query, no N+1)."""

    entry: ActivityLog
    user: User


def _member_project_ids(user_id: uuid.UUID) -> Select[tuple[uuid.UUID]]:
    """Projects the user is a CURRENT member of: removed members lose the feed immediately."""
    return select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)


class ActivityQueries:
    """Read side of the activity log. Entries without a project (auth events) never appear."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _rows(self, scope: ColumnElement[bool], *, offset: int, limit: int) -> list[ActivityRow]:
        rows = self.db.execute(
            select(ActivityLog, User)
            .join(User, User.id == ActivityLog.user_id)
            .where(scope)
            .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return [ActivityRow(entry, user) for entry, user in rows]

    def _total(self, scope: ColumnElement[bool]) -> int:
        return int(self.db.scalar(select(func.count()).select_from(ActivityLog).where(scope)) or 0)

    def for_project(
        self, project_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[ActivityRow], int]:
        scope = ActivityLog.project_id == project_id
        return self._rows(scope, offset=offset, limit=limit), self._total(scope)

    def for_member(
        self, user_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[ActivityRow], int]:
        """Activity in every project the user currently belongs to, newest first."""
        scope = ActivityLog.project_id.in_(_member_project_ids(user_id))
        return self._rows(scope, offset=offset, limit=limit), self._total(scope)
