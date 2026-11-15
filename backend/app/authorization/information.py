"""The policy information point (PIP): current facts from PostgreSQL.

Read-only. Every fact is fetched with a fresh column query for the decision being made, never
from the session's identity map, so a removed member or a changed task cannot be answered from
stale in-memory objects. Identities (project of a task, creator, assignee) come from the
database, never from the request.
"""

import uuid

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.authorization.context import (
    AuthorizationContext,
    ProjectFacts,
    Subject,
    TaskChanges,
    TaskFacts,
)
from app.core.exceptions import NotFoundError
from app.models import Project, ProjectMember, Task, User


class PolicyInformationPoint:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- single facts -------------------------------------------------------------------

    def subject(self, user: User) -> Subject:
        return Subject(id=user.id, is_active=user.is_active)

    def project_facts(self, project_id: uuid.UUID) -> ProjectFacts | None:
        row = self.db.execute(
            select(Project.id, Project.owner_id).where(Project.id == project_id)
        ).first()
        return ProjectFacts(id=row.id, owner_id=row.owner_id) if row else None

    def is_member(self, project_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return bool(
            self.db.scalar(
                select(
                    exists().where(
                        ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
                    )
                )
            )
        )

    def task_facts(self, task_id: uuid.UUID) -> TaskFacts | None:
        row = self.db.execute(
            select(
                Task.id,
                Task.project_id,
                Task.creator_id,
                Task.assignee_id,
                Task.status,
                Task.title,
                Task.description,
                Task.priority,
                Task.due_date,
            ).where(Task.id == task_id)
        ).first()
        if row is None:
            return None
        return TaskFacts(
            id=row.id,
            project_id=row.project_id,
            creator_id=row.creator_id,
            assignee_id=row.assignee_id,
            status=str(row.status),
            title=row.title,
            description=row.description,
            priority=str(row.priority) if row.priority is not None else None,
            due_date=row.due_date,
        )

    # ---- the context for one decision ---------------------------------------------------

    def build_context(
        self,
        user: User,
        action: str,
        *,
        project_id: uuid.UUID | None = None,
        task_id: uuid.UUID | None = None,
        changes: TaskChanges | None = None,
    ) -> AuthorizationContext:
        """Collect everything the policies need. Raises NotFoundError for unknown resources.

        Pass ``task_id`` for an existing task (its project is looked up here) or ``project_id``
        for project-level actions and task creation. Never both.
        """
        if project_id is not None and task_id is not None:
            raise ValueError("Pass either project_id or task_id, not both")

        subject = self.subject(user)
        task: TaskFacts | None = None
        if task_id is not None:
            task = self.task_facts(task_id)
            if task is None:
                raise NotFoundError()
            project_id = task.project_id  # the database decides which project a task is in

        project: ProjectFacts | None = None
        is_member = False
        if project_id is not None:
            project = self.project_facts(project_id)
            if project is None:
                raise NotFoundError()
            is_member = self.is_member(project.id, subject.id)

        proposed: TaskFacts | None = None
        if changes is not None and project is not None:
            base = task or TaskFacts(
                project_id=project.id,
                creator_id=subject.id,  # a new task is created by the authenticated user
                assignee_id=None,
                status="todo",
                priority="medium",
            )
            proposed = changes.apply(base)

        resulting = proposed or task
        assignee_is_member = (
            project is not None
            and resulting is not None
            and resulting.assignee_id is not None
            and self.is_member(project.id, resulting.assignee_id)
        )

        return AuthorizationContext(
            subject=subject,
            action=str(action),
            project=project,
            is_project_member=is_member,
            task=task,
            proposed_task=proposed,
            assignee_is_project_member=assignee_is_member,
        )
