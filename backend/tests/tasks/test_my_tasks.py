"""GET /me/tasks: the caller's assigned tasks across all of their projects."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from tests.projects.helpers import PROJECTS, Actor
from tests.tasks.helpers import TASKS, Team, ids, project_tasks, titles

MY_TASKS = "/api/v1/me/tasks"


def my_tasks(actor: Actor, **params: Any) -> Any:
    response = actor.get(MY_TASKS, params=params)
    assert response.status_code == 200, response.text
    return response


def own_project_task(actor: Actor, project_name: str, **fields: Any) -> tuple[str, dict[str, Any]]:
    """A project owned by ``actor`` with one task assigned to ``actor``."""
    project = actor.create_project(project_name)
    fields.setdefault("title", f"{project_name} task")
    response = actor.post(project_tasks(project["id"]), {**fields, "assignee_id": str(actor.id)})
    assert response.status_code == 201, response.text
    return str(project["id"]), response.json()["data"]


def move_to_completed(actor: Actor, task_id: str) -> None:
    for step in ("in_progress", "completed"):
        response = actor.patch(f"{TASKS}/{task_id}/status", {"status": step})
        assert response.status_code == 200, response.text


# ---- scoping ---------------------------------------------------------------------------------


def test_lists_the_callers_tasks_across_all_of_their_projects(team: Team) -> None:
    in_team = team.new_task(title="Team task", assignee_id=str(team.cy.id))
    own_pid, in_own = own_project_task(team.cy, "Cy side project")

    response = my_tasks(team.cy)

    assert sorted(ids(response)) == sorted([in_team["id"], in_own["id"]])
    assert response.json()["meta"]["total"] == 2
    projects = {item["id"]: item["project"] for item in response.json()["data"]}
    assert projects[in_team["id"]] == {"id": team.pid, "name": "Team project", "status": "active"}
    assert projects[in_own["id"]] == {"id": own_pid, "name": "Cy side project", "status": "active"}


def test_tasks_assigned_to_other_people_or_nobody_never_appear(team: Team) -> None:
    team.new_task(title="Ben's task", assignee_id=str(team.ben.id))
    team.new_task(title="Nobody's task")
    own_project_task(team.dan, "Dan only")  # dan's project: cy is not a member

    assert my_tasks(team.cy).json()["data"] == []
    assert titles(my_tasks(team.ben)) == ["Ben's task"]
    assert titles(my_tasks(team.dan)) == ["Dan only task"]


def test_a_removed_member_no_longer_sees_tasks_of_that_project(team: Team) -> None:
    team.new_task(title="Team task", assignee_id=str(team.cy.id))
    own_project_task(team.cy, "Cy side project")

    assert team.ana.delete(f"{PROJECTS}/{team.pid}/members/{team.cy.id}").status_code == 204

    assert titles(my_tasks(team.cy)) == ["Cy side project task"]


def test_unauthenticated_requests_get_401(app: FastAPI) -> None:
    anonymous = TestClient(app, raise_server_exceptions=False)
    assert anonymous.get(MY_TASKS).status_code == 401


# ---- response --------------------------------------------------------------------------------


def test_each_task_has_the_full_task_fields_and_policy_based_actions(team: Team) -> None:
    team.new_task(title="Team task", description="Details", assignee_id=str(team.cy.id))
    own_project_task(team.cy, "Cy side project")

    items = {item["title"]: item for item in my_tasks(team.cy).json()["data"]}
    team_task = items["Team task"]

    assert team_task["description"] == "Details"
    assert team_task["creator"]["id"] == str(team.ben.id)
    assert team_task["assignee"]["id"] == str(team.cy.id)
    for field in ("status", "priority", "due_date", "position", "completed_at", "created_at"):
        assert field in team_task
    # The assignee may update. Only the project owner may delete a todo task.
    assert "update" in team_task["allowed_actions"]
    assert "delete" not in team_task["allowed_actions"]
    assert "delete" in items["Cy side project task"]["allowed_actions"]


def test_completed_tasks_are_included_unless_filtered_out(team: Team) -> None:
    done = team.complete_task(assignee=team.cy)
    move_to_completed(team.cy, done["id"])
    open_task = team.new_task(title="Still open", assignee_id=str(team.cy.id))

    assert sorted(ids(my_tasks(team.cy))) == sorted([done["id"], open_task["id"]])
    open_only = my_tasks(team.cy, status=["todo", "in_progress"])
    assert ids(open_only) == [open_task["id"]]


# ---- filters, sorting, pagination ------------------------------------------------------------


def test_filters_by_search_priority_and_project(team: Team) -> None:
    team.new_task(title="Design login page", priority="high", assignee_id=str(team.cy.id))
    team.new_task(title="Write docs", priority="low", assignee_id=str(team.cy.id))
    own_pid, _ = own_project_task(team.cy, "Cy side project", priority="high")

    assert titles(my_tasks(team.cy, q="LOGIN")) == ["Design login page"]
    assert sorted(titles(my_tasks(team.cy, priority="high"))) == [
        "Cy side project task",
        "Design login page",
    ]
    assert titles(my_tasks(team.cy, project_id=own_pid)) == ["Cy side project task"]


def test_a_project_the_caller_is_not_in_gives_an_empty_list(team: Team) -> None:
    dan_pid, _ = own_project_task(team.dan, "Dan only")
    team.new_task(title="Team task", assignee_id=str(team.cy.id))

    assert my_tasks(team.cy, project_id=dan_pid).json()["data"] == []
    assert my_tasks(team.cy, project_id=str(uuid.uuid4())).json()["data"] == []


def test_due_date_and_overdue_filters(team: Team, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.task_service.utcnow", lambda: datetime(2026, 11, 15, 8, 0, tzinfo=UTC)
    )
    team.new_task(title="Late", due_date="2026-11-10", assignee_id=str(team.cy.id))
    team.new_task(title="Today", due_date="2026-11-15", assignee_id=str(team.cy.id))
    team.new_task(title="Later", due_date="2026-12-20", assignee_id=str(team.cy.id))
    team.new_task(title="Undated", assignee_id=str(team.cy.id))

    assert titles(my_tasks(team.cy, overdue="true")) == ["Late"]
    assert sorted(titles(my_tasks(team.cy, overdue="false"))) == ["Later", "Today", "Undated"]
    window = my_tasks(team.cy, due_after="2026-11-11", due_before="2026-11-30")
    assert titles(window) == ["Today"]


def test_sorts_by_due_date_with_undated_tasks_last(team: Team) -> None:
    team.new_task(title="Undated", assignee_id=str(team.cy.id))
    team.new_task(title="Later", due_date="2026-12-20", assignee_id=str(team.cy.id))
    own_project_task(team.cy, "Cy side project", due_date="2026-11-20")

    assert titles(my_tasks(team.cy, sort="due_date")) == [
        "Cy side project task",
        "Later",
        "Undated",
    ]


def test_paginates_with_the_standard_meta(team: Team) -> None:
    for index in range(3):
        team.new_task(title=f"T{index}", assignee_id=str(team.cy.id))

    first = my_tasks(team.cy, page=1, limit=2)
    response = my_tasks(team.cy, page=2, limit=2)

    assert len(ids(first)) == 2 and len(ids(response)) == 1
    assert sorted(titles(first) + titles(response)) == ["T0", "T1", "T2"]
    assert response.json()["meta"] == {"page": 2, "page_size": 2, "total": 3, "total_pages": 2}


@pytest.mark.parametrize(
    "params",
    [
        {"project_id": "not-a-uuid"},
        {"status": "done"},
        {"sort": "title"},
        {"overdue": "maybe"},
        {"q": "x" * 101},
    ],
)
def test_invalid_query_parameters_give_422(team: Team, params: dict[str, Any]) -> None:
    assert team.cy.get(MY_TASKS, params=params).status_code == 422


# ---- efficiency ------------------------------------------------------------------------------


def test_uses_the_same_number_of_queries_however_many_tasks_exist(
    team: Team, db_session: Session
) -> None:
    statements: list[str] = []
    connection = db_session.connection()

    def count(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        statements.append(statement)

    def queries_for_list() -> int:
        statements.clear()
        event.listen(connection, "before_cursor_execute", count)
        try:
            my_tasks(team.cy, limit=100)
        finally:
            event.remove(connection, "before_cursor_execute", count)
        return len(statements)

    team.new_task(title="T0", assignee_id=str(team.cy.id))
    few = queries_for_list()
    for index in range(1, 15):
        team.new_task(title=f"T{index}", assignee_id=str(team.cy.id))
    own_project_task(team.cy, "Second project")
    own_project_task(team.cy, "Third project")
    many = queries_for_list()

    assert few == many  # projects, creators and assignees come from joins: no N+1
    assert many <= 6
