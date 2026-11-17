"""Task business logic.

Order of checks for every operation (so each failure has one clear status code):

1. ``AuthorizationService.require(...)``: 404 for non-members and missing tasks, 403 when a
   member is denied by a policy. The decision is made by the policy engine, never here.
2. Business rules: assignee must be a project member, status transition must be valid (422).
3. ``require_completion_if_completed``: a task that is (or becomes) completed must satisfy the
   ``task.complete`` policy (403).
4. The change, its activity entry and the commit, in ONE transaction.
"""

import logging
import uuid
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.authorization.context import ProjectFacts, TaskChanges, TaskFacts
from app.authorization.policies import Action
from app.authorization.service import AuthorizationService
from app.core.clock import utcnow
from app.core.exceptions import BusinessRuleViolation, NotFoundError
from app.models import Project, Task, TaskStatus, User
from app.models.enums import ActivityAction
from app.repositories.activity_repository import ActivityRepository
from app.repositories.project_member_repository import ProjectMemberRepository
from app.repositories.task_repository import TaskFilters, TaskRepository, TaskRow, TaskSort
from app.schemas.task import TaskCreate, TaskStatusUpdate, TaskUpdate

logger = logging.getLogger(__name__)

# The workflow is a line: todo <-> in_progress <-> completed.
# todo <-> completed directly is not allowed (move through in_progress).
ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.TODO: frozenset({TaskStatus.IN_PROGRESS}),
    TaskStatus.IN_PROGRESS: frozenset({TaskStatus.TODO, TaskStatus.COMPLETED}),
    TaskStatus.COMPLETED: frozenset({TaskStatus.IN_PROGRESS}),
}

ASSIGNEE_NOT_MEMBER = "The assignee must be a member of the project."
_ALLOWED_ACTION_NAMES: dict[Action, str] = {
    Action.TASK_UPDATE: "update",
    Action.TASK_DELETE: "delete",
    Action.TASK_COMPLETE: "complete",
}
_DISPLAY_LIMIT = 200  # long text values are shortened in activity metadata


@dataclass(frozen=True, slots=True)
class TaskItem:
    row: TaskRow
    allowed_actions: list[str]


@dataclass(frozen=True, slots=True)
class TaskPage:
    items: list[TaskItem]
    total: int


@dataclass(frozen=True, slots=True)
class AssignedTaskItem:
    item: TaskItem
    project: Project


@dataclass(frozen=True, slots=True)
class AssignedTaskPage:
    items: list[AssignedTaskItem]
    total: int


def _facts(task: Task) -> TaskFacts:
    return TaskFacts(
        id=task.id,
        project_id=task.project_id,
        creator_id=task.creator_id,
        assignee_id=task.assignee_id,
        status=str(task.status),
        title=task.title,
        description=task.description,
        priority=str(task.priority),
        due_date=task.due_date,
    )


def _plain(value: object) -> object:
    """JSON-friendly form of a value for activity metadata."""
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and len(value) > _DISPLAY_LIMIT:
        return value[:_DISPLAY_LIMIT] + "..."
    return str(value) if hasattr(value, "value") else value  # enums -> their string value


