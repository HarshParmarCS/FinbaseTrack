"""Fixes from the backend audit: input robustness, log hygiene, response headers."""

import logging
from typing import Any

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.exc import DataError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.session import get_engine
from app.main import create_app
from tests.auth.helpers import login, register
from tests.projects.helpers import PROJECTS, Actor
from tests.tasks.helpers import TASKS, Team, error_of, project_tasks

NUL = "bad\u0000value"


# ---- NUL characters are a validation error, never a 500 ------------------------------------------


@pytest.mark.parametrize(
    ("field", "build"),
    [
        ("title", lambda team: ("post", project_tasks(team.pid), {"title": NUL})),
        (
            "description",
            lambda team: ("post", project_tasks(team.pid), {"title": "ok", "description": NUL}),
        ),
        ("name", lambda team: ("post", PROJECTS, {"name": NUL})),
        ("description", lambda team: ("post", PROJECTS, {"name": "ok", "description": NUL})),
    ],
    ids=["task-title", "task-description", "project-name", "project-description"],
)
def test_nul_characters_in_create_requests_are_rejected_with_422(
    team: Team, field: str, build: Any
) -> None:
    method, url, body = build(team)

    response = getattr(team.ben, method)(url, body)

    assert response.status_code == 422
    assert error_of(response)["code"] == "VALIDATION_ERROR"
    assert field in [d["field"] for d in error_of(response)["details"]]


def test_nul_characters_in_updates_are_rejected_with_422(team: Team) -> None:
    task = team.new_task(team.ben)

    assert team.ben.patch(f"{TASKS}/{task['id']}", {"title": NUL}).status_code == 422
    assert team.ben.patch(f"{TASKS}/{task['id']}", {"description": NUL}).status_code == 422
    assert team.ana.patch(f"{PROJECTS}/{team.pid}", {"name": NUL}).status_code == 422
    assert team.ana.patch(f"{PROJECTS}/{team.pid}", {"description": NUL}).status_code == 422


def test_nul_characters_in_search_are_rejected_with_422(team: Team) -> None:
    assert team.ben.get(project_tasks(team.pid), params={"q": "a\x00b"}).status_code == 422
    assert team.ben.get(PROJECTS, params={"q": "a\x00b"}).status_code == 422


def test_nul_characters_in_a_registration_name_are_rejected_with_422(app: FastAPI) -> None:
    client = TestClient(app, raise_server_exceptions=False)

    response = register(client, name=NUL)

    assert response.status_code == 422


def test_normal_unicode_text_is_still_accepted(team: Team) -> None:
    data = team.new_task(team.ben, title="Zażółć gęślą jaźń 日本語 😀", description="é" * 100)

    assert data["title"] == "Zażółć gęślą jaźń 日本語 😀"


# ---- pagination cannot overflow the database ----


@pytest.mark.parametrize("page", [100_001, 10**9, 10**20])
def test_an_oversized_page_number_is_a_validation_error(team: Team, page: int) -> None:
    for url in (project_tasks(team.pid), PROJECTS, "/api/v1/dashboard/activity"):
        assert team.ben.get(url, params={"page": page}).status_code == 422


def test_the_largest_allowed_page_is_an_ordinary_empty_page(team: Team) -> None:
    response = team.ben.get(project_tasks(team.pid), params={"page": 100_000, "limit": 100})

    assert response.status_code == 200
    assert response.json()["data"] == []


# ---- database errors never become 500s or leak values ----


def probe_app(app: FastAPI) -> FastAPI:
    router = APIRouter()

    @router.get("/probe/data-error")
    def data_error() -> None:
        raise DataError(
            "INSERT INTO tasks (title) VALUES (%(title)s)",
            {"title": "secret-parameter-value"},
            Exception("value too long for column\nDETAIL: secret-parameter-value"),
        )

    app.include_router(router)
    return app


