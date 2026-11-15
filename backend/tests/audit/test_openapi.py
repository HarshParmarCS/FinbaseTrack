"""Swagger and the OpenAPI document describe the API as it really behaves."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.openapi import PUBLIC_PATHS, REFRESH_PATHS, UNSAFE_METHODS

LOGOUT = "/api/v1/auth/logout"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


@pytest.fixture
def schema(client: TestClient) -> dict[str, Any]:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    return response.json()  # type: ignore[no-any-return]


def operations(schema: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (method, path, op)
        for path, item in schema["paths"].items()
        for method, op in item.items()
        if method in HTTP_METHODS
    ]


def test_swagger_ui_is_served(client: TestClient) -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text


def test_openapi_document_is_version_3(schema: dict[str, Any]) -> None:
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"]
    assert len(operations(schema)) == 23


def test_security_schemes_describe_cookie_auth_and_csrf(schema: dict[str, Any]) -> None:
    schemes = schema["components"]["securitySchemes"]

    assert schemes["accessTokenCookie"]["in"] == "cookie"
    assert schemes["refreshTokenCookie"]["in"] == "cookie"
    assert schemes["csrfHeader"]["in"] == "header"


def test_public_operations_declare_no_security(schema: dict[str, Any]) -> None:
    for method, path, op in operations(schema):
        if path in PUBLIC_PATHS:
            assert op["security"] == [], f"{method} {path}"


def test_protected_operations_require_the_right_cookie(schema: dict[str, Any]) -> None:
    for method, path, op in operations(schema):
        if path in PUBLIC_PATHS:
            continue
        (requirement,) = op["security"]
        cookie = "refreshTokenCookie" if path in REFRESH_PATHS else "accessTokenCookie"
        assert cookie in requirement, f"{method} {path}"
        assert ("csrfHeader" in requirement) == (method in UNSAFE_METHODS), f"{method} {path}"


def test_no_operation_exposes_cookie_parameters(schema: dict[str, Any]) -> None:
    for method, path, op in operations(schema):
        located = {p["in"] for p in op.get("parameters", [])}
        assert "cookie" not in located, f"{method} {path}"


def test_every_422_is_the_error_envelope(schema: dict[str, Any]) -> None:
    for method, path, op in operations(schema):
        if "422" in op["responses"]:
            ref = op["responses"]["422"]["content"]["application/json"]["schema"]["$ref"]
            assert ref.endswith("/ErrorResponse"), f"{method} {path}"
    assert "HTTPValidationError" not in schema["components"]["schemas"]


def test_operation_ids_are_unique_and_every_operation_has_a_summary(
    schema: dict[str, Any],
) -> None:
    ops = operations(schema)
    ids = [op["operationId"] for _, _, op in ops]

    assert len(ids) == len(set(ids))
    assert all(op.get("summary") for _, _, op in ops)


def test_every_operation_has_a_success_example(schema: dict[str, Any]) -> None:
    for method, path, op in operations(schema):
        successes = [
            r for code, r in op["responses"].items() if code.startswith("2") and "content" in r
        ]
        if not successes:
            continue  # 204 responses have no body
        assert any("example" in r["content"]["application/json"] for r in successes), (
            f"{method} {path}"
        )


def test_protected_operations_document_their_error_statuses(schema: dict[str, Any]) -> None:
    for method, path, op in operations(schema):
        codes = set(op["responses"])
        if path not in PUBLIC_PATHS and path != LOGOUT:  # logout is idempotent: 204, never 401
            assert "401" in codes, f"{method} {path} lacks 401"
        if method in UNSAFE_METHODS and path not in PUBLIC_PATHS | REFRESH_PATHS:
            assert "403" in codes, f"{method} {path} lacks 403"
        if "{" in path:
            assert "404" in codes, f"{method} {path} lacks 404"
