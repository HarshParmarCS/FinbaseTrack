"""Updating a task (never its status) and the creator-or-assignee rule."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.repositories.activity_repository import ActivityRepository
from tests.tasks.helpers import TASKS, Team, error_of, task_activity, task_row


def url(task: dict[str, Any]) -> str:
    return f"{TASKS}/{task['id']}"


# ---- who may update ----------------------------------------------------------------------------


def test_the_creator_can_update_their_task(team: Team) -> None:
    task = team.new_task(team.ben, title="Old")

    response = team.ben.patch(url(task), {"title": "New"})

    assert response.status_code == 200
    assert response.json()["data"]["title"] == "New"


def test_the_assignee_can_update_a_task_they_did_not_create(team: Team) -> None:
    task = team.new_task(team.ben, assignee_id=str(team.cy.id))

    response = team.cy.patch(url(task), {"description": "Assignee's note"})

    assert response.status_code == 200
    assert response.json()["data"]["description"] == "Assignee's note"


def test_a_member_who_is_neither_creator_nor_assignee_cannot_update(team: Team) -> None:
    task = team.new_task(team.ben, assignee_id=str(team.cy.id))
    bystander = team.ana

    response = bystander.patch(url(task), {"title": "Hijacked"})

    assert response.status_code == 403
    body = error_of(response)
    assert body["code"] == "FORBIDDEN"
    assert body["details"][0]["policy_id"] == "task-update"
    assert body["message"] == "Only the task creator or the task assignee can update a task."


def test_the_project_owner_has_no_update_right_just_for_being_the_owner(
    team: Team, db_session: Session
) -> None:
    task = team.new_task(team.ben, title="Ben's")

    response = team.ana.patch(url(task), {"title": "Owner edit"})

    assert response.status_code == 403
    row = task_row(db_session, task["id"])
    assert row is not None and row.title == "Ben's"


def test_a_member_who_just_got_assigned_gains_update_rights(team: Team) -> None:
    task = team.new_task(team.ben)
    assert team.cy.patch(url(task), {"title": "X"}).status_code == 403

    team.ben.patch(url(task), {"assignee_id": str(team.cy.id)})

    assert team.cy.patch(url(task), {"title": "X"}).status_code == 200


def test_a_user_who_is_no_longer_the_assignee_loses_update_rights(team: Team) -> None:
    task = team.new_task(team.ben, assignee_id=str(team.cy.id))
    team.ben.patch(url(task), {"assignee_id": None})

    assert team.cy.patch(url(task), {"title": "X"}).status_code == 403


def test_a_non_member_gets_404_not_403(team: Team) -> None:
    task = team.new_task()

    assert team.dan.patch(url(task), {"title": "X"}).status_code == 404


def test_updating_requires_authentication_and_csrf(app: FastAPI, team: Team) -> None:
    task = team.new_task()
    anonymous = TestClient(app, raise_server_exceptions=False)

    assert anonymous.patch(url(task), json={"title": "X"}).status_code == 401
    assert team.ben.client.patch(url(task), json={"title": "X"}).status_code == 403


# ---- partial semantics --------------------------------------------------------------------------


def test_only_the_fields_sent_are_changed(team: Team) -> None:
    task = team.new_task(
        title="Keep",
        description="Keep too",
        priority="high",
        due_date="2026-12-01",
        assignee_id=str(team.cy.id),
    )

    data = team.ben.patch(url(task), {"priority": "low"}).json()["data"]

    assert data["priority"] == "low"
    assert (data["title"], data["description"], data["due_date"]) == (
        "Keep",
        "Keep too",
        "2026-12-01",
    )
    assert data["assignee"]["id"] == str(team.cy.id)
    assert data["status"] == "todo"


def test_all_updatable_fields_can_change_together(team: Team) -> None:
    task = team.new_task()

    data = team.ben.patch(
        url(task),
        {
            "title": "Renamed",
            "description": "Described",
            "priority": "high",
            "due_date": "2027-01-31",
            "assignee_id": str(team.cy.id),
        },
    ).json()["data"]

    assert data["title"] == "Renamed"
    assert data["description"] == "Described"
    assert data["priority"] == "high"
    assert data["due_date"] == "2027-01-31"
    assert data["assignee"]["name"] == "Cy"


def test_null_clears_description_due_date_and_assignee(team: Team) -> None:
    task = team.new_task(description="x", due_date="2026-12-01", assignee_id=str(team.cy.id))

    data = team.ben.patch(
        url(task), {"description": None, "due_date": None, "assignee_id": None}
    ).json()["data"]

    assert (data["description"], data["due_date"], data["assignee"]) == (None, None, None)


def test_updating_moves_updated_at_forward(team: Team, db_session: Session) -> None:
    task = team.new_task()
    db_session.execute(
        text("update tasks set updated_at = now() - interval '1 day' where id = :id"),
        {"id": task["id"]},
    )
    before = task_row(db_session, task["id"])
    assert before is not None
    before_time = before.updated_at

    team.ben.patch(url(task), {"title": "Changed"})

    after = task_row(db_session, task["id"])
    assert after is not None and after.updated_at > before_time


# ---- fields that must not be changed ---


@pytest.mark.parametrize(
    "field",
    [
        "status",
        "position",
        "creator_id",
        "project_id",
        "id",
        "completed_at",
        "created_at",
        "updated_at",
    ],
)
def test_protected_fields_cannot_be_changed_through_the_generic_update(
    team: Team, db_session: Session, field: str
) -> None:
    task = team.new_task()
    value: Any = (
        "completed" if field == "status" else (5.0 if field == "position" else str(team.cy.id))
    )

    response = team.ben.patch(url(task), {field: value})

    assert response.status_code == 422
    assert field in [d["field"] for d in error_of(response)["details"]]
    row = task_row(db_session, task["id"])
    assert row is not None
    assert (
        row.creator_id == team.ben.id and row.status == "todo" and row.position == task["position"]
    )


def test_the_generic_update_cannot_complete_a_task(team: Team, db_session: Session) -> None:
    task = team.complete_task(team.ben)

    response = team.ben.patch(url(task), {"status": "completed"})

    assert response.status_code == 422
    row = task_row(db_session, task["id"])
    assert row is not None and row.status == "todo" and row.completed_at is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": None},
        {"title": ""},
        {"title": "x" * 201},
        {"priority": None},
        {"priority": "urgent"},
        {"description": "d" * 5001},
        {"due_date": "next week"},
        {"assignee_id": "not-a-uuid"},
    ],
)
def test_invalid_updates_are_rejected(team: Team, payload: dict[str, Any]) -> None:
    task = team.new_task()

    assert team.ben.patch(url(task), payload).status_code == 422


# ---- assignee rules ---


def test_the_assignee_must_be_a_current_project_member(team: Team, db_session: Session) -> None:
    task = team.new_task()

    response = team.ben.patch(url(task), {"assignee_id": str(team.dan.id)})

    assert response.status_code == 422
    assert error_of(response)["code"] == "BUSINESS_RULE_VIOLATION"
    row = task_row(db_session, task["id"])
    assert row is not None and row.assignee_id is None


def test_a_removed_member_cannot_be_assigned(team: Team) -> None:
    task = team.new_task()
    team.ana.delete(f"/api/v1/projects/{team.pid}/members/{team.cy.id}")

    assert team.ben.patch(url(task), {"assignee_id": str(team.cy.id)}).status_code == 422


def test_authorization_is_checked_before_assignee_validation(team: Team) -> None:
    """A user who may not update must get 403/404, never information about other users."""
    task = team.new_task(team.ben)

    assert team.ana.patch(url(task), {"assignee_id": str(team.dan.id)}).status_code == 403
    assert team.dan.patch(url(task), {"assignee_id": str(team.dan.id)}).status_code == 404


def test_removing_a_member_unassigns_their_tasks_and_blocks_them(team: Team) -> None:
    task = team.new_task(team.ben, assignee_id=str(team.cy.id))

    team.ana.delete(f"/api/v1/projects/{team.pid}/members/{team.cy.id}")

    assert team.ben.get(url(task)).json()["data"]["assignee"] is None
    assert team.cy.get(url(task)).status_code == 404
    assert team.cy.patch(url(task), {"title": "X"}).status_code == 404


# ---- completed tasks must stay complete ---


def complete(team: Team, task: dict[str, Any]) -> None:
    assert team.ben.patch(f"{url(task)}/status", {"status": "in_progress"}).status_code == 200
    assert team.ben.patch(f"{url(task)}/status", {"status": "completed"}).status_code == 200


def test_a_completed_task_can_still_be_edited_when_it_stays_complete(team: Team) -> None:
    task = team.complete_task(team.ben)
    complete(team, task)

    response = team.ben.patch(url(task), {"title": "Renamed after completion"})

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "completed"


@pytest.mark.parametrize(
    "clearing", [{"due_date": None}, {"description": None}, {"assignee_id": None}]
)
def test_an_edit_that_would_make_a_completed_task_incomplete_is_denied(
    team: Team, db_session: Session, clearing: dict[str, Any]
) -> None:
    task = team.complete_task(team.ben)
    complete(team, task)

    response = team.ben.patch(url(task), clearing)

    assert response.status_code == 403
    assert error_of(response)["details"][0]["policy_id"] == "task-complete"
    row = task_row(db_session, task["id"])
    assert row is not None
    assert row.due_date is not None and row.description is not None and row.assignee_id is not None


# ---- activity and atomicity ---


def test_updates_are_recorded_with_old_and_new_values(team: Team, db_session: Session) -> None:
    task = team.new_task(team.ben, title="Before", priority="low")

    team.ben.patch(url(task), {"title": "After", "priority": "high"})

    entry = task_activity(db_session, task["id"], "task.updated")[0]
    assert entry.user_id == team.ben.id
    assert entry.meta == {"changes": {"title": ["Before", "After"], "priority": ["low", "high"]}}


def test_assigning_and_unassigning_are_recorded(team: Team, db_session: Session) -> None:
    task = team.new_task(team.ben)

    team.ben.patch(url(task), {"assignee_id": str(team.cy.id)})
    team.ben.patch(url(task), {"assignee_id": None})

    assigned = task_activity(db_session, task["id"], "task.assigned")
    unassigned = task_activity(db_session, task["id"], "task.unassigned")
    assert [e.meta for e in assigned] == [
        {"assignee_id": str(team.cy.id), "previous_assignee_id": None}
    ]
    assert [e.meta for e in unassigned] == [{"previous_assignee_id": str(team.cy.id)}]
    assert task_activity(db_session, task["id"], "task.updated") == []  # only the assignee changed


def test_an_update_that_changes_nothing_records_nothing(team: Team, db_session: Session) -> None:
    task = team.new_task(title="Same")

    response = team.ben.patch(url(task), {"title": "Same"})

    assert response.status_code == 200
    assert task_activity(db_session, task["id"], "task.updated") == []


def test_updating_is_all_or_nothing(
    team: Team, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = team.new_task(title="Original")
    db_session.commit()

    def explode(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("activity failed")

    monkeypatch.setattr(ActivityRepository, "record", explode)

    response = team.ben.patch(url(task), {"title": "Half done"})

    assert response.status_code == 500
    row = task_row(db_session, task["id"])
    assert row is not None and row.title == "Original"


def test_updating_a_deleted_task_is_404(team: Team) -> None:
    task = team.new_task(team.ana)
    team.ana.delete(url(task))

    assert team.ana.patch(url(task), {"title": "X"}).status_code == 404
    assert team.ana.patch(f"{TASKS}/{uuid.uuid4()}", {"title": "X"}).status_code == 404


def test_activity_timestamps_exist_for_each_entry(team: Team, db_session: Session) -> None:
    task = team.new_task()
    team.ben.patch(url(task), {"title": "Next"})

    entries = task_activity(db_session, task["id"])

    assert {e.action for e in entries} == {"task.created", "task.updated"}  # same transaction time
    assert all(e.created_at <= datetime.now(UTC) for e in entries)


def test_the_service_itself_rejects_a_non_member_assignee_before_the_database_does(
    team: Team, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defense in depth: with the database-error translation switched off, the 422 still comes
    from the service's own check, not from the composite foreign key."""
    from app.services.task_service import _IntegrityTranslator

    monkeypatch.setattr(_IntegrityTranslator, "__exit__", lambda self, *args: False)
    task = team.new_task(team.ben)

    on_update = team.ben.patch(url(task), {"assignee_id": str(team.dan.id)})
    on_create = team.ben.post(
        f"/api/v1/projects/{team.pid}/tasks", {"title": "X", "assignee_id": str(team.dan.id)}
    )

    assert on_update.status_code == on_create.status_code == 422
