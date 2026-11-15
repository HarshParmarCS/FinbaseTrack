"""The facts a policy decision is based on.

Frozen dataclasses with no ORM or HTTP types, so the engine can be tested without a database
and cannot be influenced by lazy loading or stale ORM objects. The policy information point
(information.py) fills them from the current database state.
"""

import uuid
from dataclasses import dataclass, fields, replace
from datetime import date
from typing import Final


class _Unset:
    """Marks a field the request does not change (None is a valid new value, e.g. unassign)."""

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = _Unset()


@dataclass(frozen=True, slots=True)
class Subject:
    """The authenticated user, taken from the verified JWT and the database."""

    id: uuid.UUID
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class ProjectFacts:
    id: uuid.UUID
    owner_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class TaskFacts:
    project_id: uuid.UUID
    creator_id: uuid.UUID
    assignee_id: uuid.UUID | None
    status: str
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    due_date: date | None = None
    id: uuid.UUID | None = None  # None for a task that does not exist yet


@dataclass(frozen=True, slots=True)
class TaskChanges:
    """Requested changes to a task (create or update). UNSET means "not changed"."""

    title: str | None | _Unset = UNSET
    description: str | None | _Unset = UNSET
    priority: str | None | _Unset = UNSET
    status: str | _Unset = UNSET
    due_date: date | None | _Unset = UNSET
    assignee_id: uuid.UUID | None | _Unset = UNSET

    def apply(self, base: TaskFacts) -> TaskFacts:
        """The task as it would be after the change (the "resulting state")."""
        updates = {
            f.name: getattr(self, f.name)
            for f in fields(self)
            if not isinstance(getattr(self, f.name), _Unset)
        }
        if "status" in updates:
            updates["status"] = str(updates["status"])
        if "priority" in updates and updates["priority"] is not None:
            updates["priority"] = str(updates["priority"])
        return replace(base, **updates)


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    subject: Subject
    action: str
    project: ProjectFacts | None = None
    # Current membership of the subject in `project`, read from the database for this decision.
    is_project_member: bool = False
    # The stored task (None when creating or when the action is not about a task).
    task: TaskFacts | None = None
    # The task after the requested change (None when nothing is being changed).
    proposed_task: TaskFacts | None = None
    # Is the assignee of the resulting task currently a member of the project?
    assignee_is_project_member: bool = False

    @property
    def resulting_task(self) -> TaskFacts | None:
        """What the task will look like if the action is allowed."""
        return self.proposed_task if self.proposed_task is not None else self.task