def test_a_database_data_error_is_a_422_that_logs_only_the_reason(
    app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    client = TestClient(probe_app(app), raise_server_exceptions=False)

    with caplog.at_level(logging.WARNING):
        response = client.get("/probe/data-error")

    assert response.status_code == 422
    assert error_of(response)["code"] == "VALIDATION_ERROR"
    assert "secret-parameter-value" not in response.text
    assert "value too long for column" in caplog.text
    assert "secret-parameter-value" not in caplog.text  # only the first line of the reason


def test_sql_parameters_are_never_included_in_database_errors() -> None:
    engine = get_engine()

    with pytest.raises(DataError) as info, engine.connect() as connection:
        connection.execute(text("select cast(:v as text)"), {"v": "marker\x00confidential"})

    assert engine.hide_parameters is True
    assert "confidential" not in str(info.value)
    assert "[parameters" not in str(info.value)


# ---- response headers ----


@pytest.mark.parametrize(
    "path", ["/api/v1/health", "/api/v1/auth/me", "/api/v1/projects", "/api/v1/nope"]
)
def test_api_responses_are_never_cacheable_and_not_sniffable(ana: Actor, path: str) -> None:
    response = ana.get(path)

    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "X-Request-ID" in response.headers


def test_authentication_responses_are_not_cacheable(app: FastAPI) -> None:
    client = TestClient(app, raise_server_exceptions=False)

    registered = register(client)
    logged_in = login(client)

    assert registered.headers["Cache-Control"] == "no-store"
    assert logged_in.headers["Cache-Control"] == "no-store"


def test_error_responses_carry_the_hardening_headers_too(team: Team) -> None:
    hidden = team.dan.get(project_tasks(team.pid))
    rejected = team.ben.client.post(PROJECTS, json={"name": "no csrf"})

    for response in (hidden, rejected):
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_documentation_pages_get_nosniff_but_are_not_marked_no_store(app: FastAPI) -> None:
    response = TestClient(app).get("/docs")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "Cache-Control" not in response.headers


def test_hsts_is_sent_only_when_the_deployment_uses_https(app: FastAPI) -> None:
    assert "Strict-Transport-Security" not in TestClient(app).get("/api/v1/health").headers

    https_settings = Settings(
        _env_file=None,
        database_url=get_settings().database_url,
        jwt_secret_key="s" * 40,
        environment="production",
        cookie_secure=True,
    )
    secure_app = create_app(https_settings)
    response = TestClient(secure_app).get("/api/v1/health")

    assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"


# ---- the password hash is only read when it is needed ----


def test_only_login_ever_selects_the_password_hash(team: Team, db_session: Session) -> None:
    task = team.complete_task(team.ben)
    statements: list[str] = []
    connection = db_session.connection()

    def capture(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        statements.append(statement)

    def run(request: Any) -> list[str]:
        db_session.expunge_all()  # force fresh loads: nothing may be answered from memory
        statements.clear()
        event.listen(connection, "before_cursor_execute", capture)
        try:
            request()
        finally:
            event.remove(connection, "before_cursor_execute", capture)
        return [s for s in statements if "password_hash" in s]

    pid, tid = team.pid, task["id"]
    reads: dict[str, Any] = {
        "current user": lambda: team.ben.get("/api/v1/auth/me"),
        "project list": lambda: team.ben.get(PROJECTS),
        "project detail": lambda: team.ben.get(f"{PROJECTS}/{pid}"),
        "members": lambda: team.ben.get(f"{PROJECTS}/{pid}/members"),
        "task list": lambda: team.ben.get(project_tasks(pid)),
        "task detail": lambda: team.ben.get(f"{TASKS}/{tid}"),
        "task update": lambda: team.ben.patch(f"{TASKS}/{tid}", {"title": "Renamed"}),
        "task status": lambda: team.ben.patch(f"{TASKS}/{tid}/status", {"status": "in_progress"}),
        "dashboard": lambda: team.ben.get("/api/v1/dashboard/stats"),
        "activity feed": lambda: team.ben.get("/api/v1/dashboard/activity"),
        "project activity": lambda: team.ben.get(f"{PROJECTS}/{pid}/activity"),
    }
    for name, request in reads.items():
        assert run(request) == [], f"{name} selected password_hash"

    client = TestClient(team.ben.client.app, raise_server_exceptions=False)
    assert run(lambda: login(client, email=team.ben.email, password="correct-horse-battery")), (
        "login must load the password hash to verify the password"
    )
