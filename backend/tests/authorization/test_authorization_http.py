"""401 (not authenticated) versus 403 (not allowed) versus 404 (not visible), end to end.

No project or task API exists yet, so a throwaway probe router drives the real dependencies:
get_current_user for authentication and the authorization dependency for access.
"""

import uuid
from typing import Any

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.authorization.context import TaskChanges
from app.authorization.dependencies import AuthorizationServiceDep
from app.authorization.engine import PolicyEngine
from app.authorization.policies import PolicyConfigError
from app.core.config import Settings
from app.main import create_app
from app.models import TaskStatus
from tests.auth.helpers import get_user, register
from tests.factories import add_member, make_project, make_task

router = APIRouter()


@router.get("/probe/projects/{project_id}/delete-check")
def probe_project_delete(
    project_id: uuid.UUID, user: CurrentUser, authz: AuthorizationServiceDep
) -> dict[str, str]:
    authz.require(user, "project.delete", project_id=project_id)
    return {"result": "allowed"}


@router.get("/probe/projects/{project_id}/view-check")
def probe_project_view(
    project_id: uuid.UUID, user: CurrentUser, authz: AuthorizationServiceDep
) -> dict[str, str]:
    authz.require(user, "project.view", project_id=project_id)
    return {"result": "allowed"}


@router.get("/probe/tasks/{task_id}/delete-check")
def probe_task_delete(
    task_id: uuid.UUID, user: CurrentUser, authz: AuthorizationServiceDep
) -> dict[str, str]:
    authz.require(user, "task.delete", task_id=task_id)
    return {"result": "allowed"}


@router.get("/probe/tasks/{task_id}/complete-check")
def probe_task_complete(
    task_id: uuid.UUID, user: CurrentUser, authz: AuthorizationServiceDep
) -> dict[str, str]:
    authz.require_task_update(user, task_id, TaskChanges(status="completed"))
    return {"result": "allowed"}


@pytest.fixture
def probed_app(app: FastAPI) -> FastAPI:
    app.include_router(router)
    return app


def session_for(app: FastAPI, email: str) -> TestClient:
    client = TestClient(app, raise_server_exceptions=False)
    assert register(client, email=email, name=email.split("@")[0]).status_code == 201
    return client


class Scene:
    def __init__(self, app: FastAPI, db: Session) -> None:
        self.owner_client = session_for(app, "owner@example.com")
        self.member_client = session_for(app, "member@example.com")
        self.outsider_client = session_for(app, "outsider@example.com")
        owner = get_user(db, "owner@example.com")
        self.member = get_user(db, "member@example.com")
        self.project = make_project(db, owner)
        add_member(db, self.project, self.member)
        self.db = db
        self.owner = owner


@pytest.fixture
def scene(probed_app: FastAPI, db_session: Session) -> Scene:
    return Scene(probed_app, db_session)


def error(response: Any) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return body


def test_unauthenticated_request_is_401_not_403(probed_app: FastAPI, scene: Scene) -> None:
    anonymous = TestClient(probed_app, raise_server_exceptions=False)

    response = anonymous.get(f"/probe/projects/{scene.project.id}/delete-check")

    assert response.status_code == 401
    assert error(response)["code"] == "UNAUTHENTICATED"


def test_invalid_token_is_401_not_403(probed_app: FastAPI, scene: Scene) -> None:
    client = TestClient(probed_app, raise_server_exceptions=False)
    client.cookies.set("access_token", "garbage")

    assert client.get(f"/probe/projects/{scene.project.id}/delete-check").status_code == 401


def test_member_who_is_not_the_owner_is_403_with_the_policy_id(scene: Scene) -> None:
    response = scene.member_client.get(f"/probe/projects/{scene.project.id}/delete-check")

    assert response.status_code == 403
    body = error(response)
    assert body["code"] == "FORBIDDEN"
    assert body["details"][0]["policy_id"] == "project-delete"
    assert body["message"] == "Only the project owner can delete a project."


