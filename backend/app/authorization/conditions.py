"""Reusable boolean conditions and the SAFE condition registry.

A condition is a pure function ``(context, **params) -> bool``. It only reads the context
(facts already loaded from the database) and never writes, raises HTTP errors or does I/O.

``policies.json`` can only SELECT a condition by name from ``CONDITIONS`` below and pass
parameters that the condition's validators accept. The JSON never contains code, and nothing
here uses eval/exec/dynamic imports. Anything not registered is rejected at load time.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.authorization.context import AuthorizationContext, TaskFacts
from app.models.enums import TaskStatus

ConditionFunc = Callable[..., bool]
ParamValidator = Callable[[Any], Any]  # returns the normalized value, raises ValueError if bad

# Names of the task fields that "complete information" can require.
REQUIRED_FIELD_NAMES: frozenset[str] = frozenset(
    {"title", "description", "priority", "due_date", "assignee"}
)


@dataclass(frozen=True)
class ConditionSpec:
    name: str
    func: ConditionFunc
    params: Mapping[str, ParamValidator]

    def validate_params(self, given: Mapping[str, Any]) -> dict[str, Any]:
        """Check parameter names and values. Raises ValueError with a clear message."""
        unknown = set(given) - set(self.params)
        if unknown:
            raise ValueError(f"unknown parameter(s) {sorted(unknown)} for condition '{self.name}'")
        missing = set(self.params) - set(given)
        if missing:
            raise ValueError(f"missing parameter(s) {sorted(missing)} for condition '{self.name}'")
        return {key: self.params[key](value) for key, value in given.items()}


CONDITIONS: dict[str, ConditionSpec] = {}


def condition(
    name: str, params: Mapping[str, ParamValidator] | None = None
) -> Callable[[ConditionFunc], ConditionFunc]:
    """Register a condition under a fixed name."""

    def register(func: ConditionFunc) -> ConditionFunc:
        if name in CONDITIONS:
            raise RuntimeError(f"Condition '{name}' is registered twice")
        CONDITIONS[name] = ConditionSpec(name=name, func=func, params=params or {})
        return func

    return register


# ---- parameter validators -------------------------------------------------------------------


def _task_status(value: Any) -> str:
    if not isinstance(value, str) or value not in {s.value for s in TaskStatus}:
        raise ValueError(f"'value' must be one of {[s.value for s in TaskStatus]}")
    return value


def _required_fields(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("'fields' must be a non-empty list")
    if not all(isinstance(item, str) for item in value):
        raise ValueError("'fields' must contain only strings")
    unknown = set(value) - REQUIRED_FIELD_NAMES
    if unknown:
        raise ValueError(
            f"unknown field(s) {sorted(unknown)}; allowed: {sorted(REQUIRED_FIELD_NAMES)}"
        )
    if len(set(value)) != len(value):
        raise ValueError("'fields' must not contain duplicates")
    return tuple(value)


# ---- conditions -------------------------------------------------------------------------------


@condition("is_authenticated")
def is_authenticated(ctx: AuthorizationContext) -> bool:
    """The subject is an active user. (Identity itself is established by the verified JWT.)"""
    return ctx.subject.is_active


@condition("is_project_member")
def is_project_member(ctx: AuthorizationContext) -> bool:
    """The subject is currently a member of the project."""
    return ctx.project is not None and ctx.is_project_member


@condition("is_project_owner")
def is_project_owner(ctx: AuthorizationContext) -> bool:
    """The subject owns the project AND is still a member (owners are always members)."""
    return (
        ctx.project is not None and ctx.is_project_member and ctx.project.owner_id == ctx.subject.id
    )


@condition("is_task_creator")
def is_task_creator(ctx: AuthorizationContext) -> bool:
    return ctx.task is not None and ctx.task.creator_id == ctx.subject.id


@condition("is_task_assignee")
def is_task_assignee(ctx: AuthorizationContext) -> bool:
    return (
        ctx.task is not None
        and ctx.task.assignee_id is not None
        and ctx.task.assignee_id == ctx.subject.id
    )


@condition("task_status_is", params={"value": _task_status})
def task_status_is(ctx: AuthorizationContext, *, value: str) -> bool:
    """The STORED task currently has this status."""
    return ctx.task is not None and str(ctx.task.status) == value


@condition("task_has_assignee")
def task_has_assignee(ctx: AuthorizationContext) -> bool:
    """The resulting task has an assignee, and that assignee is a current project member."""
    task = ctx.resulting_task
    return task is not None and task.assignee_id is not None and ctx.assignee_is_project_member


def _is_filled(task: TaskFacts, field: str) -> bool:
    if field == "assignee":
        return task.assignee_id is not None
    value: str | date | None = getattr(task, field)
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


@condition("task_required_fields_complete", params={"fields": _required_fields})
def task_required_fields_complete(ctx: AuthorizationContext, *, fields: tuple[str, ...]) -> bool:
    """Every listed field of the RESULTING task is filled in (text must not be blank)."""
    task = ctx.resulting_task
    return task is not None and all(_is_filled(task, field) for field in fields)
