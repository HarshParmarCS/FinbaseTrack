"""Centralized exception handling: every error leaves as the documented envelope."""

from typing import Any

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.exceptions import (
    AppError,
    BusinessRuleViolation,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    UnauthenticatedError,
)
from app.main import create_app
from app.schemas.common import ErrorDetail


class _Payload(BaseModel):
    email: str
    password: str = Field(min_length=8)


def _probe_router() -> APIRouter:
    router = APIRouter()

    @router.get("/probe/not-found")
    def not_found() -> None:
        raise NotFoundError("Project not found.")

    @router.get("/probe/conflict")
    def conflict() -> None:
        raise ConflictError()

    @router.get("/probe/unauthenticated")
    def unauthenticated() -> None:
        raise UnauthenticatedError()

    @router.get("/probe/forbidden")
    def forbidden() -> None:
        raise PermissionDeniedError(
            details=[ErrorDetail(policy_id="task-delete", message="Task must be todo.")]
        )

    @router.get("/probe/business-rule")
    def business_rule() -> None:
        raise BusinessRuleViolation("Assignee must be a project member.")

    @router.get("/probe/crash")
    def crash() -> None:
        raise RuntimeError("secret internal detail: db password is hunter2")

    @router.post("/probe/validate")
    def validate(payload: _Payload) -> None:
        return None

    return router


@pytest.fixture
def probe_client() -> TestClient:
    application = create_app()
    application.include_router(_probe_router())
    return TestClient(application, raise_server_exceptions=False)


def _error(response: Any) -> dict[str, Any]:
    body: dict[str, Any] = response.json()
    assert set(body) == {"error"}
    error: dict[str, Any] = body["error"]
    assert set(error) == {"code", "message", "details", "request_id"}
    return error


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [
        ("/probe/not-found", 404, "NOT_FOUND"),
        ("/probe/conflict", 409, "CONFLICT"),
        ("/probe/unauthenticated", 401, "UNAUTHENTICATED"),
        ("/probe/forbidden", 403, "FORBIDDEN"),
        ("/probe/business-rule", 422, "BUSINESS_RULE_VIOLATION"),
    ],
)
def test_domain_errors_map_to_status_and_code(
    probe_client: TestClient, path: str, status: int, code: str
) -> None:
    response = probe_client.get(path)

    assert response.status_code == status
    assert _error(response)["code"] == code


def test_domain_error_uses_custom_message(probe_client: TestClient) -> None:
    error = _error(probe_client.get("/probe/not-found"))

    assert error["message"] == "Project not found."


def test_policy_denial_details_are_returned(probe_client: TestClient) -> None:
    error = _error(probe_client.get("/probe/forbidden"))

    assert error["details"] == [
        {"field": None, "message": "Task must be todo.", "policy_id": "task-delete"}
    ]


def test_error_body_request_id_matches_response_header(probe_client: TestClient) -> None:
    response = probe_client.get("/probe/not-found", headers={"X-Request-ID": "req-42"})

    assert _error(response)["request_id"] == "req-42"
    assert response.headers["X-Request-ID"] == "req-42"


def test_validation_error_returns_field_details_without_echoing_input(
    probe_client: TestClient,
) -> None:
    response = probe_client.post(
        "/probe/validate", json={"email": "a@example.com", "password": "short"}
    )

    error = _error(response)
    assert response.status_code == 422
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"][0]["field"] == "password"
    assert "short" not in response.text


def test_missing_field_is_reported_by_name(probe_client: TestClient) -> None:
    response = probe_client.post("/probe/validate", json={"password": "longenough"})

    fields = [detail["field"] for detail in _error(response)["details"]]
    assert fields == ["email"]


def test_unexpected_error_returns_generic_500_without_internals(
    probe_client: TestClient,
) -> None:
    response = probe_client.get("/probe/crash")

    error = _error(response)
    assert response.status_code == 500
    assert error["code"] == "INTERNAL_ERROR"
    assert error["message"] == "An unexpected error occurred."
    assert "hunter2" not in response.text
    assert "Traceback" not in response.text
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_app_error_base_defaults() -> None:
    error = AppError()

    assert error.status_code == 500
    assert error.code == "INTERNAL_ERROR"
    assert error.details == []
