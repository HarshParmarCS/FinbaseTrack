import logging

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth.passwords import password_needs_rehash
from app.auth.tokens import hash_token
from app.core.cookies import set_auth_cookies
from app.models import RefreshToken, User
from tests.auth.helpers import (
    BASE,
    EMAIL,
    PASSWORD,
    get_user,
    login,
    register,
    row_for_token,
    set_cookies,
)

# ---- registration ----------------------------------------------------------------------------


def test_registration_creates_the_user_and_logs_them_in(
    client: TestClient, db_session: Session
) -> None:
    response = register(client)

    assert response.status_code == 201
    data = response.json()["data"]
    assert set(data) == {"id", "email", "name"}
    assert data["email"] == EMAIL
    assert data["name"] == "Ana Lopez"
    user = get_user(db_session)
    assert str(user.id) == data["id"]
    assert user.is_active is True
    assert client.get(f"{BASE}/me").json()["data"]["id"] == data["id"]


def test_password_is_stored_only_as_an_argon2id_hash(
    client: TestClient, db_session: Session
) -> None:
    register(client)

    stored = get_user(db_session).password_hash

    assert stored.startswith("$argon2id$")
    assert PASSWORD not in stored
    assert PasswordHasher().verify(stored, PASSWORD)


def test_response_never_contains_password_hash_or_tokens(client: TestClient) -> None:
    response = register(client)

    assert "password" not in response.text
    assert "argon2" not in response.text
    for name in ("access_token", "refresh_token"):
        value = client.cookies.get(name)
        assert value is not None
        assert value not in response.text


def test_email_is_normalized_to_lowercase_without_surrounding_spaces(
    client: TestClient, db_session: Session
) -> None:
    response = register(client, email="  Ana.Lopez@Example.COM ")

    assert response.status_code == 201
    assert response.json()["data"]["email"] == "ana.lopez@example.com"
    assert get_user(db_session, "ana.lopez@example.com").email == "ana.lopez@example.com"


def test_duplicate_email_is_rejected(client: TestClient, db_session: Session) -> None:
    assert register(client).status_code == 201

    response = register(client, name="Someone Else")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"
    assert db_session.scalar(select(func.count()).select_from(User)) == 1


def test_duplicate_email_is_detected_regardless_of_case(client: TestClient) -> None:
    register(client, email="ana@example.com")

    assert register(client, email="ANA@Example.com").status_code == 409


def test_registration_stores_only_the_hash_of_the_refresh_token(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    refresh_token = client.cookies.get("refresh_token")
    assert refresh_token is not None

    row = row_for_token(db_session, refresh_token)

    assert row.token_hash == hash_token(refresh_token)
    assert row.token_hash != refresh_token
    assert row.revoked_at is None
    stored_values = db_session.execute(
        text("select token_hash from refresh_tokens where token_hash = :t"), {"t": refresh_token}
    ).all()
    assert stored_values == []  # the raw token is not in the table


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"name": "Ana", "email": "ana@example.com", "password": "short"}, "password"),
        ({"name": "Ana", "email": "ana@example.com", "password": "x" * 129}, "password"),
        ({"name": "Ana", "email": "not-an-email", "password": PASSWORD}, "email"),
        ({"name": "   ", "email": "ana@example.com", "password": PASSWORD}, "name"),
        ({"name": "x" * 121, "email": "ana@example.com", "password": PASSWORD}, "name"),
        ({"email": "ana@example.com", "password": PASSWORD}, "name"),
        ({"name": "Ana", "password": PASSWORD}, "email"),
        ({"name": "Ana", "email": "ana@example.com"}, "password"),
    ],
)
def test_invalid_registration_input_is_rejected(
    client: TestClient, payload: dict[str, str], field: str
) -> None:
    response = client.post(f"{BASE}/register", json=payload)

    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "VALIDATION_ERROR"
    assert field in [detail["field"] for detail in body["details"]]


@pytest.mark.parametrize("extra", ["user_id", "id", "is_active", "role"])
def test_client_supplied_identity_fields_are_rejected(client: TestClient, extra: str) -> None:
    response = client.post(
        f"{BASE}/register",
        json={"name": "Ana", "email": EMAIL, "password": PASSWORD, extra: "anything"},
    )

    assert response.status_code == 422
    assert extra in [d["field"] for d in response.json()["error"]["details"]]


def test_validation_errors_do_not_echo_the_password(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/register", json={"name": "Ana", "email": "bad", "password": "tiny-pw"}
    )

    assert "tiny-pw" not in response.text


