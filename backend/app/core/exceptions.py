"""Domain exceptions and centralized exception handlers.

Services raise the domain exceptions below and never raise ``HTTPException``.
The handlers registered here convert every error into the error envelope
defined in docs/api-contract.md.
"""

import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.cookies import clear_auth_cookies
from app.core.logging import request_id_ctx
from app.schemas.common import ErrorBody, ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class AppError(Exception):
    """Base class for domain errors that map to an HTTP response."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"
    default_message: str = "An unexpected error occurred."
    # When true, the error response also expires the authentication cookies.
    clears_session_cookies: bool = False

    def __init__(self, message: str | None = None, details: Sequence[ErrorDetail] = ()) -> None:
        self.message = message or self.default_message
        self.details = list(details)
        super().__init__(self.message)


class UnauthenticatedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHENTICATED"
    default_message = "Authentication is required."


class SessionInvalidError(UnauthenticatedError):
    """The refresh token is unusable (missing, invalid, expired, revoked or reused).

    The client must log in again, so the response also clears the auth cookies.
    """

    clears_session_cookies = True
    default_message = "Your session is no longer valid. Please log in again."


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"
    default_message = "You are not allowed to perform this action."


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"
    default_message = "Resource not found."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"
    default_message = "The request conflicts with the current state."


class BusinessRuleViolation(AppError):  # noqa: N818  (name fixed by docs/api-contract.md)
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "BUSINESS_RULE_VIOLATION"
    default_message = "The request violates a business rule."


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Sequence[ErrorDetail] = (),
) -> JSONResponse:
    """Build the error envelope response, including the request ID."""
    request_id = request_id_ctx.get()
    body = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            details=list(details),
            request_id=None if request_id == "-" else request_id,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers={REQUEST_ID_HEADER: request_id},
    )


_HTTP_STATUS_CODES = {
    status.HTTP_401_UNAUTHORIZED: "UNAUTHENTICATED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
}


async def handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    response = error_response(exc.status_code, exc.code, exc.message, exc.details)
    if exc.clears_session_cookies:
        clear_auth_cookies(response, get_settings())
    return response


async def handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    """Framework-level HTTP errors, such as unknown routes (404) or wrong methods (405)."""
    assert isinstance(exc, StarletteHTTPException)
    code = _HTTP_STATUS_CODES.get(exc.status_code, "HTTP_ERROR")
    return error_response(exc.status_code, code, str(exc.detail))


def _format_validation_errors(errors: Sequence[Any]) -> list[ErrorDetail]:
    # The offending input value is deliberately omitted: it may contain secrets.
    details: list[ErrorDetail] = []
    for err in errors:
        location = [str(part) for part in err["loc"][1:]]  # drop "body" / "query" / "path"
        details.append(ErrorDetail(field=".".join(location) or None, message=str(err["msg"])))
    return details


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "VALIDATION_ERROR",
        "Request validation failed.",
        _format_validation_errors(exc.errors()),
    )


async def handle_data_error(request: Request, exc: Exception) -> JSONResponse:
    """The database rejected a value (bad text, out of range). A client error, never a 500.

    Defense in depth behind request validation. Only the database's one-line reason is logged:
    never the SQL parameters.
    """
    assert isinstance(exc, DataError)
    reason = str(exc.orig).splitlines()[0] if exc.orig else "data error"
    logger.warning(
        "Database rejected a value on %s %s: %s", request.method, request.url.path, reason
    )
    return error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "VALIDATION_ERROR",
        "A value in the request cannot be stored.",
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Last resort: log the traceback, return a generic message (no internals)."""
    logger.error("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "INTERNAL_ERROR",
        "An unexpected error occurred.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(DataError, handle_data_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
