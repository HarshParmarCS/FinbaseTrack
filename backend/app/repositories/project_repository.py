"""Project database access. Queries only: no business rules, no authorization, no commits."""

import uuid
from dataclasses import dataclass

from sqlalchemy import ScalarSelect, Select, delete, func, select
from sqlalchemy.orm import Session

from app.models import Project, ProjectMember, ProjectStatus, Task, TaskStatus, User


@dataclass(frozen=True, slots=True)
class TaskCounts:
    todo: int = 0
    in_progress: int = 0
    completed: int = 0


@dataclass(frozen=True, slots=True)
class ProjectSummary:
    """A project with its owner and counters, loaded by ONE query."""

    project: Project
    owner: User
    member_count: int
    task_counts: TaskCounts


def _escape_like(text: str) -> str:
    """Make %, _ and the escape character match literally in a LIKE pattern."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _task_count(status: TaskStatus) -> ScalarSelect[int]:
    return (
        select(func.count())
        .select_from(Task)
        .where(Task.project_id == Project.id, Task.status == status)
        .correlate(Project)
        .scalar_subquery()
    )


def _summary_select() -> Select[tuple[Project, User, int, int, int, int]]:
    """Project + owner + member and task counters in a single statement (no N+1).

    The counters are correlated scalar subqueries. They run inside the same SQL statement,
    served by the (project_id, ...) indexes, so the cost is bounded by the page size.
    """
    member_count = (
        select(func.count())
        .select_from(ProjectMember)
        .where(ProjectMember.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )
    return (
        select(
            Project,
            User,
            member_count,
            _task_count(TaskStatus.TODO),
            _task_count(TaskStatus.IN_PROGRESS),
            _task_count(TaskStatus.COMPLETED),
        )
        .join(User, User.id == Project.owner_id)
        .execution_options(populate_existing=True)  # never serve counters/fields from a stale cache
    )


def _to_summary(row: tuple[Project, User, int, int, int, int]) -> ProjectSummary:
    project, owner, members, todo, in_progress, completed = row
    return ProjectSummary(project, owner, members, TaskCounts(todo, in_progress, completed))


class ProjectRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, project: Project) -> Project:
        """Insert the project (and any members attached to it) in the current transaction."""
        self.db.add(project)
        self.db.flush()
        return project

    def get(self, project_id: uuid.UUID, *, for_update: bool = False) -> Project | None:
        statement = select(Project).where(Project.id == project_id)
        statement = statement.execution_options(populate_existing=True)
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalars(statement).first()

    def get_summary(self, project_id: uuid.UUID) -> ProjectSummary | None:
        row = self.db.execute(_summary_select().where(Project.id == project_id)).first()
        return _to_summary(tuple(row)) if row else None

    def list_summaries_for_member(
        self,
        user_id: uuid.UUID,
        *,
        q: str | None,
        status: ProjectStatus | None,
        offset: int,
        limit: int,
    ) -> tuple[list[ProjectSummary], int]:
        """Projects the user is a CURRENT member of, newest activity first, plus the total."""
        filters = [ProjectMember.user_id == user_id]
        if q:
            filters.append(Project.name.ilike(f"%{_escape_like(q)}%", escape="\\"))
        if status is not None:
            filters.append(Project.status == status)

        total = self.db.scalar(
            select(func.count())
            .select_from(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(*filters)
        )
        rows = self.db.execute(
            _summary_select()
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(*filters)
            .order_by(Project.updated_at.desc(), Project.id)
            .offset(offset)
            .limit(limit)
        ).all()
        return [_to_summary(tuple(row)) for row in rows], int(total or 0)

    def delete(self, project: Project) -> None:
        """Delete the project row with ONE explicit statement.

        Members and tasks go with it through the database's ON DELETE CASCADE. A Core DELETE is
        used on purpose: an ORM delete would also delete any already-loaded child rows one by
        one (and in the wrong order for the assignee foreign key).
        """
        project_id = project.id
        self.db.execute(delete(Project).where(Project.id == project_id))
        self.db.expunge(project)
        self.db.expire_all()  # loaded children now refer to rows the database has removed
