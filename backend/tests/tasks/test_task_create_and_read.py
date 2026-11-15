"""Creating and reading tasks (single task)."""

import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Task
from app.repositories.activity_repository import ActivityRepository
from tests.tasks.helpers import TASKS, Team, error_of, project_tasks, task_activity, task_row

# ---- create -----------------------------------------------------------------------------------


def test_a_member_creates_a_task_with_sensible_defaults(team: Team) -> None:
    response = team.ben.post(project_tasks(team.pid), {"title": "Design login page"})

    assert response.status_code == 201
    data = response.json()["data"]
    assert uuid.UUID(data["id"])
    assert data["project_id"] == team.pid
    assert data["title"] == "Design login page"
    assert data["description"] is None
    assert data["status"] == "todo"
    assert data["priority"] == "medium"
    assert data["assignee"] is None
    assert data["due_date"] is None
    assert data["completed_at"] is None
    assert data["position"] == 1024.0
    assert data["creator"] == {"id": str(team.ben.id), "email": team.ben.email, "name": "Ben"}
    assert data["created_at"] and data["updated_at"]


def test_the_creator_is_always_the_authenticated_user(team: Team, db_session: Session) -> None:
    data = team.new_task(team.cy)

    row = task_row(db_session, data["id"])
    assert row is not None and row.creator_id == team.cy.id
    assert row.project_id == uuid.UUID(team.pid)


def test_a_task_can_be_created_with_every_field(team: Team) -> None:
    data = team.new_task(
        team.ben,
        title="  Write docs  ",
        description="Explain the flow",
        priority="high",
        assignee_id=str(team.cy.id),
        due_date="2026-12-24",
    )

    assert data["title"] == "Write docs"
    assert data["description"] == "Explain the flow"
    assert data["priority"] == "high"
    assert data["assignee"] == {"id": str(team.cy.id), "email": team.cy.email, "name": "Cy"}
    assert data["due_date"] == "2026-12-24"


def test_the_project_owner_can_create_tasks_and_assign_themselves(team: Team) -> None:
    data = team.new_task(team.ana, assignee_id=str(team.ana.id))

    assert data["creator"]["id"] == data["assignee"]["id"] == str(team.ana.id)


def test_allowed_actions_reflect_what_the_creator_may_do(team: Team) -> None:
    by_member = team.new_task(team.ben)
    by_owner = team.new_task(team.ana)

    # A member who created a task may update it. Only the owner may delete (todo tasks).
    # Nobody may "complete" it yet: it has no assignee.
    assert by_member["allowed_actions"] == ["update"]
    assert by_owner["allowed_actions"] == ["update", "delete"]


def test_a_new_task_is_placed_at_the_end_of_its_status_column(team: Team) -> None:
    first = team.new_task(title="one")
    second = team.new_task(title="two")
    in_progress = team.new_task(title="three", status="in_progress")

    assert (first["position"], second["position"]) == (1024.0, 2048.0)
    assert in_progress["position"] == 1024.0  # another column starts again


def test_a_task_can_start_in_progress(team: Team) -> None:
    assert team.new_task(status="in_progress")["status"] == "in_progress"


@pytest.mark.parametrize(
    "spoof", ["creator_id", "project_id", "id", "position", "completed_at", "created_at"]
)
def test_server_controlled_fields_cannot_be_sent(team: Team, spoof: str) -> None:
    value: Any = str(team.cy.id) if spoof.endswith("_id") else "2026-01-01"

    response = team.ben.post(project_tasks(team.pid), {"title": "X", spoof: value})

    assert response.status_code == 422
    assert spoof in [d["field"] for d in error_of(response)["details"]]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": ""},
        {"title": "   "},
        {"title": "x" * 201},
        {"title": None},
        {"title": "ok", "description": "d" * 5001},
        {"title": "ok", "priority": "urgent"},
        {"title": "ok", "status": "blocked"},
        {"title": "ok", "due_date": "2026-13-45"},
        {"title": "ok", "due_date": "tomorrow"},
        {"title": "ok", "assignee_id": "not-a-uuid"},
    ],
)
def test_invalid_task_input_is_rejected(team: Team, payload: dict[str, Any]) -> None:
    response = team.ben.post(project_tasks(team.pid), payload)

    assert response.status_code == 422
    assert error_of(response)["code"] == "VALIDATION_ERROR"


def test_a_due_date_in_the_past_is_allowed(team: Team) -> None:
    assert team.new_task(due_date="2020-01-01")["due_date"] == "2020-01-01"


def test_blank_description_is_stored_as_null(team: Team) -> None:
    assert team.new_task(description="   ")["description"] is None


# -- membership ----------------------------------------------------------------------------------


def test_a_non_member_cannot_create_a_task(team: Team, db_session: Session) -> None:
    response = team.dan.post(project_tasks(team.pid), {"title": "Sneaky"})

    assert response.status_code == 404
    assert db_session.scalar(select(func.count()).select_from(Task)) == 0


def test_creating_in_a_missing_project_is_404_just_like_a_hidden_one(team: Team) -> None:
    hidden = team.dan.post(project_tasks(team.pid), {"title": "X"})
    missing = team.dan.post(project_tasks(str(uuid.uuid4())), {"title": "X"})

    assert hidden.status_code == missing.status_code == 404
    assert error_of(hidden)["message"] == error_of(missing)["message"]


def test_creating_requires_authentication_and_csrf(app: FastAPI, team: Team) -> None:
    anonymous = TestClient(app, raise_server_exceptions=False)

    assert anonymous.post(project_tasks(team.pid), json={"title": "X"}).status_code == 401
    assert team.ben.client.post(project_tasks(team.pid), json={"title": "X"}).status_code == 403