def test_owner_is_allowed(scene: Scene) -> None:
    response = scene.owner_client.get(f"/probe/projects/{scene.project.id}/delete-check")

    assert response.status_code == 200
    assert response.json() == {"result": "allowed"}


def test_non_member_is_404_and_looks_identical_to_a_missing_project(scene: Scene) -> None:
    hidden = scene.outsider_client.get(f"/probe/projects/{scene.project.id}/view-check")
    missing = scene.outsider_client.get(f"/probe/projects/{uuid.uuid4()}/view-check")

    assert hidden.status_code == missing.status_code == 404
    assert error(hidden)["code"] == error(missing)["code"] == "NOT_FOUND"
    assert error(hidden)["message"] == error(missing)["message"]
    assert error(hidden)["details"] == error(missing)["details"] == []


def test_removed_member_gets_404_on_the_next_request(scene: Scene) -> None:
    url = f"/probe/projects/{scene.project.id}/view-check"
    assert scene.member_client.get(url).status_code == 200

    scene.db.execute(
        text("delete from project_members where user_id = :u"),
        {"u": scene.member.id},
    )

    assert scene.member_client.get(url).status_code == 404


def test_inactive_user_is_rejected_by_authentication_before_authorization(scene: Scene) -> None:
    scene.member.is_active = False
    scene.db.flush()

    response = scene.member_client.get(f"/probe/projects/{scene.project.id}/view-check")

    assert response.status_code == 401


def test_owner_deleting_an_in_progress_task_is_403(scene: Scene) -> None:
    task = make_task(scene.db, scene.project, scene.owner, status=TaskStatus.IN_PROGRESS)

    response = scene.owner_client.get(f"/probe/tasks/{task.id}/delete-check")

    assert response.status_code == 403
    assert error(response)["details"][0]["policy_id"] == "task-delete"


def test_owner_deleting_a_todo_task_is_allowed(scene: Scene) -> None:
    task = make_task(scene.db, scene.project, scene.owner, status=TaskStatus.TODO)

    assert scene.owner_client.get(f"/probe/tasks/{task.id}/delete-check").status_code == 200


def test_guessing_a_task_id_in_someone_elses_project_is_404(scene: Scene) -> None:
    task = make_task(scene.db, scene.project, scene.owner)

    response = scene.outsider_client.get(f"/probe/tasks/{task.id}/delete-check")

    assert response.status_code == 404


def test_completing_a_task_that_has_no_assignee_is_403_from_the_completion_policy(
    scene: Scene,
) -> None:
    task = make_task(scene.db, scene.project, scene.member, description="d", priority="high")

    response = scene.member_client.get(f"/probe/tasks/{task.id}/complete-check")

    assert response.status_code == 403
    assert error(response)["details"][0]["policy_id"] == "task-complete"


# ---- startup: the policy file is validated when the app is created ---------------


def test_the_application_loads_and_exposes_the_validated_engine(app: FastAPI) -> None:
    engine = app.state.policy_engine

    assert isinstance(engine, PolicyEngine)
    assert len(engine.registry) == 9


def test_the_application_refuses_to_start_with_an_invalid_policy_file(tmp_path: Any) -> None:
    broken = tmp_path / "policies.json"
    broken.write_text('{"version": 1, "default_effect": "allow", "policies": []}')
    settings = Settings(
        _env_file=None,
        database_url="postgresql://u:p@localhost/db",
        jwt_secret_key="s" * 40,
        policy_file=broken,
    )

    with pytest.raises(PolicyConfigError):
        create_app(settings)


def test_the_application_refuses_to_start_when_the_policy_file_is_missing(tmp_path: Any) -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql://u:p@localhost/db",
        jwt_secret_key="s" * 40,
        policy_file=tmp_path / "missing.json",
    )

    with pytest.raises(PolicyConfigError, match="Cannot read"):
        create_app(settings)
