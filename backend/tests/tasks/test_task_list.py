"""Listing tasks: membership, search, filters, sorting, pagination."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from tests.tasks.helpers import TODAY, Team, error_of, ids, project_tasks, titles


def seed(team: Team) -> dict[str, dict[str, Any]]:
    """A varied set of tasks in the team project."""
    return {
        "login": team.new_task(
            team.ben,
            title="Design login page",
            priority="high",
            due_date="2026-11-10",
            assignee_id=str(team.cy.id),
            description="Wireframes for sign in",
        ),
        "docs": team.new_task(
            team.cy,
            title="Write docs",
            priority="low",
            due_date="2026-12-20",
            description="Explain the LOGIN flow",
        ),
        "api": team.new_task(
            team.ben,
            title="Build API",
            priority="medium",
            status="in_progress",
            due_date="2026-11-15",
            assignee_id=str(team.ben.id),
        ),
        "deploy": team.new_task(team.ana, title="Deploy", priority="high"),
        "polish": team.new_task(
            team.ben,
            title="UI polish",
            priority="low",
            due_date="2026-11-01",
            assignee_id=str(team.cy.id),
        ),
    }


def listing(actor: Any, team: Team, **params: Any) -> Any:
    return actor.get(project_tasks(team.pid), params=params)


# ---- membership ----------------------------------------------------------------------------------


def test_members_list_the_tasks_of_the_project(team: Team) -> None:
    seed(team)

    for member in (team.ana, team.ben, team.cy):
        response = listing(member, team)
        assert response.status_code == 200
        assert response.json()["meta"]["total"] == 5


def test_a_non_member_cannot_list_tasks(team: Team) -> None:
    seed(team)

    hidden = listing(team.dan, team)
    missing = team.dan.get(project_tasks(str(uuid.uuid4())))

    assert hidden.status_code == missing.status_code == 404
    assert error_of(hidden)["message"] == error_of(missing)["message"]


def test_a_removed_member_cannot_list_tasks_any_more(team: Team) -> None:
    seed(team)
    assert listing(team.ben, team).status_code == 200

    team.ana.delete(f"/api/v1/projects/{team.pid}/members/{team.ben.id}")

    assert listing(team.ben, team).status_code == 404


def test_only_the_projects_own_tasks_are_listed(team: Team) -> None:
    team.new_task(title="Mine")
    other = team.ana.create_project("Other")
    team.ana.post(project_tasks(other["id"]), {"title": "Elsewhere"})

    assert titles(listing(team.ana, team)) == ["Mine"]


def test_listing_requires_authentication(app: FastAPI, team: Team) -> None:
    anonymous = TestClient(app, raise_server_exceptions=False)

    assert anonymous.get(project_tasks(team.pid)).status_code == 401


def test_an_empty_project_gives_an_empty_page(team: Team) -> None:
    response = listing(team.ben, team)

    assert response.json() == {
        "data": [],
        "meta": {"page": 1, "page_size": 20, "total": 0, "total_pages": 0},
    }


# ---- search ---


def test_search_matches_title_and_description_case_insensitively(team: Team) -> None:
    seed(team)

    found = listing(team.ben, team, q="LOGIN")

    assert sorted(titles(found)) == ["Design login page", "Write docs"]
    assert found.json()["meta"]["total"] == 2


def test_search_matches_part_of_a_word(team: Team) -> None:
    seed(team)

    assert titles(listing(team.ben, team, q="ploy")) == ["Deploy"]


def test_search_treats_percent_and_underscore_literally(team: Team) -> None:
    team.new_task(title="100% done")
    team.new_task(title="100 percent")
    team.new_task(title="a_b")
    team.new_task(title="axb")

    assert titles(listing(team.ben, team, q="100%")) == ["100% done"]
    assert titles(listing(team.ben, team, q="a_b")) == ["a_b"]


def test_search_finds_nothing_in_other_projects(team: Team) -> None:
    other = team.dan.create_project("Dan's")
    team.dan.post(project_tasks(other["id"]), {"title": "Secret login plan"})
    seed(team)

    assert "Secret login plan" not in titles(listing(team.ben, team, q="login"))


# ---- filters ---


def test_filter_by_status(team: Team) -> None:
    seed(team)

    assert titles(listing(team.ben, team, status="in_progress")) == ["Build API"]
    assert listing(team.ben, team, status="completed").json()["data"] == []


def test_filter_by_several_statuses_with_a_repeated_parameter(team: Team) -> None:
    seed(team)

    response = team.ben.get(project_tasks(team.pid) + "?status=todo&status=in_progress")

    assert response.json()["meta"]["total"] == 5


def test_filter_by_priority(team: Team) -> None:
    seed(team)

    assert sorted(titles(listing(team.ben, team, priority="high"))) == [
        "Deploy",
        "Design login page",
    ]
    both = team.ben.get(project_tasks(team.pid) + "?priority=low&priority=medium")
    assert sorted(titles(both)) == ["Build API", "UI polish", "Write docs"]


def test_filter_by_assignee(team: Team) -> None:
    seed(team)

    assert sorted(titles(listing(team.ben, team, assignee_id=str(team.cy.id)))) == [
        "Design login page",
        "UI polish",
    ]
    assert titles(listing(team.ben, team, assignee_id=str(team.ben.id))) == ["Build API"]


def test_filter_for_unassigned_tasks(team: Team) -> None:
    seed(team)

    assert sorted(titles(listing(team.ben, team, assignee_id="unassigned"))) == [
        "Deploy",
        "Write docs",
    ]


@pytest.mark.parametrize("bad", ["me", "123", "unassigned!", "null"])
def test_a_malformed_assignee_filter_is_rejected(team: Team, bad: str) -> None:
    response = listing(team.ben, team, assignee_id=bad)

    assert response.status_code == 422
    assert "assignee_id" in [d["field"] for d in error_of(response)["details"]]


def test_filter_by_due_date_range_is_inclusive(team: Team) -> None:
    seed(team)

    after = listing(team.ben, team, due_after="2026-11-10")
    before = listing(team.ben, team, due_before="2026-11-10")
    window = listing(team.ben, team, due_after="2026-11-10", due_before="2026-11-15")

    assert sorted(titles(after)) == ["Build API", "Design login page", "Write docs"]
    assert sorted(titles(before)) == ["Design login page", "UI polish"]
    assert sorted(titles(window)) == ["Build API", "Design login page"]


def test_due_date_filters_exclude_tasks_without_a_due_date(team: Team) -> None:
    seed(team)

    assert "Deploy" not in titles(listing(team.ben, team, due_after="2000-01-01"))


@pytest.mark.parametrize(
    "params", [{"due_after": "soon"}, {"due_before": "2026-13-01"}, {"overdue": "maybe"}]
)
def test_invalid_date_and_boolean_filters_are_rejected(team: Team, params: dict[str, str]) -> None:
    assert listing(team.ben, team, **params).status_code == 422


def test_overdue_filter_uses_today_in_utc_and_ignores_completed_tasks(
    team: Team, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed(team)
    monkeypatch.setattr(
        "app.services.task_service.utcnow", lambda: datetime(2026, 11, 15, 8, 0, tzinfo=UTC)
    )
    assert TODAY.isoformat() == "2026-11-15"

    overdue = listing(team.ben, team, overdue="true")
    not_overdue = listing(team.ben, team, overdue="false")

    # Due 11-10 and 11-01 are before today. Due 11-15 is today (not overdue).
    assert sorted(titles(overdue)) == ["Design login page", "UI polish"]
    assert sorted(titles(not_overdue)) == ["Build API", "Deploy", "Write docs"]


def test_a_completed_task_is_never_overdue(team: Team, monkeypatch: pytest.MonkeyPatch) -> None:
    task = team.new_task(
        title="Old but done",
        description="d",
        priority="low",
        due_date="2026-01-01",
        assignee_id=str(team.cy.id),
    )
    team.ben.patch(f"/api/v1/tasks/{task['id']}/status", {"status": "in_progress"})
    team.ben.patch(f"/api/v1/tasks/{task['id']}/status", {"status": "completed"})
    monkeypatch.setattr(
        "app.services.task_service.utcnow", lambda: datetime(2026, 11, 15, tzinfo=UTC)
    )

    assert listing(team.ben, team, overdue="true").json()["data"] == []


def test_filters_combine_with_and(team: Team) -> None:
    seed(team)

    response = listing(
        team.ben, team, q="login", priority="high", assignee_id=str(team.cy.id), status="todo"
    )

    assert titles(response) == ["Design login page"]


# ---- sorting ---


def test_the_default_order_is_newest_first(team: Team, db_session: Session) -> None:
    tasks = seed(team)
    for index, key in enumerate(["login", "docs", "api", "deploy", "polish"]):
        db_session.execute(
            text("update tasks set created_at = :t where id = :id"),
            {"t": datetime(2026, 1, index + 1, tzinfo=UTC), "id": tasks[key]["id"]},
        )

    assert titles(listing(team.ben, team)) == [
        "UI polish",
        "Deploy",
        "Build API",
        "Write docs",
        "Design login page",
    ]


def test_sort_by_created_at_ascending_and_descending(team: Team, db_session: Session) -> None:
    tasks = seed(team)
    for index, key in enumerate(["login", "docs", "api", "deploy", "polish"]):
        db_session.execute(
            text("update tasks set created_at = :t where id = :id"),
            {"t": datetime(2026, 1, index + 1, tzinfo=UTC), "id": tasks[key]["id"]},
        )

    ascending = titles(listing(team.ben, team, sort="created_at"))
    descending = titles(listing(team.ben, team, sort="-created_at"))

    assert ascending[0] == "Design login page" and ascending[-1] == "UI polish"
    assert descending == list(reversed(ascending))


def test_sort_by_due_date_puts_tasks_without_one_last_in_both_directions(team: Team) -> None:
    seed(team)

    ascending = titles(listing(team.ben, team, sort="due_date"))
    descending = titles(listing(team.ben, team, sort="-due_date"))

    assert ascending == ["UI polish", "Design login page", "Build API", "Write docs", "Deploy"]
    assert descending == ["Write docs", "Build API", "Design login page", "UI polish", "Deploy"]


def test_sort_by_priority_uses_low_medium_high_not_the_alphabet(team: Team) -> None:
    seed(team)

    ascending = [t["priority"] for t in listing(team.ben, team, sort="priority").json()["data"]]
    descending = [t["priority"] for t in listing(team.ben, team, sort="-priority").json()["data"]]

    assert ascending == ["low", "low", "medium", "high", "high"]
    assert descending == ["high", "high", "medium", "low", "low"]


def test_sort_by_position_orders_a_board_column(team: Team) -> None:
    first = team.new_task(title="first")
    second = team.new_task(title="second")
    third = team.new_task(title="third")
    team.ben.patch(f"/api/v1/tasks/{third['id']}/status", {"status": "todo", "position": 10.5})

    response = listing(team.ben, team, sort="position")

    assert titles(response) == ["third", "first", "second"]
    assert {first["id"], second["id"]} <= set(ids(response))


@pytest.mark.parametrize(
    "sort", ["title", "-title", "random", "created_at;drop table tasks", "", "id"]
)
def test_only_allow_listed_sort_orders_are_accepted(team: Team, sort: str) -> None:
    response = listing(team.ben, team, sort=sort)

    assert response.status_code == 422
    assert error_of(response)["code"] == "VALIDATION_ERROR"


def test_equal_sort_keys_still_paginate_without_duplicates_or_gaps(team: Team) -> None:
    created = {team.new_task(title=f"T{i}")["id"] for i in range(7)}  # identical timestamps

    seen: list[str] = []
    for page in (1, 2, 3, 4):
        seen += ids(listing(team.ben, team, sort="due_date", page=page, page_size=2))

    assert len(seen) == len(set(seen)) == 7
    assert set(seen) == created


# ---- pagination ---


def test_pagination_metadata_is_complete_and_correct(team: Team) -> None:
    for index in range(5):
        team.new_task(title=f"T{index}")

    first = listing(team.ben, team, page=1, page_size=2).json()
    last = listing(team.ben, team, page=3, page_size=2).json()
    beyond = listing(team.ben, team, page=9, page_size=2).json()

    assert first["meta"] == {"page": 1, "page_size": 2, "total": 5, "total_pages": 3}
    assert len(first["data"]) == 2 and len(last["data"]) == 1
    assert beyond["data"] == [] and beyond["meta"]["total"] == 5


def test_limit_is_an_alias_of_page_size(team: Team) -> None:
    for index in range(4):
        team.new_task(title=f"T{index}")

    by_limit = listing(team.ben, team, page=2, limit=3).json()

    assert by_limit["meta"] == {"page": 2, "page_size": 3, "total": 4, "total_pages": 2}
    assert len(by_limit["data"]) == 1
    same = listing(team.ben, team, page_size=3, limit=3)
    assert same.status_code == 200
    clash = listing(team.ben, team, page_size=3, limit=4)
    assert clash.status_code == 422


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": -1},
        {"limit": 0},
        {"limit": 101},
        {"page_size": 101},
        {"page": "x"},
        {"limit": "many"},
    ],
)
def test_pagination_limits_are_enforced(team: Team, params: dict[str, Any]) -> None:
    assert listing(team.ben, team, **params).status_code == 422


def test_the_page_size_is_capped_at_100(team: Team) -> None:
    assert listing(team.ben, team, limit=100).json()["meta"]["page_size"] == 100
    assert listing(team.ben, team).json()["meta"]["page_size"] == 20


# ---- efficiency ---


def test_listing_uses_the_same_number_of_queries_however_many_tasks_exist(
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
            assert listing(team.ben, team, limit=100).status_code == 200
        finally:
            event.remove(connection, "before_cursor_execute", count)
        return len(statements)

    for index in range(3):
        team.new_task(title=f"T{index}", assignee_id=str(team.cy.id))
    few = queries_for_list()
    for index in range(3, 25):
        team.new_task(title=f"T{index}", assignee_id=str(team.cy.id))
    many = queries_for_list()

    assert few == many  # creators and assignees come from joins: no N+1
    assert many <= 8
