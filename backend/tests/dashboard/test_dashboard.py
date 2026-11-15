"""Dashboard statistics and the activity feeds."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from tests.projects.helpers import PROJECTS, Actor
from tests.tasks.helpers import TASKS, Team, error_of

STATS = "/api/v1/dashboard/stats"
FEED = "/api/v1/dashboard/activity"
FIXED_NOW = datetime(2026, 11, 15, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.dashboard_service.utcnow", lambda: FIXED_NOW)


def stats(actor: Actor) -> dict[str, Any]:
    response = actor.get(STATS)
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()["data"]
    return data


def numbers(data: dict[str, Any]) -> dict[str, int]:
    return {k: v for k, v in data.items() if k != "recent_activity"}


def seed(team: Team) -> None:
    """5 tasks in the team project: 1 overdue, 1 completed, 4 pending, mixed assignees."""
    team.new_task(team.ben, title="Overdue", due_date="2026-11-10", assignee_id=str(team.cy.id))
    team.new_task(
        team.ben,
        title="Running",
        status="in_progress",
        due_date="2026-11-20",
        assignee_id=str(team.ben.id),
    )
    done = team.complete_task(team.ben, assignee=team.cy)
    team.ben.patch(f"{TASKS}/{done['id']}/status", {"status": "in_progress"})
    team.ben.patch(f"{TASKS}/{done['id']}/status", {"status": "completed"})
    team.new_task(team.ben, title="Unscheduled", assignee_id=str(team.cy.id))
    team.new_task(team.ben, title="Due today", due_date="2026-11-15")


# ---- statistics ----


def test_a_new_user_sees_zeros_and_no_activity(ana: Actor) -> None:
    data = stats(ana)

    assert numbers(data) == {
        "total_projects": 0,
        "active_projects": 0,
        "total_tasks": 0,
        "completed_tasks": 0,
        "pending_tasks": 0,
        "overdue_tasks": 0,
        "assigned_to_me": 0,
    }
    assert data["recent_activity"] == []


def test_statistics_follow_the_documented_definitions(team: Team) -> None:
    seed(team)

    data = stats(team.ben)

    assert data["total_projects"] == 1
    assert data["active_projects"] == 1
    assert data["total_tasks"] == 5
    assert data["completed_tasks"] == 1
    assert data["pending_tasks"] == 4  # todo + in_progress
    assert data["overdue_tasks"] == 1  # due before today, not completed; "due today" is not overdue
    assert data["assigned_to_me"] == 1  # Ben: "Running" (completed tasks do not count)


def test_assigned_to_me_depends_on_who_asks(team: Team) -> None:
    seed(team)

    assert stats(team.cy)["assigned_to_me"] == 2  # "Overdue" and "Unscheduled" (the third is done)
    assert stats(team.ana)["assigned_to_me"] == 0


def test_archived_projects_count_as_projects_but_not_as_active(team: Team) -> None:
    team.ana.patch(f"{PROJECTS}/{team.pid}", {"status": "archived"})
    team.ana.create_project("Live one")

    data = stats(team.ana)

    assert (data["total_projects"], data["active_projects"]) == (2, 1)


def test_statistics_combine_every_project_the_user_belongs_to(team: Team) -> None:
    seed(team)
    other = team.ana.create_project("Second")
    team.ana.post(f"{PROJECTS}/{other['id']}/tasks", {"title": "Elsewhere"})

    data = stats(team.ana)

    assert data["total_projects"] == 2
    assert data["total_tasks"] == 6


def test_a_non_member_sees_nothing_of_other_peoples_projects(team: Team) -> None:
    seed(team)

    data = stats(team.dan)

    assert numbers(data) == dict.fromkeys(numbers(data), 0)
    assert data["recent_activity"] == []


def test_a_removed_member_loses_the_statistics_immediately(team: Team) -> None:
    seed(team)
    assert stats(team.cy)["total_tasks"] == 5

    team.ana.delete(f"{PROJECTS}/{team.pid}/members/{team.cy.id}")

    after = stats(team.cy)
    assert after["total_tasks"] == 0
    assert after["total_projects"] == 0
    assert after["recent_activity"] == []


def test_statistics_use_todays_date_in_utc_for_overdue(
    team: Team, monkeypatch: pytest.MonkeyPatch
) -> None:
    team.new_task(team.ben, due_date="2026-11-15")
    assert stats(team.ben)["overdue_tasks"] == 0

    monkeypatch.setattr(
        "app.services.dashboard_service.utcnow", lambda: datetime(2026, 11, 16, 0, 1, tzinfo=UTC)
    )

    assert stats(team.ben)["overdue_tasks"] == 1


def test_statistics_require_authentication(app: FastAPI) -> None:
    anonymous = TestClient(app, raise_server_exceptions=False)

    assert anonymous.get(STATS).status_code == 401
    assert anonymous.get(FEED).status_code == 401


def test_recent_activity_holds_at_most_ten_newest_entries(team: Team, db_session: Session) -> None:
    for index in range(12):
        team.new_task(team.ben, title=f"T{index}")

    data = stats(team.ben)

    assert len(data["recent_activity"]) == 10  # 15 entries exist: 1 project, 2 members, 12 tasks
    assert {a["project_id"] for a in data["recent_activity"]} == {team.pid}


def test_the_dashboard_uses_a_constant_number_of_queries(team: Team, db_session: Session) -> None:
    statements: list[str] = []
    connection = db_session.connection()

    def count(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        statements.append(statement)

    def queries() -> int:
        statements.clear()
        event.listen(connection, "before_cursor_execute", count)
        try:
            assert team.ana.get(STATS).status_code == 200
        finally:
            event.remove(connection, "before_cursor_execute", count)
        return len(statements)

    team.new_task(team.ben)
    few = queries()
    for index in range(30):
        team.new_task(team.ben, title=f"T{index}", assignee_id=str(team.cy.id))
    for index in range(5):
        team.ana.create_project(f"Extra {index}")
    many = queries()

    assert few == many
    assert many <= 6  # current user + projects + tasks + activity (+ a spare)


# ---- the personal feed ----


def make_feed_deterministic(db: Session, project_id: str) -> None:
    """Give each entry its own timestamp (entries made in one test transaction share one)."""
    db.execute(
        text(
            """
            update activity_logs set created_at = timestamp '2026-01-01 00:00:00+00'
                + (sub.n * interval '1 minute')
            from (select id, row_number() over (order by id) as n from activity_logs
                  where project_id = :p) sub
            where activity_logs.id = sub.id
            """
        ),
        {"p": project_id},
    )


def test_the_feed_lists_activity_of_the_users_projects_newest_first(
    team: Team, db_session: Session
) -> None:
    team.new_task(team.ben, title="First")
    team.new_task(team.ben, title="Second")
    make_feed_deterministic(db_session, team.pid)

    response = team.cy.get(FEED, params={"limit": 100})

    assert response.status_code == 200
    items = response.json()["data"]
    stamps = [item["created_at"] for item in items]
    assert stamps == sorted(stamps, reverse=True)
    assert response.json()["meta"]["total"] == len(items) >= 4
    first = items[0]
    assert set(first) == {"id", "user", "project_id", "task_id", "action", "metadata", "created_at"}
    assert set(first["user"]) == {"id", "email", "name"}
    assert first["project_id"] == team.pid


def test_the_feed_is_paginated_with_page_and_limit(team: Team) -> None:
    for index in range(7):
        team.new_task(team.ben, title=f"T{index}")

    first = team.ben.get(FEED, params={"page": 1, "limit": 3}).json()
    last = team.ben.get(FEED, params={"page": 3, "page_size": 3}).json()

    # entries: 1 project.created + 2 member.added + 7 task.created = 10
    assert first["meta"] == {"page": 1, "page_size": 3, "total": 10, "total_pages": 4}
    assert len(first["data"]) == 3 and len(last["data"]) == 3
    assert {i["id"] for i in first["data"]}.isdisjoint({i["id"] for i in last["data"]})


def test_the_feed_never_contains_other_peoples_projects_or_auth_events(team: Team) -> None:
    other = team.dan.create_project("Dan's private project")
    team.dan.post(f"{PROJECTS}/{other['id']}/tasks", {"title": "Secret"})

    items = team.ben.get(FEED, params={"limit": 100}).json()["data"]

    assert other["id"] not in {i["project_id"] for i in items}
    assert all(i["project_id"] is not None for i in items)  # auth events have no project
    assert not {"user.registered", "auth.login"} & {i["action"] for i in items}


def test_a_removed_member_loses_the_feed_immediately(team: Team) -> None:
    team.new_task(team.ben)
    assert team.cy.get(FEED).json()["meta"]["total"] > 0

    team.ana.delete(f"{PROJECTS}/{team.pid}/members/{team.cy.id}")

    assert team.cy.get(FEED).json() == {
        "data": [],
        "meta": {"page": 1, "page_size": 20, "total": 0, "total_pages": 0},
    }


@pytest.mark.parametrize("params", [{"page": 0}, {"limit": 0}, {"limit": 101}, {"page": 100001}])
def test_feed_pagination_limits_are_enforced(team: Team, params: dict[str, int]) -> None:
    assert team.ben.get(FEED, params=params).status_code == 422


# ---- a project's timeline ----


def activity_url(pid: str) -> str:
    return f"{PROJECTS}/{pid}/activity"


def test_a_member_reads_the_project_timeline(team: Team) -> None:
    task = team.new_task(team.ben, title="Plan")
    team.ben.patch(f"{TASKS}/{task['id']}", {"title": "Plan v2"})

    response = team.cy.get(activity_url(team.pid), params={"limit": 100})

    assert response.status_code == 200
    actions = [item["action"] for item in response.json()["data"]]
    assert {"project.created", "member.added", "task.created", "task.updated"} <= set(actions)
    assert {item["project_id"] for item in response.json()["data"]} == {team.pid}


def test_the_timeline_records_who_did_what(team: Team) -> None:
    task = team.new_task(team.ben, title="Plan")

    items = team.ana.get(activity_url(team.pid), params={"limit": 100}).json()["data"]

    created = next(i for i in items if i["action"] == "task.created")
    assert created["user"]["name"] == "Ben"
    assert created["task_id"] == task["id"]
    assert created["metadata"]["title"] == "Plan"


def test_a_non_member_cannot_read_a_project_timeline(team: Team) -> None:
    hidden = team.dan.get(activity_url(team.pid))
    missing = team.dan.get(activity_url(str(uuid.uuid4())))

    assert hidden.status_code == missing.status_code == 404
    assert error_of(hidden)["message"] == error_of(missing)["message"]


def test_a_removed_member_cannot_read_the_timeline(team: Team) -> None:
    team.ana.delete(f"{PROJECTS}/{team.pid}/members/{team.cy.id}")

    assert team.cy.get(activity_url(team.pid)).status_code == 404


def test_the_timeline_is_scoped_to_its_project(team: Team) -> None:
    other = team.ana.create_project("Other")
    team.ana.post(f"{PROJECTS}/{other['id']}/tasks", {"title": "Elsewhere"})

    items = team.ana.get(activity_url(team.pid), params={"limit": 100}).json()["data"]

    assert other["id"] not in {i["project_id"] for i in items}


def test_deleted_tasks_stay_in_the_timeline(team: Team) -> None:
    task = team.new_task(team.ben, title="Short lived")
    team.ana.delete(f"{TASKS}/{task['id']}")

    items = team.ana.get(activity_url(team.pid), params={"limit": 100}).json()["data"]

    assert {"task.created", "task.deleted"} <= {
        i["action"] for i in items if i["task_id"] == task["id"]
    }


def test_a_deleted_project_has_no_timeline_any_more(team: Team) -> None:
    team.ana.delete(f"{PROJECTS}/{team.pid}")

    assert team.ana.get(activity_url(team.pid)).status_code == 404
    assert team.ana.get(FEED).json()["data"] == []


def test_the_timeline_requires_authentication(app: FastAPI, team: Team) -> None:
    anonymous = TestClient(app, raise_server_exceptions=False)

    assert anonymous.get(activity_url(team.pid)).status_code == 401
