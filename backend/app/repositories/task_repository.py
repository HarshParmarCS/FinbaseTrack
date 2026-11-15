"""Task database access. Queries only: no business rules, no authorization, no commits."""

import uuid
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any

from sqlalchemy import ColumnElement, Select, case, func, or_, select, update
from sqlalchemy.orm import Session, aliased

from app.models import Task, TaskPriority, TaskStatus, User

UNASSIGNED = "unassigned"


class TaskSort(StrEnum):
    """The ONLY sort orders a client may request (an explicit allow-list)."""

    CREATED_AT = "created_at"
    CREATED_AT_DESC = "-created_at"
    UPDATED_AT = "updated_at"
    UPDATED_AT_DESC = "-updated_at"
    DUE_DATE = "due_date"
    DUE_DATE_DESC = "-due_date"
    PRIORITY = "priority"
    PRIORITY_DESC = "-priority"
    POSITION = "position"


@dataclass(frozen=True, slots=True)
class TaskFilters:
    q: str | None = None
    statuses: tuple[TaskStatus, ...] = ()
    priorities: tuple[TaskPriority, ...] = ()
    assignee_id: uuid.UUID | None = None
    unassigned: bool = False
    due_after: date | None = None
    due_before: date | None = None
    overdue: bool | None = None
    today: date | None = None  # required when `overdue` is set


@dataclass(frozen=True, slots=True)
class TaskRow:
    """A task with its creator and assignee, loaded by one query."""

    task: Task
    creator: User
    assignee: User | None


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _priority_rank() -> ColumnElement[int]:
    return case(
        (Task.priority == TaskPriority.LOW, 1),
        (Task.priority == TaskPriority.MEDIUM, 2),
        (Task.priority == TaskPriority.HIGH, 3),
    )


def _order_by(sort: TaskSort) -> list[Any]:
    """Explicit ordering. The id is always the final tie-breaker, so pages are stable."""
    match sort:
        case TaskSort.CREATED_AT:
            keys: list[Any] = [Task.created_at.asc()]
        case TaskSort.CREATED_AT_DESC:
            keys = [Task.created_at.desc()]
        case TaskSort.UPDATED_AT:
            keys = [Task.updated_at.asc()]
        case TaskSort.UPDATED_AT_DESC:
            keys = [Task.updated_at.desc()]
        case TaskSort.DUE_DATE:
            keys = [Task.due_date.asc().nulls_last()]
        case TaskSort.DUE_DATE_DESC:
            keys = [Task.due_date.desc().nulls_last()]
        case TaskSort.PRIORITY:
            keys = [_priority_rank().asc()]
        case TaskSort.PRIORITY_DESC:
            keys = [_priority_rank().desc()]
        case TaskSort.POSITION:
            keys = [Task.position.asc()]
    return [*keys, Task.id.asc()]


class TaskRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- reads --------------------------------------------------------------------------

    def _rows_select(self) -> Select[Any]:
        creator = aliased(User)
        assignee = aliased(User)
        return (
            select(Task, creator, assignee)
            .join(creator, creator.id == Task.creator_id)
            .outerjoin(assignee, assignee.id == Task.assignee_id)
            .execution_options(populate_existing=True)  # never serve stale cached columns
        )

    def get(self, task_id: uuid.UUID, *, for_update: bool = False) -> Task | None:
        statement = select(Task).where(Task.id == task_id)
        statement = statement.execution_options(populate_existing=True)
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalars(statement).first()

    def get_row(self, task_id: uuid.UUID) -> TaskRow | None:
        row = self.db.execute(self._rows_select().where(Task.id == task_id)).first()
        return TaskRow(row[0], row[1], row[2]) if row else None

    def list_rows(
        self,
        project_id: uuid.UUID,
        filters: TaskFilters,
        sort: TaskSort,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[TaskRow], int]:
        """One page of a project's tasks plus the total: two queries, whatever the page size."""
        conditions = self._conditions(project_id, filters)
        total = self.db.scalar(select(func.count()).select_from(Task).where(*conditions))
        rows = self.db.execute(
            self._rows_select()
            .where(*conditions)
            .order_by(*_order_by(sort))
            .offset(offset)
            .limit(limit)
        ).all()
        return [TaskRow(r[0], r[1], r[2]) for r in rows], int(total or 0)

    @staticmethod
    def _conditions(project_id: uuid.UUID, f: TaskFilters) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = [Task.project_id == project_id]
        if f.q:
            pattern = f"%{_escape_like(f.q)}%"
            conditions.append(
                or_(
                    Task.title.ilike(pattern, escape="\\"),
                    Task.description.ilike(pattern, escape="\\"),
                )
            )
        if f.statuses:
            conditions.append(Task.status.in_(f.statuses))
        if f.priorities:
            conditions.append(Task.priority.in_(f.priorities))
        if f.unassigned:
            conditions.append(Task.assignee_id.is_(None))
        elif f.assignee_id is not None:
            conditions.append(Task.assignee_id == f.assignee_id)
        if f.due_after is not None:
            conditions.append(Task.due_date >= f.due_after)
        if f.due_before is not None:
            conditions.append(Task.due_date <= f.due_before)
        if f.overdue is not None:
            if f.today is None:
                raise ValueError("'today' is required to filter on overdue")
            is_overdue = (Task.due_date < f.today) & (Task.status != TaskStatus.COMPLETED)
            conditions.append(
                is_overdue if f.overdue else or_(Task.due_date.is_(None), ~is_overdue)
            )
        return conditions

    def next_position(self, project_id: uuid.UUID, status: TaskStatus) -> float:
        """A position that places a task at the end of its status column."""
        highest = self.db.scalar(
            select(func.max(Task.position)).where(
                Task.project_id == project_id, Task.status == status
            )
        )
        return float(highest) + 1024.0 if highest is not None else 1024.0

    # ---- writes -------------------------------------------------------------------------

    def add(self, task: Task) -> Task:
        self.db.add(task)
        self.db.flush()
        return task

    def delete(self, task: Task) -> None:
        self.db.delete(task)
        self.db.flush()

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
