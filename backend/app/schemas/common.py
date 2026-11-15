"""Shared response envelopes (see docs/api-contract.md, section 1)."""

import math
from typing import Annotated

from fastapi import Depends, Query
from fastapi.exceptions import RequestValidationError
from pydantic import AfterValidator, BaseModel


def reject_nul(value: str | None) -> str | None:
    """PostgreSQL text cannot store NUL (0x00): reject it as a validation error, not a 500."""
    if value is not None and "\x00" in value:
        raise ValueError("must not contain NUL characters")
    return value


NoNul = AfterValidator(reject_nul)


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


MAX_PAGE = 100_000  # keeps OFFSET far below the database's integer range


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
    """Query parameters shared by every list endpoint.

    ``page`` starts at 1. ``page_size`` is 1 to 100 (default 20). ``limit`` is an alias of
    ``page_size``; if both are sent they must agree.
    """

    DEFAULT_PAGE_SIZE = 20

    def __init__(
        self,
        page: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 1,
        page_size: Annotated[int | None, Query(ge=1, le=100)] = None,
        limit: Annotated[int | None, Query(ge=1, le=100, description="Alias of page_size")] = None,
    ) -> None:
        if page_size is not None and limit is not None and page_size != limit:
            raise RequestValidationError(
                [
                    {
                        "type": "value_error",
                        "loc": ("query", "limit"),
                        "msg": "'limit' is an alias of 'page_size'; send one, or the same value",
                        "input": limit,
                    }
                ]
            )
        self.page = page
        self.page_size = page_size or limit or self.DEFAULT_PAGE_SIZE

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


PaginationDep = Annotated[Pagination, Depends()]
