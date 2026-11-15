"""Authentication events are written to the activity log (and never contain secrets)."""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActivityLog
from app.repositories.user_repository import UserRepository
from tests.auth.helpers import (
    EMAIL,
    PASSWORD,
    get_user,
    login,
    logout,
    refresh,
    register,
    request_with_cookies,
    row_for_token,
)


def entries(db: Session, action: str | None = None) -> list[ActivityLog]:
    db.expire_all()
    statement = select(ActivityLog)
    if action:
        statement = statement.where(ActivityLog.action == action)
    return list(db.scalars(statement))


def test_registration_is_recorded(client: TestClient, db_session: Session) -> None:
    register(client)

    [entry] = entries(db_session, "user.registered")

    assert entry.user_id == get_user(db_session).id
    assert entry.project_id is None and entry.task_id is None
    assert entry.meta == {}


def test_logins_are_recorded_one_per_login(client: TestClient, db_session: Session) -> None:
    register(client)
    login(client)
    login(client)

    assert len(entries(db_session, "auth.login")) == 2


def test_failed_logins_write_nothing(client: TestClient, db_session: Session) -> None:
    register(client)
    client.cookies.clear()

    login(client, password="not-the-password")
    login(client, email="nobody@example.com")

    assert entries(db_session, "auth.login") == []


def test_logout_is_recorded_when_a_session_ends(client: TestClient, db_session: Session) -> None:
    register(client)

    logout(client)

    [entry] = entries(db_session, "auth.logout")
    assert entry.user_id == get_user(db_session).id


def test_a_logout_without_a_session_writes_nothing(app: FastAPI, db_session: Session) -> None:
    request_with_cookies(app, "POST", "/api/v1/auth/logout", {}, csrf=False)

    assert entries(db_session, "auth.logout") == []


def test_refresh_token_reuse_is_recorded_as_a_security_event(
    app: FastAPI, client: TestClient, db_session: Session
) -> None:
    register(client)
    stolen = client.cookies.get("refresh_token") or ""
    family = row_for_token(db_session, stolen).family_id
    refresh(client)

    request_with_cookies(app, "POST", "/api/v1/auth/refresh", {"refresh_token": stolen})

    [entry] = entries(db_session, "auth.refresh_reuse_detected")
    assert entry.user_id == get_user(db_session).id
    assert entry.meta == {"family_id": str(family)}


def test_a_normal_refresh_is_not_a_security_event(client: TestClient, db_session: Session) -> None:
    register(client)
    refresh(client)

    assert entries(db_session, "auth.refresh_reuse_detected") == []


def test_a_rejected_registration_leaves_no_trace(client: TestClient, db_session: Session) -> None:
    register(client)
    other = TestClient(client.app, raise_server_exceptions=False)

    assert register(other).status_code == 409

    assert len(entries(db_session, "user.registered")) == 1


def test_authentication_entries_never_contain_secrets(
    app: FastAPI, client: TestClient, db_session: Session
) -> None:
    register(client)
    login(client)
    request_with_cookies(app, "POST", "/api/v1/auth/refresh", {"refresh_token": "garbage"})
    refresh(client)
    logout(client)

    blob = " ".join(f"{e.action} {e.meta}" for e in entries(db_session))

    for secret in (PASSWORD, EMAIL, "argon2", "eyJ"):
        assert secret not in blob


def test_a_registration_race_is_reported_as_a_conflict(
    client: TestClient, app: FastAPI, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both requests pass the 'email is free' check; the database's unique key decides."""
    register(client)
    other = TestClient(app, raise_server_exceptions=False)
    monkeypatch.setattr(UserRepository, "get_by_email", lambda self, email: None)

    response = register(other)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"
    assert len(entries(db_session, "user.registered")) == 1
    assert uuid.UUID(str(get_user(db_session).id))