# -- assignee --------------------------------------------------------------------------------------


def test_the_assignee_must_be_a_project_member(team: Team, db_session: Session) -> None:
    response = team.ben.post(
        project_tasks(team.pid), {"title": "X", "assignee_id": str(team.dan.id)}
    )

    assert response.status_code == 422
    assert error_of(response)["code"] == "BUSINESS_RULE_VIOLATION"
    assert "member of the project" in error_of(response)["message"]
    assert db_session.scalar(select(func.count()).select_from(Task)) == 0


def test_an_assignee_that_is_not_even_a_user_is_rejected(team: Team) -> None:
    response = team.ben.post(
        project_tasks(team.pid), {"title": "X", "assignee_id": str(uuid.uuid4())}
    )

    assert response.status_code == 422
    assert error_of(response)["code"] == "BUSINESS_RULE_VIOLATION"


def test_a_removed_member_can_no_longer_be_assigned(team: Team) -> None:
    team.ana.delete(f"/api/v1/projects/{team.pid}/members/{team.cy.id}")

    response = team.ben.post(
        project_tasks(team.pid), {"title": "X", "assignee_id": str(team.cy.id)}
    )

    assert response.status_code == 422


def test_a_member_of_another_project_cannot_be_assigned_here(team: Team) -> None:
    other = team.dan.create_project("Dan's project")
    assert other["id"] != team.pid

    response = team.ben.post(
        project_tasks(team.pid), {"title": "X", "assignee_id": str(team.dan.id)}
    )

    assert response.status_code == 422


# -- creating directly as completed ------------------------------------------------------------


def test_a_task_cannot_be_created_completed_without_the_required_information(team: Team) -> None:
    response = team.ben.post(
        project_tasks(team.pid), {"title": "Done already", "status": "completed"}
    )

    assert response.status_code == 403
    assert error_of(response)["details"][0]["policy_id"] == "task-complete"


def test_a_task_can_be_created_completed_when_everything_is_filled_in(
    team: Team, db_session: Session
) -> None:
    data = team.new_task(
        title="Done already",
        status="completed",
        description="Finished before it was filed",
        priority="low",
        due_date="2026-12-01",
        assignee_id=str(team.cy.id),
    )

    assert data["status"] == "completed"
    assert data["completed_at"] is not None


# -- activity and atomicity ------------------------------------------------------------------------


def test_creating_a_task_records_activity(team: Team, db_session: Session) -> None:
    data = team.new_task(team.ben, title="Plan", assignee_id=str(team.cy.id))

    entry = task_activity(db_session, data["id"], "task.created")[0]

    assert entry.user_id == team.ben.id
    assert entry.project_id == uuid.UUID(team.pid)
    assert entry.meta == {
        "title": "Plan",
        "status": "todo",
        "priority": "medium",
        "assignee_id": str(team.cy.id),
    }


def test_creating_a_task_is_all_or_nothing(
    team: Team, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("activity failed")

    monkeypatch.setattr(ActivityRepository, "record", explode)

    response = team.ben.post(project_tasks(team.pid), {"title": "Doomed"})

    assert response.status_code == 500
    db_session.expire_all()
    assert db_session.scalar(select(func.count()).select_from(Task)) == 0


# ---- read one -----------------------------------------------------------------------------------


def test_a_member_reads_the_complete_task_with_creator_and_assignee(team: Team) -> None:
    task = team.complete_task(team.ben, assignee=team.cy)

    response = team.ana.get(f"{TASKS}/{task['id']}")  # the owner reads a task they did not create

    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == {
        "id",
        "project_id",
        "title",
        "description",
        "status",
        "priority",
        "assignee",
        "creator",
        "due_date",
        "position",
        "completed_at",
        "allowed_actions",
        "created_at",
        "updated_at",
    }
    assert data["creator"]["name"] == "Ben"
    assert data["assignee"]["name"] == "Cy"
    assert data["description"] == "Wireframes and copy"
    assert data["due_date"] == "2026-12-01"


def test_allowed_actions_depend_on_who_is_asking(team: Team) -> None:
    task = team.complete_task(team.ben, assignee=team.cy)  # ben creates, cy is assignee
    url = f"{TASKS}/{task['id']}"

    as_creator = team.ben.get(url).json()["data"]["allowed_actions"]
    as_assignee = team.cy.get(url).json()["data"]["allowed_actions"]
    as_owner = team.ana.get(url).json()["data"]["allowed_actions"]

    assert as_creator == ["update", "complete"]
    assert as_assignee == ["update", "complete"]
    assert as_owner == ["delete"]  # the owner may delete a todo task but not update or complete it


def test_a_non_member_cannot_read_a_task(team: Team) -> None:
    task = team.new_task()

    response = team.dan.get(f"{TASKS}/{task['id']}")

    assert response.status_code == 404
    assert error_of(response)["code"] == "NOT_FOUND"


def test_a_hidden_task_looks_exactly_like_a_missing_one(team: Team) -> None:
    task = team.new_task()

    hidden = team.dan.get(f"{TASKS}/{task['id']}")
    missing = team.dan.get(f"{TASKS}/{uuid.uuid4()}")

    assert hidden.status_code == missing.status_code == 404
    assert error_of(hidden) | {"request_id": None} == error_of(missing) | {"request_id": None}


def test_reading_validates_the_id_and_requires_authentication(app: FastAPI, team: Team) -> None:
    task = team.new_task()
    anonymous = TestClient(app, raise_server_exceptions=False)

    assert team.ben.get(f"{TASKS}/not-a-uuid").status_code == 422
    assert anonymous.get(f"{TASKS}/{task['id']}").status_code == 401