# ---- cookies -------------------------------------------------------------------------------


def test_authentication_cookies_have_the_documented_attributes(client: TestClient) -> None:
    response = register(client)

    cookies = set_cookies(response)
    access, refresh, csrf = cookies["access_token"], cookies["refresh_token"], cookies["csrf_token"]
    assert access["httponly"] is True
    assert access["path"] == "/"
    assert access["max-age"] == str(15 * 60)
    assert access["samesite"].lower() == "lax"
    assert refresh["httponly"] is True
    assert refresh["path"] == "/api/v1/auth"
    assert refresh["max-age"] == str(7 * 24 * 60 * 60)
    assert refresh["samesite"].lower() == "lax"
    assert "httponly" not in csrf  # the frontend must be able to read it
    assert csrf["path"] == "/"
    assert csrf["samesite"].lower() == "lax"
    assert all("secure" not in c for c in cookies.values())  # plain http in development


def test_cookies_are_secure_when_configured_for_https() -> None:
    from fastapi import Response

    from app.core.config import Settings

    settings = Settings(
        _env_file=None,
        database_url="postgresql://u:p@localhost/db",
        jwt_secret_key="s" * 40,
        environment="production",
        cookie_secure=True,
    )
    response = Response()

    set_auth_cookies(response, settings, access="a", refresh="r")

    headers = response.headers.getlist("set-cookie")
    assert len(headers) == 3
    assert all("Secure" in header for header in headers)
    assert sum("HttpOnly" in header for header in headers) == 2


# ---- login ------------------------------------------------------------------------------


def test_login_succeeds_and_sets_the_three_cookies(client: TestClient) -> None:
    register(client)
    client.cookies.clear()

    response = login(client)

    assert response.status_code == 200
    assert response.json()["data"]["email"] == EMAIL
    assert {"access_token", "refresh_token", "csrf_token"} <= set(set_cookies(response))
    assert client.get(f"{BASE}/me").status_code == 200


def test_login_normalizes_the_email(client: TestClient) -> None:
    register(client)
    client.cookies.clear()

    assert login(client, email="  ANA@Example.com ").status_code == 200


def test_each_login_starts_a_new_token_family(client: TestClient, db_session: Session) -> None:
    register(client)
    login(client)
    login(client)

    families = db_session.scalars(select(RefreshToken.family_id)).all()

    assert len(families) == 3
    assert len(set(families)) == 3


def test_wrong_password_and_unknown_email_get_the_same_generic_401(client: TestClient) -> None:
    register(client)
    client.cookies.clear()

    wrong_password = login(client, password="not-the-password")
    unknown_email = login(client, email="nobody@example.com")

    for response in (wrong_password, unknown_email):
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"
        assert response.json()["error"]["message"] == "Invalid email or password."
        assert "set-cookie" not in response.headers
    assert wrong_password.json()["error"]["message"] == unknown_email.json()["error"]["message"]


def test_inactive_user_cannot_log_in_even_with_the_right_password(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    client.cookies.clear()
    get_user(db_session).is_active = False
    db_session.flush()

    response = login(client)

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password."
    assert "set-cookie" not in response.headers


def test_login_input_is_validated_and_unknown_fields_rejected(client: TestClient) -> None:
    assert client.post(f"{BASE}/login", json={"email": EMAIL}).status_code == 422
    assert client.post(f"{BASE}/login", json={"email": "bad", "password": "x"}).status_code == 422
    extra = {"email": EMAIL, "password": PASSWORD, "user_id": "x"}
    assert client.post(f"{BASE}/login", json=extra).status_code == 422


def test_weak_password_hash_is_upgraded_on_successful_login(
    client: TestClient, db_session: Session
) -> None:
    weak_hash = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash(PASSWORD)
    db_session.add(User(name="Old Account", email=EMAIL, password_hash=weak_hash))
    db_session.flush()
    assert password_needs_rehash(weak_hash)

    assert login(client).status_code == 200

    upgraded = get_user(db_session).password_hash
    assert upgraded != weak_hash
    assert not password_needs_rehash(upgraded)


def test_passwords_and_tokens_are_never_logged(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        register(client)
        login(client, password="wrong-password-value")
        login(client)
        client.get(f"{BASE}/me")

    logged = caplog.text
    assert PASSWORD not in logged
    assert "wrong-password-value" not in logged
    for name in ("access_token", "refresh_token", "csrf_token"):
        value = client.cookies.get(name)
        assert value and value not in logged
    assert "argon2" not in logged
