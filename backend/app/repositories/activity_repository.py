"""Activity log persistence. Append-only."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import ActivityLog
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
