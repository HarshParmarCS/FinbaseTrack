"""Authentication request and response schemas (see docs/api-contract.md)."""

import uuid
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
)


def _normalize_email(value: str) -> str:
    """Single place where emails are normalized: trimmed and lowercase (matches the DB check)."""
    return value.strip().lower()


# EmailStr validates the address; the validator then lowercases the WHOLE address.
NormalizedEmail = Annotated[EmailStr, AfterValidator(_normalize_email)]


class _StrictModel(BaseModel):
    # Unknown fields (for example user_id or is_active) are rejected with 422, never ignored.
    model_config = ConfigDict(extra="forbid")


class RegisterIn(_StrictModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    email: NormalizedEmail = Field(max_length=255)
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)]


class LoginIn(_StrictModel):
    email: NormalizedEmail = Field(max_length=255)
    # No minimum here: a short wrong password must give the same generic 401, not a 422 hint.
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
