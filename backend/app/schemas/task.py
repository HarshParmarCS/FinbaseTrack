"""Task request and response schemas (see docs/api-contract.md, section 3.5)."""

import datetime as dt
import math
import uuid
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StringConstraints,
    model_validator,
)

from app.models import TaskPriority, TaskStatus
from app.schemas.auth import UserOut
from app.schemas.common import NoNul

TaskAction = Literal["update", "delete", "complete"]

TaskTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200), NoNul
]
MAX_POSITION = 1e12


def _blank_to_none(value: str | None) -> str | None:
    return (value.strip() or None) if value is not None else None


TaskDescription = Annotated[
    str | None, StringConstraints(max_length=5000), NoNul, AfterValidator(_blank_to_none)
]


class _StrictModel(BaseModel):
    # Unknown fields (creator_id, project_id, position, ...) are rejected, never silently ignored.
    model_config = ConfigDict(extra="forbid")


class TaskCreate(_StrictModel):
    title: TaskTitle
    description: TaskDescription = None
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.TODO
    assignee_id: uuid.UUID | None = None
    due_date: dt.date | None = None


class TaskUpdate(_StrictModel):
    """Partial update. Status and position are deliberately NOT here (see TaskStatusUpdate)."""

    title: TaskTitle | None = None
    description: TaskDescription = None
    priority: TaskPriority | None = None
    assignee_id: uuid.UUID | None = None
    due_date: dt.date | None = None

    @model_validator(mode="after")
    def validate_partial(self) -> Self:
        provided = self.model_fields_set
        if not provided:
            raise ValueError("At least one field must be provided")
        for required in ("title", "priority"):  # these cannot be cleared
            if required in provided and getattr(self, required) is None:
                raise ValueError(f"'{required}' cannot be null")
        return self


class TaskStatusUpdate(_StrictModel):
    status: TaskStatus
    # StrictFloat: JSON numbers only (no strings and no booleans such as `true`).
    position: (
        Annotated[StrictFloat, Field(allow_inf_nan=False, ge=-MAX_POSITION, le=MAX_POSITION)] | None
    ) = None

    @model_validator(mode="after")
    def position_is_finite(self) -> Self:
        if self.position is not None and not math.isfinite(self.position):
            raise ValueError("'position' must be a finite number")
        return self


class TaskOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    assignee: UserOut | None
    creator: UserOut
    due_date: dt.date | None
    position: float
    completed_at: dt.datetime | None
    allowed_actions: list[TaskAction]
    created_at: dt.datetime
    updated_at: dt.datetime
