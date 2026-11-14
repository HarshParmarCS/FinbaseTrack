"""Shared response envelopes (see docs/api-contract.md, section 1)."""

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """One field-level or policy-level error detail."""

    field: str | None = None
    message: str
    policy_id: str | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = []
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """Error envelope: ``{"error": {...}}``."""

    error: ErrorBody


class Envelope[T](BaseModel):
    """Success envelope: ``{"data": ...}``."""

    data: T
