"""CSRF protection (Origin check + double-submit token) and CORS."""

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy.orm import Session

from tests.auth.helpers import (
    BASE,
    EMAIL,
    PASSWORD,
    csrf_headers,
    login,
    register,
    row_for_token,
)

ALLOWED = "http://localhost:3000"
EVIL = "https://evil.example"


def assert_forbidden(response: Response) -> None:
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert "X-Request-ID" in response.headers


# ---- double-submit token ----------------------------------------------------------------------


def test_refresh_without_csrf_header_is_forbidden(client: TestClient) -> None:
    register(client)

    assert_forbidden(client.post(f"{BASE}/refresh"))


def test_refresh_with_wrong_csrf_header_is_forbidden(client: TestClient) -> None:
    register(client)

    assert_forbidden(client.post(f"{BASE}/refresh", headers={"X-CSRF-Token": "forged-value"}))


def test_refresh_with_matching_csrf_header_succeeds(client: TestClient) -> None:
    register(client)

    assert client.post(f"{BASE}/refresh", headers=csrf_headers(client)).status_code == 200


def test_csrf_header_without_the_cookie_is_not_enough(client: TestClient) -> None:
    register(client)
    refresh_cookie = client.cookies.get("refresh_token")
    client.cookies.clear()
    client.cookies.set("refresh_token", refresh_cookie or "", path="/api/v1/auth")

    assert_forbidden(client.post(f"{BASE}/refresh", headers={"X-CSRF-Token": "anything"}))


def test_logout_without_csrf_header_is_forbidden_and_does_not_revoke(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    token = client.cookies.get("refresh_token") or ""

    assert_forbidden(client.post(f"{BASE}/logout"))

    assert row_for_token(db_session, token).revoked_at is None


def test_login_and_register_do_not_need_the_csrf_header_even_with_old_cookies(
    client: TestClient,
) -> None:
    register(client)  # the client now holds session cookies

    assert (
        client.post(f"{BASE}/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 200
    )
    other = {"name": "Bob", "email": "bob@example.com", "password": PASSWORD}
    assert client.post(f"{BASE}/register", json=other).status_code == 201


def test_safe_methods_never_need_the_csrf_header(client: TestClient) -> None:
    register(client)

    assert client.get(f"{BASE}/me").status_code == 200
    assert client.get("/api/v1/health").status_code == 200


def test_requests_without_auth_cookies_need_no_csrf_token(client: TestClient) -> None:
    # No session cookie means no ambient credential for an attacker to abuse.
    assert client.post(f"{BASE}/logout").status_code == 204


# ---- Origin check -----------------------------------------------------------------------------


@pytest.mark.parametrize("origin", [EVIL, "null", "http://localhost:3000.evil.example"])
def test_disallowed_origin_is_forbidden_even_for_login(client: TestClient, origin: str) -> None:
    register(client)
    client.cookies.clear()

    response = client.post(
        f"{BASE}/login", json={"email": EMAIL, "password": PASSWORD}, headers={"Origin": origin}
    )

    assert_forbidden(response)
    assert "set-cookie" not in response.headers


def test_disallowed_origin_is_forbidden_even_with_a_valid_csrf_token(client: TestClient) -> None:
    register(client)

    headers = {**csrf_headers(client), "Origin": EVIL}

    assert_forbidden(client.post(f"{BASE}/refresh", headers=headers))


def test_allowed_origin_can_use_the_api(client: TestClient) -> None:
    register(client)

    headers = {**csrf_headers(client), "Origin": ALLOWED}

    assert client.post(f"{BASE}/refresh", headers=headers).status_code == 200


def test_api_own_origin_is_allowed(client: TestClient) -> None:
    # Same-origin requests (for example Swagger UI served by the API itself).
    response = register(client, headers={"Origin": "http://testserver"})

    assert response.status_code == 201


def test_requests_without_an_origin_header_are_not_blocked_by_the_origin_check(
    client: TestClient,
) -> None:
    # Non-browser clients (curl, server-to-server) send no Origin. They are still bound by the
    # token rule when they carry auth cookies.
    assert register(client).status_code == 201


# ---- CORS -------------------------------------------------------------------------------------


def test_preflight_from_an_allowed_origin_is_accepted_with_credentials(
    client: TestClient,
) -> None:
    response = client.options(
        f"{BASE}/refresh",
        headers={
            "Origin": ALLOWED,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-csrf-token",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED
    assert response.headers["access-control-allow-credentials"] == "true"
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "x-csrf-token" in allowed_headers


def test_preflight_from_another_origin_is_refused(client: TestClient) -> None:
    response = client.options(
        f"{BASE}/refresh",
        headers={"Origin": EVIL, "Access-Control-Request-Method": "POST"},
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_headers_are_only_added_for_allowed_origins(client: TestClient) -> None:
    allowed = client.get("/api/v1/health", headers={"Origin": ALLOWED})
    other = client.get("/api/v1/health", headers={"Origin": EVIL})

    assert allowed.headers["access-control-allow-origin"] == ALLOWED
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert "access-control-allow-origin" not in other.headers


def test_wildcard_origin_is_never_used_with_credentials(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": ALLOWED})

    assert response.headers["access-control-allow-origin"] != "*"


def test_login_response_to_an_allowed_origin_carries_cors_and_cookies(client: TestClient) -> None:
    register(client)
    client.cookies.clear()

    response = client.post(
        f"{BASE}/login",
        json={"email": EMAIL, "password": PASSWORD},
        headers={"Origin": ALLOWED},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED
    assert login(client).status_code == 200
