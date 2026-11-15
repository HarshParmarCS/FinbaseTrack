"""Make the generated OpenAPI document describe what the API REALLY does.

FastAPI's default document is close but not exact for this API:

* authentication is by HttpOnly cookies plus a CSRF header, which it cannot infer;
* every 422 body is our ``ErrorResponse`` envelope, not FastAPI's ``HTTPValidationError``;
* cookie dependencies show up as ordinary per-operation parameters.

``install_openapi`` fixes those in one place and adds the real request/response examples that
``scripts/generate_api_docs.py`` captured from the running application.
"""

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from app.core.cookies import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE
from app.core.csrf import CSRF_HEADER

EXAMPLES_FILE = Path(__file__).resolve().parents[1] / "api" / "examples.json"

# Routes that need no access token.
PUBLIC_PATHS = {"/api/v1/health", "/api/v1/auth/register", "/api/v1/auth/login"}
# Routes authenticated by the refresh-token cookie instead of the access token.
REFRESH_PATHS = {"/api/v1/auth/refresh", "/api/v1/auth/logout"}
UNSAFE_METHODS = {"post", "put", "patch", "delete"}

SECURITY_SCHEMES: dict[str, dict[str, Any]] = {
    "accessTokenCookie": {
        "type": "apiKey",
        "in": "cookie",
        "name": ACCESS_COOKIE,
        "description": (
            "Access token (JWT, 15 minutes) set as an HttpOnly cookie by register, login and "
            "refresh. Browsers send it automatically."
        ),
    },
    "refreshTokenCookie": {
        "type": "apiKey",
        "in": "cookie",
        "name": REFRESH_COOKIE,
        "description": (
            "Refresh token (JWT, 7 days) set as an HttpOnly cookie, sent only to /api/v1/auth/*."
        ),
    },
    "csrfHeader": {
        "type": "apiKey",
        "in": "header",
        "name": CSRF_HEADER,
        "description": (
            f"Required on POST, PATCH and DELETE requests that carry session cookies: send the "
            f"value of the `{CSRF_COOKIE}` cookie (set at login). Login and register are exempt."
        ),
    },
}


def _security_for(path: str, method: str) -> list[dict[str, list[str]]]:
    if path in PUBLIC_PATHS:
        return []
    cookie = "refreshTokenCookie" if path in REFRESH_PATHS else "accessTokenCookie"
    requirement: dict[str, list[str]] = {cookie: []}
    if method in UNSAFE_METHODS:
        requirement["csrfHeader"] = []
    return [requirement]


def _load_examples() -> dict[str, Any]:
    if not EXAMPLES_FILE.exists():
        return {}
    data: dict[str, Any] = json.loads(EXAMPLES_FILE.read_text())
    return data


def harden_schema(schema: dict[str, Any], examples: dict[str, Any]) -> dict[str, Any]:
    """Return ``schema`` corrected in place (and also return it for convenience)."""
    components = schema.setdefault("components", {})
    components.setdefault("securitySchemes", {}).update(SECURITY_SCHEMES)

    for path, item in schema.get("paths", {}).items():
        for method, operation in item.items():
            # The cookie dependencies are described by the security schemes instead.
            operation["parameters"] = [
                p for p in operation.get("parameters", []) if p.get("in") != "cookie"
            ]
            if not operation["parameters"]:
                del operation["parameters"]
            operation["security"] = _security_for(path, method)

            responses = operation.get("responses", {})
            if "422" in responses:
                responses["422"] = {
                    "description": "Validation error or business rule violation (error envelope)",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    },
                }
            _attach_examples(operation, examples.get(f"{method.upper()} {path}"))

    for unused in ("HTTPValidationError", "ValidationError"):
        components.get("schemas", {}).pop(unused, None)
    return schema


def _attach_examples(operation: dict[str, Any], example: dict[str, Any] | None) -> None:
    if not example:
        return
    request = example.get("request", {}).get("body")
    body = operation.get("requestBody", {}).get("content", {}).get("application/json")
    if body is not None and request is not None:
        body["example"] = request
    for kind in ("success", "error"):
        sample = example.get(kind)
        if not sample:
            continue
        response = operation["responses"].setdefault(str(sample["status"]), {"description": kind})
        if sample.get("body") is not None:
            content = response.setdefault("content", {}).setdefault("application/json", {})
            content["example"] = sample["body"]


def install_openapi(app: FastAPI) -> None:
    default_openapi = app.openapi

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = default_openapi()  # FastAPI builds and caches it on first call
        harden_schema(schema, _load_examples())
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