class TaskService:
    def __init__(
        self,
        db: Session,
        tasks: TaskRepository,
        members: ProjectMemberRepository,
        activity: ActivityRepository,
        authz: AuthorizationService,
    ) -> None:
        self.db = db
        self.tasks = tasks
        self.members = members
        self.activity = activity
        self.authz = authz

    # ---- create ---------------------------------------------------------------------------

    def create_task(self, user: User, project_id: uuid.UUID, data: TaskCreate) -> TaskItem:
        changes = TaskChanges(
            title=data.title,
            description=data.description,
            priority=data.priority.value,
            status=data.status.value,
            due_date=data.due_date,
            assignee_id=data.assignee_id,
        )
        ctx = self.authz.require(user, Action.TASK_CREATE, project_id=project_id, changes=changes)
        assert ctx.project is not None
        self._ensure_assignee_is_member(project_id, data.assignee_id)
        self.authz.require_completion_if_completed(ctx)

        task = Task(
            project_id=project_id,
            title=data.title,
            description=data.description,
            status=data.status,
            priority=data.priority,
            creator_id=user.id,  # always the authenticated user, never taken from the request
            assignee_id=data.assignee_id,
            due_date=data.due_date,
            position=self.tasks.next_position(project_id, data.status),
            completed_at=utcnow() if data.status is TaskStatus.COMPLETED else None,
        )
        with self._translate_integrity_errors():
            self.tasks.add(task)
            self.activity.record(
                user_id=user.id,
                action=ActivityAction.TASK_CREATED,
                project_id=project_id,
                task_id=task.id,
                meta={
                    "title": _plain(task.title),
                    "status": _plain(task.status),
                    "priority": _plain(task.priority),
                    "assignee_id": _plain(task.assignee_id),
                },
            )
            self.db.commit()
        logger.info("Task created task_id=%s project_id=%s", task.id, project_id)
        return self._item(user, ctx.project, task.id)

    # ---- read -----------------------------------------------------------------------------

    def list_tasks(
        self,
        user: User,
        project_id: uuid.UUID,
        filters: TaskFilters,
        sort: TaskSort,
        *,
        offset: int,
        limit: int,
    ) -> TaskPage:
        ctx = self.authz.require(user, Action.PROJECT_VIEW, project_id=project_id)
        assert ctx.project is not None
        if filters.overdue is not None:
            filters = replace(filters, today=utcnow().date())  # "today" in UTC
        rows, total = self.tasks.list_rows(project_id, filters, sort, offset=offset, limit=limit)
        return TaskPage([self._to_item(user, ctx.project, row) for row in rows], total)

    def list_assigned_tasks(
        self,
        user: User,
        filters: TaskFilters,
        sort: TaskSort,
        *,
        project_id: uuid.UUID | None,
        offset: int,
        limit: int,
    ) -> AssignedTaskPage:
        """The caller's assigned tasks across their projects.

        Data scoping, not a policy decision (like the project list and the dashboard): the
        repository returns only tasks in projects the caller is a current member of. The
        ``allowed_actions`` of each task still come from the policy engine.
        """
        if filters.overdue is not None:
            filters = replace(filters, today=utcnow().date())  # "today" in UTC
        rows, total = self.tasks.list_assigned_rows(
            user.id, filters, sort, project_id=project_id, offset=offset, limit=limit
        )
        items = [
            AssignedTaskItem(
                self._to_item(
                    user, ProjectFacts(id=r.project.id, owner_id=r.project.owner_id), r.row
                ),
                r.project,
            )
            for r in rows
        ]
        return AssignedTaskPage(items, total)

    def get_task(self, user: User, task_id: uuid.UUID) -> TaskItem:
        # Reading a task is reading its project: the PIP finds the project from the task itself.
        ctx = self.authz.require(user, Action.PROJECT_VIEW, task_id=task_id)
        assert ctx.project is not None
        return self._item(user, ctx.project, task_id)

    # ---- update (never touches status) ---------------------------------------------------------

    def update_task(self, user: User, task_id: uuid.UUID, data: TaskUpdate) -> TaskItem:
        provided = data.model_fields_set
        requested: dict[str, Any] = {name: _plain_input(getattr(data, name)) for name in provided}
        changes = TaskChanges(**requested)
        ctx = self.authz.require(user, Action.TASK_UPDATE, task_id=task_id, changes=changes)
        assert ctx.project is not None
        if "assignee_id" in provided:
            self._ensure_assignee_is_member(ctx.project.id, data.assignee_id)
        # A task that is already completed must stay complete after the edit.
        self.authz.require_completion_if_completed(ctx)

        task = self.tasks.get(task_id, for_update=True)
        if task is None:  # deleted by someone else between the check and now
            raise NotFoundError()

        old_assignee = task.assignee_id
        diffs: dict[str, list[object]] = {}
        with self._translate_integrity_errors():
            for field in provided:
                new_value = getattr(data, field)
                old_value = getattr(task, field)
                if new_value != old_value:
                    diffs[field] = [_plain(old_value), _plain(new_value)]
                    setattr(task, field, new_value)

            assignee_diff = diffs.pop("assignee_id", None)
            if diffs:
                self.db.flush()
                self._record(user, task, ActivityAction.TASK_UPDATED, {"changes": diffs})
            if assignee_diff is not None:
                self._record_assignment(user, task, old_assignee)
            self.db.commit()
        logger.info("Task updated task_id=%s fields=%s", task_id, sorted(provided))
        return self._item(user, ctx.project, task_id)

    # ---- status ---------------------------------------------------------------------------

    def change_status(self, user: User, task_id: uuid.UUID, data: TaskStatusUpdate) -> TaskItem:
        """Move a task between statuses (the only way to change status)."""
        changes = TaskChanges(status=data.status.value)
        ctx = self.authz.require(user, Action.TASK_UPDATE, task_id=task_id, changes=changes)
        assert ctx.project is not None

        task = self.tasks.get(task_id, for_update=True)
        if task is None:
            raise NotFoundError()
        previous = task.status
        target = data.status
        self._ensure_valid_transition(previous, target, data.position)
        # Entering (or staying in) completed needs the assignee and every required field.
        self.authz.require_completion_if_completed(ctx)

        # Decide the position first: it is a query, and must not see the half-changed task.
        if data.position is not None:
            position = data.position
        elif target is not previous:
            position = self.tasks.next_position(task.project_id, target)
        else:
            position = task.position

        task.status = target
        task.completed_at = utcnow() if target is TaskStatus.COMPLETED else None
        task.position = position
        self.db.flush()
        self._record(
            user,
            task,
            ActivityAction.TASK_STATUS_CHANGED,
            {"from": _plain(previous), "to": _plain(target), "position": task.position},
        )
        self.db.commit()
        logger.info("Task status changed task_id=%s %s -> %s", task_id, previous, target)
        return self._item(user, ctx.project, task_id)

    # ---- delete ---------------------------------------------------------------------------

    def delete_task(self, user: User, task_id: uuid.UUID) -> None:
        """Only the project owner, and only while the task is todo (policy ``task.delete``)."""
        ctx = self.authz.require(user, Action.TASK_DELETE, task_id=task_id)
        assert ctx.project is not None

        task = self.tasks.get(task_id, for_update=True)
        if task is None:
            raise NotFoundError()
        # The history outlives the task: activity_logs has no foreign keys.
        self._record(
            user,
            task,
            ActivityAction.TASK_DELETED,
            {"title": _plain(task.title), "status": _plain(task.status)},
        )
        self.tasks.delete(task)
        self.db.commit()
        logger.info("Task deleted task_id=%s project_id=%s", task_id, ctx.project.id)

    # ---- helpers --------------------------------------------------------------------------

    def _ensure_assignee_is_member(
        self, project_id: uuid.UUID, assignee_id: uuid.UUID | None
    ) -> None:
        if assignee_id is None:
            return
        if self.members.get(project_id, assignee_id) is None:
            raise BusinessRuleViolation(ASSIGNEE_NOT_MEMBER)

    @staticmethod
    def _ensure_valid_transition(
        current: TaskStatus, target: TaskStatus, position: float | None
    ) -> None:
        if target is current:
            if position is None:
                raise BusinessRuleViolation(f"The task is already {current.value}.")
            return  # same column, new position: a reorder
        if target not in ALLOWED_TRANSITIONS[current]:
            allowed = ", ".join(sorted(s.value for s in ALLOWED_TRANSITIONS[current]))
            raise BusinessRuleViolation(
                f"A task cannot move from {current.value} to {target.value}. "
                f"Allowed from {current.value}: {allowed}."
            )

    def _record(self, user: User, task: Task, action: ActivityAction, meta: dict[str, Any]) -> None:
        self.activity.record(
            user_id=user.id,
            action=action,
            project_id=task.project_id,
            task_id=task.id,
            meta=meta,
        )

    def _record_assignment(self, user: User, task: Task, previous: uuid.UUID | None) -> None:
        if task.assignee_id is None:
            self._record(
                user,
                task,
                ActivityAction.TASK_UNASSIGNED,
                {"previous_assignee_id": _plain(previous)},
            )
        else:
            self._record(
                user,
                task,
                ActivityAction.TASK_ASSIGNED,
                {"assignee_id": _plain(task.assignee_id), "previous_assignee_id": _plain(previous)},
            )

    def _item(self, user: User, project: ProjectFacts, task_id: uuid.UUID) -> TaskItem:
        row = self.tasks.get_row(task_id)
        if row is None:
            raise NotFoundError()
        return self._to_item(user, project, row)

    def _to_item(self, user: User, project: ProjectFacts, row: TaskRow) -> TaskItem:
        # The caller is a member: the project was authorized before any task was read.
        allowed = self.authz.allowed_task_actions(user, project, _facts(row.task), is_member=True)
        names = [name for action, name in _ALLOWED_ACTION_NAMES.items() if action in allowed]
        # Completing a task is a status update PLUS the completion policy, so the UI may only
        # offer "complete" when BOTH would pass.
        if "complete" in names and "update" not in names:
            names.remove("complete")
        return TaskItem(row, names)

    @staticmethod
    def _translate_integrity_errors() -> "_IntegrityTranslator":
        return _IntegrityTranslator()


class _IntegrityTranslator:
    """Turn a database constraint failure from a race into the right domain error.

    The checks above are the normal path. These cover the instant between a check and the
    commit (for example the project was deleted, or the assignee was removed meanwhile).
    """

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: Any, exc: BaseException | None, tb: Any) -> None:
        if not isinstance(exc, IntegrityError):
            return  # not ours: the original exception continues
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if constraint == "fk_tasks_project_id_projects":
            raise NotFoundError() from exc
        if constraint == "fk_tasks_assignee_member":
            raise BusinessRuleViolation(ASSIGNEE_NOT_MEMBER) from exc


def _plain_input(value: object) -> object:
    """Request values as plain data for the policy context (enums become their string)."""
    return value.value if hasattr(value, "value") else value
