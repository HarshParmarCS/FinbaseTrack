"""Shared response envelopes (see docs/api-contract.md, section 1)."""

import math
from typing import Annotated

from fastapi import Depends, Query
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


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def of(cls, *, page: int, page_size: int, total: int) -> "PageMeta":
        return cls(
            page=page, page_size=page_size, total=total, total_pages=math.ceil(total / page_size)
        )


class PagedEnvelope[T](BaseModel):
    """List envelope: ``{"data": [...], "meta": {...}}``."""

    data: list[T]
    meta: PageMeta


class Pagination:
    """Query parameters shared by every list endpoint (``page`` from 1, ``page_size`` 1 to 100)."""

    def __init__(
        self,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


PaginationDep = Annotated[Pagination, Depends()]
