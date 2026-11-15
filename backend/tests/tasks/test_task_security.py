"""Access to tasks through guessed UUIDs, removed members, and enforcement wiring."""

import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.authorization.service import AuthorizationService
from app.models import ActivityLog, User
from tests.projects.helpers import PROJECTS
from tests.tasks.helpers import TASKS, Team, error_of, project_tasks, task_row

ENDPOINTS = [
    ("get", "{task}", None),
    ("patch", "{task}", {"title": "hijack"}),
    ("patch", "{task}/status", {"status": "in_progress"}),
    ("delete", "{task}", None),
]


def call(actor: Any, method: str, template: str, task_id: str, body: Any) -> Any:
    url = f"{TASKS}/" + template.format(task=task_id)
    if method == "get":
        return actor.get(url)
    if method == "delete":
        return actor.delete(url)
    return actor.patch(url, body)


# ---- guessing UUIDs ---


@pytest.mark.parametrize(("method", "template", "body"), ENDPOINTS)
def test_an_outsider_guessing_a_real_task_id_learns_nothing(
    team: Team, db_session: Session, method: str, template: str, body: Any
) -> None:
    task = team.new_task(team.ben, title="Confidential")

    real = call(team.dan, method, template, task["id"], body)
    invented = call(team.dan, method, template, str(uuid.uuid4()), body)

    assert real.status_code == invented.status_code == 404
    real_error, invented_error = error_of(real), error_of(invented)
    assert real_error["code"] == invented_error["code"] == "NOT_FOUND"
    assert real_error["message"] == invented_error["message"]
    assert real_error["details"] == invented_error["details"] == []
    assert "Confidential" not in real.text
    row = task_row(db_session, task["id"])
    assert row is not None and row.title == "Confidential" and row.status == "todo"


@pytest.mark.parametrize(("method", "template", "body"), ENDPOINTS)
def test_a_member_of_another_project_cannot_reach_the_task_either(
    team: Team, method: str, template: str, body: Any
) -> None:
    task = team.new_task(team.ben)
    team.dan.create_project("Dan's own project")  # dan is a member of SOMETHING, just not this

    assert call(team.dan, method, template, task["id"], body).status_code == 404


def test_an_outsider_cannot_list_create_or_probe_a_project_by_id(team: Team) -> None:
    assert team.dan.get(project_tasks(team.pid)).status_code == 404
    assert team.dan.post(project_tasks(team.pid), {"title": "X"}).status_code == 404
    assert team.dan.get(project_tasks(str(uuid.uuid4()))).status_code == 404


def test_a_task_id_cannot_be_used_to_reach_another_projects_data(team: Team) -> None:
    """The project is always derived from the task: a project id in the URL can't be mixed in."""
    other = team.dan.create_project("Dan's project")
    mine = team.new_task(team.ben)

    # Dan owns `other`, but `mine` belongs to the team project.
    assert team.dan.get(f"{TASKS}/{mine['id']}").status_code == 404
    listing = team.dan.get(project_tasks(other["id"]))
    assert listing.status_code == 200 and listing.json()["data"] == []


# ---- removed members ---


def test_a_removed_member_loses_access_to_every_task_endpoint_at_once(team: Team) -> None:
    mine = team.new_task(team.ben, title="Ben's task")
    assigned = team.new_task(team.ana, title="Assigned to Ben", assignee_id=str(team.ben.id))
    assert team.ben.get(f"{TASKS}/{mine['id']}").status_code == 200
    assert team.ben.patch(f"{TASKS}/{assigned['id']}", {"title": "ok"}).status_code == 200

    assert team.ana.delete(f"{PROJECTS}/{team.pid}/members/{team.ben.id}").status_code == 204

    for task in (mine, assigned):
        for method, template, body in ENDPOINTS:
            response = call(team.ben, method, template, task["id"], body)
            assert response.status_code == 404, (method, template, response.text)
    assert team.ben.get(project_tasks(team.pid)).status_code == 404
    assert team.ben.post(project_tasks(team.pid), {"title": "back door"}).status_code == 404


