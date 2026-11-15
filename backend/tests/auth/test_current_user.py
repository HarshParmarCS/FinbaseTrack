"""get_current_user: every way an access token can be wrong must give 401."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.tokens import REFRESH_AUDIENCE, create_access_token, create_refresh_token
from app.core.config import get_settings
from tests.auth.helpers import (
    BASE,
    EMAIL,
    forge_token,
    get_user,
    register,
    request_with_cookies,
)

ME = f"{BASE}/me"


def me_with_token(app: FastAPI, token: str) -> Any:
    return request_with_cookies(app, "GET", ME, {"access_token": token}, csrf=False)


def assert_unauthenticated(response: Any) -> None:
    assert response.status_code == 401
    error = response.json()["error"]
    assert error["code"] == "UNAUTHENTICATED"
    assert error["message"] == "Authentication is missing, invalid or expired."


def test_me_returns_the_authenticated_user(client: TestClient) -> None:
    created = register(client).json()["data"]

    response = client.get(ME)

    assert response.status_code == 200
    assert response.json() == {"data": created}


def test_missing_token_is_rejected(client: TestClient) -> None:
    assert_unauthenticated(client.get(ME))


def test_invalid_signature_is_rejected(
    app: FastAPI, client: TestClient, db_session: Session
) -> None:
    register(client)
    user = get_user(db_session)

    token = forge_token(user_id=user.id, key="another-secret-key-that-is-long-enough-123")

    assert_unauthenticated(me_with_token(app, token))


def test_expired_token_is_rejected(app: FastAPI, client: TestClient, db_session: Session) -> None:
    register(client)
    user = get_user(db_session)

    expired = create_access_token(user.id, now=datetime.now(UTC) - timedelta(hours=1)).token

    assert_unauthenticated(me_with_token(app, expired))


def test_refresh_token_is_not_accepted_as_an_access_token(
    app: FastAPI, client: TestClient, db_session: Session
) -> None:
    register(client)
    user = get_user(db_session)

    assert_unauthenticated(me_with_token(app, create_refresh_token(user.id).token))


def test_wrong_token_type_claim_is_rejected_even_with_the_access_audience(
    app: FastAPI, client: TestClient, db_session: Session
) -> None:
    register(client)
    user = get_user(db_session)

    assert_unauthenticated(me_with_token(app, forge_token(user_id=user.id, token_type="refresh")))


@pytest.mark.parametrize(
    "defect",
    [
        {"iss": "someone-else"},
        {"aud": REFRESH_AUDIENCE},
        {"aud": "fintasks:other"},
        {"jti": None},
        {"exp": None},
        {"sub": "not-a-uuid"},
    ],
)
def test_tokens_with_wrong_or_missing_claims_are_rejected(
    app: FastAPI, client: TestClient, db_session: Session, defect: dict[str, Any]
) -> None:
    register(client)
    user = get_user(db_session)
    defect = {"sub": str(user.id), **defect}

    assert_unauthenticated(me_with_token(app, forge_token(user_id=user.id, **defect)))


@pytest.mark.filterwarnings("ignore:The HMAC key is:Warning")
def test_algorithm_substitution_and_unsigned_tokens_are_rejected(
    app: FastAPI, client: TestClient, db_session: Session
) -> None:
    register(client)
    user = get_user(db_session)
    secret = get_settings().jwt_secret_key.get_secret_value()
    valid = forge_token(user_id=user.id)
    claims = jwt.decode(valid, options={"verify_signature": False})

    assert_unauthenticated(me_with_token(app, jwt.encode(claims, secret, algorithm="HS512")))
    assert_unauthenticated(me_with_token(app, jwt.encode(claims, key=None, algorithm="none")))
    assert me_with_token(app, valid).status_code == 200  # the same claims, properly signed


@pytest.mark.parametrize("garbage", ["garbage", "a.b.c", "x" * 600])
def test_malformed_tokens_are_rejected(app: FastAPI, garbage: str) -> None:
    assert_unauthenticated(me_with_token(app, garbage))


def test_token_for_a_user_that_no_longer_exists_is_rejected(app: FastAPI) -> None:
    assert_unauthenticated(me_with_token(app, forge_token(user_id=uuid.uuid4())))


def test_inactive_user_is_rejected_even_with_a_valid_token(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    assert client.get(ME).status_code == 200

    get_user(db_session).is_active = False
    db_session.flush()

    assert_unauthenticated(client.get(ME))


def test_bearer_header_is_not_an_accepted_credential(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    token = client.cookies.get("access_token")
    client.cookies.clear()

    response = client.get(ME, headers={"Authorization": f"Bearer {token}"})

    assert_unauthenticated(response)


def test_identity_comes_from_the_token_never_from_the_request(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    other = register_other(client)

    response = client.get(ME, params={"user_id": other, "id": other})

    assert response.json()["data"]["email"] == EMAIL


def register_other(client: TestClient) -> str:
    """Create a second user from a separate client session and return their id."""
    other_client = TestClient(client.app, raise_server_exceptions=False)
    other = register(other_client, email="bob@example.com", name="Bob")
    return str(other.json()["data"]["id"])
