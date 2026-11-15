"""Project and membership schemas (see docs/api-contract.md)."""

import datetime as dt
import uuid
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    StringConstraints,
    model_validator,
)

from app.models import ProjectStatus
from app.schemas.auth import NormalizedEmail, UserOut
from app.schemas.common import NoNul

ProjectAction = Literal["update", "delete", "manage_members", "create_task"]

ProjectName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120), NoNul
]


def _blank_to_none(value: str | None) -> str | None:
    return value.strip() or None if value is not None else None


Description = Annotated[
    str | None, StringConstraints(max_length=5000), NoNul, AfterValidator(_blank_to_none)
]


class _StrictModel(BaseModel):
    # Unknown fields (for example owner_id) are rejected with 422, never silently ignored.
    model_config = ConfigDict(extra="forbid")


class ProjectCreate(_StrictModel):
    name: ProjectName
    description: Description = None
    status: ProjectStatus = ProjectStatus.ACTIVE


class ProjectUpdate(_StrictModel):
    """Partial update: only the fields present in the request are changed."""

    name: ProjectName | None = None
    description: Description = None
    status: ProjectStatus | None = None

    @model_validator(mode="after")
    def validate_partial(self) -> Self:
        provided = self.model_fields_set
        if not provided:
            raise ValueError("At least one field must be provided")
        for required in ("name", "status"):  # these cannot be cleared
            if required in provided and getattr(self, required) is None:
                raise ValueError(f"'{required}' cannot be null")
        return self


class MemberCreate(_StrictModel):
    """Who to add: exactly one of ``email`` or ``user_id`` (the person added, not the caller)."""

    email: NormalizedEmail | None = None
    user_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def exactly_one_identifier(self) -> Self:
        if (self.email is None) == (self.user_id is None):
            raise ValueError("Provide exactly one of 'email' or 'user_id'")
        return self


class MemberOut(BaseModel):
    user: UserOut
    is_owner: bool
    joined_at: dt.datetime


class TaskCountsOut(BaseModel):
    todo: int
    in_progress: int
    completed: int


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    status: ProjectStatus
    owner: UserOut
    member_count: int
    task_counts: TaskCountsOut
    allowed_actions: list[ProjectAction]
    created_at: dt.datetime
    updated_at: dt.datetime


class ProjectDetailOut(ProjectOut):
    members: list[MemberOut]
