"""Refresh-token rotation, reuse detection and logout."""

from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.tokens import create_refresh_token
from app.models import RefreshToken
from tests.auth.helpers import (
    BASE,
    EMAIL,
    assert_cookies_cleared,
    family_rows,
    get_user,
    login,
    logout,
    refresh,
    register,
    request_with_cookies,
    row_for_token,
    set_cookies,
)

REFRESH = f"{BASE}/refresh"
LOGOUT = f"{BASE}/logout"


def cookie(client: TestClient, name: str) -> str:
    value = client.cookies.get(name)
    assert value is not None, name
    return value


# ---- refresh and rotation -------------------------------------------------------------------


def test_refresh_issues_a_new_token_pair(client: TestClient) -> None:
    register(client)
    old_access, old_refresh = cookie(client, "access_token"), cookie(client, "refresh_token")

    response = refresh(client)

    assert response.status_code == 200
    assert response.json()["data"]["email"] == EMAIL
    assert {"access_token", "refresh_token", "csrf_token"} <= set(set_cookies(response))
    assert cookie(client, "refresh_token") != old_refresh
    assert cookie(client, "access_token") != old_access
    assert client.get(f"{BASE}/me").status_code == 200


def test_refresh_rotates_revokes_the_old_token_and_keeps_the_family(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    old_token = cookie(client, "refresh_token")

    refresh(client)
    new_token = cookie(client, "refresh_token")

    old_row = row_for_token(db_session, old_token)
    new_row = row_for_token(db_session, new_token)
    assert old_row.revoked_at is not None
    assert old_row.replaced_by == new_row.id
    assert new_row.revoked_at is None
    assert new_row.family_id == old_row.family_id
    assert old_row.token_hash != new_row.token_hash


def test_a_token_can_be_rotated_many_times_and_only_the_latest_stays_active(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    family = row_for_token(db_session, cookie(client, "refresh_token")).family_id

    for _ in range(3):
        assert refresh(client).status_code == 200

    rows = family_rows(db_session, family)
    assert len(rows) == 4
    assert sum(row.revoked_at is None for row in rows) == 1


def test_a_rotated_token_cannot_be_used_again(app: FastAPI, client: TestClient) -> None:
    register(client)
    old_token = cookie(client, "refresh_token")
    refresh(client)

    replay = request_with_cookies(app, "POST", REFRESH, {"refresh_token": old_token})

    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "UNAUTHENTICATED"
    assert_cookies_cleared(replay)


def test_reuse_of_a_revoked_token_revokes_the_whole_family(
    app: FastAPI, client: TestClient, db_session: Session
) -> None:
    register(client)
    stolen = cookie(client, "refresh_token")
    family = row_for_token(db_session, stolen).family_id
    refresh(client)  # the real user rotates; `stolen` is now revoked
    legitimate_latest = cookie(client, "refresh_token")

    attacker = request_with_cookies(app, "POST", REFRESH, {"refresh_token": stolen})

    assert attacker.status_code == 401
    assert all(row.revoked_at is not None for row in family_rows(db_session, family))
    # The legitimate user's newest token died with the family: both parties must log in again.
    victim = request_with_cookies(app, "POST", REFRESH, {"refresh_token": legitimate_latest})
    assert victim.status_code == 401


def test_reuse_only_revokes_the_affected_family(
    app: FastAPI, client: TestClient, db_session: Session
) -> None:
    register(client)
    first_session_token = cookie(client, "refresh_token")
    login(client)  # a second device: a different family
    second_session_token = cookie(client, "refresh_token")
    second_family = row_for_token(db_session, second_session_token).family_id
    # rotate the first family's token, then replay the old one
    request_with_cookies(app, "POST", REFRESH, {"refresh_token": first_session_token})
    request_with_cookies(app, "POST", REFRESH, {"refresh_token": first_session_token})

    assert all(row.revoked_at is None for row in family_rows(db_session, second_family))


def test_access_token_is_never_accepted_at_the_refresh_endpoint(
    app: FastAPI, client: TestClient
) -> None:
    register(client)

    response = request_with_cookies(
        app, "POST", REFRESH, {"refresh_token": cookie(client, "access_token")}
    )

    assert response.status_code == 401
    assert_cookies_cleared(response)


def test_refresh_without_a_cookie_is_rejected_and_clears_cookies(
    app: FastAPI,
) -> None:
    response = request_with_cookies(app, "POST", REFRESH, {}, csrf=False)

    assert response.status_code == 401
    assert_cookies_cleared(response)


def test_garbage_refresh_token_is_rejected(app: FastAPI) -> None:
    response = request_with_cookies(app, "POST", REFRESH, {"refresh_token": "garbage"})

    assert response.status_code == 401


def test_validly_signed_but_never_issued_refresh_token_is_rejected(
    app: FastAPI, client: TestClient, db_session: Session
) -> None:
    register(client)
    user = get_user(db_session)
    never_stored = create_refresh_token(user.id).token  # correct signature, not in the database

    response = request_with_cookies(app, "POST", REFRESH, {"refresh_token": never_stored})

    assert response.status_code == 401


def test_expired_refresh_token_is_rejected(
    app: FastAPI, client: TestClient, db_session: Session
) -> None:
    register(client)
    user = get_user(db_session)
    eight_days_ago = datetime.now(UTC) - timedelta(days=8)
    expired = create_refresh_token(user.id, now=eight_days_ago)

    response = request_with_cookies(app, "POST", REFRESH, {"refresh_token": expired.token})

    assert response.status_code == 401


def test_refresh_for_an_inactive_user_is_rejected_and_revokes_the_family(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    token = cookie(client, "refresh_token")
    family = row_for_token(db_session, token).family_id
    get_user(db_session).is_active = False
    db_session.flush()

    response = refresh(client)

    assert response.status_code == 401
    assert all(row.revoked_at is not None for row in family_rows(db_session, family))


def test_database_never_contains_the_raw_refresh_token(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    refresh(client)
    raw_tokens = {cookie(client, "refresh_token")}

    stored = set(db_session.scalars(select(RefreshToken.token_hash)))

    assert stored.isdisjoint(raw_tokens)
    assert all(len(value) == 64 for value in stored)


# ---- logout ------------------------------------------------------------------------------


def test_logout_revokes_the_refresh_token_and_clears_cookies(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    token = cookie(client, "refresh_token")

    response = logout(client)

    assert response.status_code == 204
    assert response.content == b""
    assert_cookies_cleared(response)
    assert row_for_token(db_session, token).revoked_at is not None


def test_refresh_fails_after_logout(app: FastAPI, client: TestClient) -> None:
    register(client)
    token = cookie(client, "refresh_token")
    logout(client)

    response = request_with_cookies(app, "POST", REFRESH, {"refresh_token": token})

    assert response.status_code == 401


def test_logout_clears_the_browser_session(client: TestClient) -> None:
    register(client)

    logout(client)

    assert client.cookies.get("access_token") is None
    assert client.get(f"{BASE}/me").status_code == 401


def test_logout_revokes_only_its_own_session(client: TestClient, db_session: Session) -> None:
    register(client)
    first_family = row_for_token(db_session, cookie(client, "refresh_token")).family_id
    first_cookies = dict(client.cookies)
    login(client)  # second device
    second_family = row_for_token(db_session, cookie(client, "refresh_token")).family_id
    assert first_family != second_family

    logout(client)  # logs out the second device

    assert all(row.revoked_at is not None for row in family_rows(db_session, second_family))
    assert all(row.revoked_at is None for row in family_rows(db_session, first_family))
    assert first_cookies  # the first device's cookies were not touched


def test_logout_works_without_a_valid_access_token(
    app: FastAPI, client: TestClient, db_session: Session
) -> None:
    register(client)
    token = cookie(client, "refresh_token")

    response = request_with_cookies(app, "POST", LOGOUT, {"refresh_token": token})

    assert response.status_code == 204
    assert row_for_token(db_session, token).revoked_at is not None


def test_logout_is_consistent_when_not_logged_in_or_when_repeated(
    app: FastAPI, client: TestClient
) -> None:
    anonymous = request_with_cookies(app, "POST", LOGOUT, {}, csrf=False)
    garbage = request_with_cookies(app, "POST", LOGOUT, {"refresh_token": "garbage"})
    register(client)
    first = logout(client)
    second = logout(client)

    for response in (anonymous, garbage, first, second):
        assert response.status_code == 204
        assert_cookies_cleared(response)
