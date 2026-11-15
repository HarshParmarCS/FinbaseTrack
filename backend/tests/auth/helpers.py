"""Shared helpers for authentication tests."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.tokens import ACCESS_AUDIENCE, ALGORITHM, hash_token
from app.core.config import get_settings
from app.models import RefreshToken, User

EMAIL = "ana@example.com"
PASSWORD = "correct-horse-battery"
BASE = "/api/v1/auth"


def register(
    client: TestClient,
    *,
    email: str = EMAIL,
    name: str = "Ana Lopez",
    password: str = PASSWORD,
    headers: dict[str, str] | None = None,
) -> Response:
    return client.post(
        f"{BASE}/register",
        json={"name": name, "email": email, "password": password},
        headers=headers,
    )


def login(client: TestClient, *, email: str = EMAIL, password: str = PASSWORD) -> Response:
    return client.post(f"{BASE}/login", json={"email": email, "password": password})


def csrf_headers(client: TestClient) -> dict[str, str]:
    """What the frontend does: echo the readable csrf_token cookie in a header."""
    return {"X-CSRF-Token": client.cookies.get("csrf_token") or ""}


def refresh(client: TestClient) -> Response:
    return client.post(f"{BASE}/refresh", headers=csrf_headers(client))


def logout(client: TestClient) -> Response:
    return client.post(f"{BASE}/logout", headers=csrf_headers(client))


def request_with_cookies(
    app: FastAPI,
    method: str,
    path: str,
    cookies: dict[str, str],
    *,
    csrf: bool = True,
    headers: dict[str, str] | None = None,
) -> Response:
    """Send one request from a brand-new client that holds exactly ``cookies``.

    Used to replay stolen cookies, or to send forged tokens, without touching the main
    client's cookie jar. With ``csrf=True`` a matching CSRF cookie and header are added.
    """
    all_cookies = dict(cookies)
    request_headers = dict(headers or {})
    if csrf:
        all_cookies["csrf_token"] = "test-csrf-value"
        request_headers["X-CSRF-Token"] = "test-csrf-value"
    if all_cookies:
        request_headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in all_cookies.items())
    with TestClient(app, raise_server_exceptions=False) as fresh:
        return fresh.request(method, path, headers=request_headers)


def set_cookies(response: Response) -> dict[str, dict[str, Any]]:
    """Parse Set-Cookie headers into {name: {"value": ..., "httponly": True, "path": ...}}."""
    parsed: dict[str, dict[str, Any]] = {}
    for raw in response.headers.get_list("set-cookie"):
        first, *attributes = [part.strip() for part in raw.split(";")]
        name, _, value = first.partition("=")
        cookie: dict[str, Any] = {"value": value.strip('"')}
        for attribute in attributes:
            key, _, attribute_value = attribute.partition("=")
            cookie[key.lower()] = attribute_value or True
        parsed[name] = cookie
    return parsed


def assert_cookies_cleared(response: Response) -> None:
    cookies = set_cookies(response)
    assert {"access_token", "refresh_token", "csrf_token"} <= set(cookies)
    for name in ("access_token", "refresh_token", "csrf_token"):
        assert cookies[name]["max-age"] == "0", name
        assert cookies[name]["value"] == "", name


def forge_token(
    *,
    user_id: uuid.UUID | str,
    key: str | None = None,
    algorithm: str = ALGORITHM,
    lifetime: timedelta = timedelta(minutes=15),
    issued_at: datetime | None = None,
    **claim_overrides: Any,
) -> str:
    """Build a token with chosen defects. Defaults to a VALID access token."""
    settings = get_settings()
    issued = (issued_at or datetime.now(UTC)).replace(microsecond=0)
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "iat": issued,
        "exp": issued + lifetime,
        "iss": settings.jwt_issuer,
        "aud": ACCESS_AUDIENCE,
        "jti": uuid.uuid4().hex,
        "token_type": "access",
    }
    for name, value in claim_overrides.items():
        if value is None:
            claims.pop(name, None)  # None means "remove this claim"
        else:
            claims[name] = value
    return jwt.encode(
        claims, key or settings.jwt_secret_key.get_secret_value(), algorithm=algorithm
    )


def get_user(db: Session, email: str = EMAIL) -> User:
    user = db.scalars(select(User).where(User.email == email)).one()
    return user


def row_for_token(db: Session, token: str) -> RefreshToken:
    """The stored refresh-token row for a raw token value (looked up by its hash)."""
    db.expire_all()
    return db.scalars(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(token))
    ).one()


def family_rows(db: Session, family_id: uuid.UUID) -> list[RefreshToken]:
    db.expire_all()
    return list(db.scalars(select(RefreshToken).where(RefreshToken.family_id == family_id)))