def test_a_removed_members_tasks_stay_but_their_assignments_are_cleared(team: Team) -> None:
    created = team.new_task(team.ben, title="Created by Ben")
    assigned = team.new_task(team.ana, title="Assigned to Ben", assignee_id=str(team.ben.id))

    team.ana.delete(f"{PROJECTS}/{team.pid}/members/{team.ben.id}")

    kept = team.ana.get(f"{TASKS}/{created['id']}").json()["data"]
    cleared = team.ana.get(f"{TASKS}/{assigned['id']}").json()["data"]
    assert kept["creator"]["id"] == str(team.ben.id)  # the creator is part of the history
    assert cleared["assignee"] is None


def test_a_member_who_is_readded_regains_access(team: Team) -> None:
    task = team.new_task(team.ben)
    team.ana.delete(f"{PROJECTS}/{team.pid}/members/{team.ben.id}")
    assert team.ben.get(f"{TASKS}/{task['id']}").status_code == 404

    team.ana.add_member(team.pid, team.ben)

    assert team.ben.get(f"{TASKS}/{task['id']}").status_code == 200


def test_an_inactive_user_is_rejected_by_authentication_first(
    team: Team, db_session: Session
) -> None:
    task = team.new_task(team.ben)
    user = db_session.get(User, team.ben.id)
    assert user is not None
    user.is_active = False
    db_session.flush()

    response = team.ben.get(f"{TASKS}/{task['id']}")

    assert response.status_code == 401
    assert error_of(response)["code"] == "UNAUTHENTICATED"


def test_unauthenticated_requests_get_401_not_404(app: FastAPI, team: Team) -> None:
    task = team.new_task()
    anonymous = TestClient(app, raise_server_exceptions=False)

    assert anonymous.get(f"{TASKS}/{task['id']}").status_code == 401
    assert anonymous.get(f"{TASKS}/{uuid.uuid4()}").status_code == 401  # even for unknown ids


# ---- enforcement wiring ---


def test_every_task_endpoint_asks_the_policy_engine_for_the_right_action(
    team: Team, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []
    original = AuthorizationService.require

    def spy(self: AuthorizationService, user: User, action: Any, **kwargs: Any) -> Any:
        asked.append(str(action))
        return original(self, user, action, **kwargs)

    monkeypatch.setattr(AuthorizationService, "require", spy)
    task = team.new_task(team.ben, assignee_id=str(team.cy.id))
    mark = len(asked)

    team.ben.get(project_tasks(team.pid))
    team.ben.get(f"{TASKS}/{task['id']}")
    team.ben.patch(f"{TASKS}/{task['id']}", {"title": "x"})
    team.ben.patch(f"{TASKS}/{task['id']}/status", {"status": "in_progress"})
    team.ana.patch(f"{TASKS}/{task['id']}/status", {"status": "todo"})  # denied, still asked
    team.ana.delete(f"{TASKS}/{task['id']}")

    assert asked[:mark] == ["task.create"]
    assert asked[mark:] == [
        "project.view",
        "project.view",
        "task.update",
        "task.update",
        "task.update",
        "task.delete",
    ]


def test_activity_rows_for_tasks_contain_no_secrets(team: Team, db_session: Session) -> None:
    task = team.new_task(team.ben, title="Plan", assignee_id=str(team.cy.id))
    team.ben.patch(f"{TASKS}/{task['id']}", {"title": "Plan B"})
    team.ben.patch(f"{TASKS}/{task['id']}/status", {"status": "in_progress"})

    from sqlalchemy import select

    blob = " ".join(str(r.meta) for r in db_session.scalars(select(ActivityLog)))

    assert "password" not in blob.lower() and "argon2" not in blob and "token" not in blob.lower()
