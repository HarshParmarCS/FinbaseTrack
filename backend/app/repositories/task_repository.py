"""Task database access needed by project management (task APIs come in a later milestone)."""

import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Task


class TaskRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def unassign_user_in_project(
        self, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[uuid.UUID]:
        """Clear the assignee on every task of the project assigned to ``user_id``.

        Returns the IDs of the affected tasks. Runs inside the caller's transaction and must run
        BEFORE the membership row is deleted: the composite foreign key
        ``(project_id, assignee_id) -> project_members`` refuses to remove a member who still has
        assigned tasks.
        """
        affected = list(
            self.db.scalars(
                select(Task.id).where(Task.project_id == project_id, Task.assignee_id == user_id)
            )
        )
        if affected:
            self.db.execute(
                update(Task)
                .where(Task.project_id == project_id, Task.assignee_id == user_id)
                .values(assignee_id=None)
                .execution_options(synchronize_session="fetch")
            )
        return affected
