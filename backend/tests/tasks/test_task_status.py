"""Status changes: transitions, the completion policy, positions."""

import itertools
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.authorization.service import AuthorizationService
from app.repositories.activity_repository import ActivityRepository
from tests.tasks.helpers import TASKS, Team, error_of, task_activity, task_row


def status_url(task: dict[str, Any]) -> str:
    return f"{TASKS}/{task['id']}/status"


def move(actor: Any, task: dict[str, Any], status: str, **extra: Any) -> Any:
    return actor.patch(status_url(task), {"status": status, **extra})


# ---- valid moves ---


def test_a_task_moves_from_todo_to_in_progress(team: Team) -> None:
    task = team.new_task(team.ben)

    response = move(team.ben, task, "in_progress")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "in_progress"
    assert data["completed_at"] is None


def test_the_full_lifecycle_todo_to_completed_and_back(team: Team) -> None:
    task = team.complete_task(team.ben)

    in_progress = move(team.ben, task, "in_progress").json()["data"]
    completed = move(team.ben, task, "completed").json()["data"]
    reopened = move(team.ben, task, "in_progress").json()["data"]
    back = move(team.ben, task, "todo").json()["data"]

    assert in_progress["status"] == "in_progress" and in_progress["completed_at"] is None
    assert completed["status"] == "completed" and completed["completed_at"] is not None
    assert reopened["status"] == "in_progress" and reopened["completed_at"] is None
    assert back["status"] == "todo"


def test_the_assignee_may_change_the_status_too(team: Team) -> None:
    task = team.complete_task(team.ben, assignee=team.cy)

    assert move(team.cy, task, "in_progress").status_code == 200
    assert move(team.cy, task, "completed").status_code == 200


def test_a_moved_task_goes_to_the_end_of_the_new_column(team: Team) -> None:
    first = team.new_task(title="a", status="in_progress")
    task = team.new_task(title="b")

    data = move(team.ben, task, "in_progress").json()["data"]

    assert first["position"] == 1024.0
    assert data["position"] == 2048.0


def test_an_explicit_position_is_used_for_board_moves(team: Team) -> None:
    task = team.new_task()

    data = move(team.ben, task, "in_progress", position=512.5).json()["data"]

    assert data["position"] == 512.5


def test_a_task_can_be_reordered_inside_its_column(team: Team) -> None:
    task = team.new_task()

    response = move(team.ben, task, "todo", position=7.0)

    assert response.status_code == 200
    assert response.json()["data"]["position"] == 7.0
    assert response.json()["data"]["status"] == "todo"


@pytest.mark.parametrize(
    "raw_position", ["1e13", "-1e13", "NaN", "Infinity", "-Infinity", '"abc"', "[1]", "true"]
)
def test_invalid_positions_are_rejected(team: Team, raw_position: str) -> None:
    task = team.new_task()
    body = '{"status": "in_progress", "position": ' + raw_position + "}"

    response = team.ben.client.request(
        "PATCH",
        status_url(task),
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": team.ben.client.cookies.get("csrf_token") or "",
        },
    )

    assert response.status_code == 422


# ---- the transition table ---

VALID = {
    ("todo", "in_progress"),
    ("in_progress", "todo"),
    ("in_progress", "completed"),
    ("completed", "in_progress"),
}
INVALID = {("todo", "completed"), ("completed", "todo")}


@pytest.mark.parametrize(("source", "target"), sorted(VALID))
def test_valid_transitions_are_accepted(team: Team, source: str, target: str) -> None:
    task = team.complete_task(team.ben)
    path = {"todo": [], "in_progress": ["in_progress"], "completed": ["in_progress", "completed"]}[
        source
    ]
    for step in path:
        assert move(team.ben, task, step).status_code == 200

    response = move(team.ben, task, target)

    assert response.status_code == 200
    assert response.json()["data"]["status"] == target


@pytest.mark.parametrize(("source", "target"), sorted(INVALID))
def test_invalid_transitions_are_rejected(
    team: Team, db_session: Session, source: str, target: str
) -> None:
    task = team.complete_task(team.ben)
    for step in {"todo": [], "completed": ["in_progress", "completed"]}[source]:
        move(team.ben, task, step)

    response = move(team.ben, task, target)

    assert response.status_code == 422
    body = error_of(response)
    assert body["code"] == "BUSINESS_RULE_VIOLATION"
    assert f"from {source} to {target}" in body["message"]
    row = task_row(db_session, task["id"])
    assert row is not None and row.status == source


@pytest.mark.parametrize("status", ["todo", "in_progress"])
def test_moving_to_the_current_status_without_a_position_is_rejected(
    team: Team, status: str
) -> None:
    task = team.new_task(status=status)

    response = move(team.ben, task, status)

    assert response.status_code == 422
    assert f"already {status}" in error_of(response)["message"]


def test_every_pair_of_statuses_is_covered_by_the_table() -> None:
    all_pairs = set(itertools.permutations(["todo", "in_progress", "completed"], 2))

    assert all_pairs == VALID | INVALID


def test_an_invalid_transition_is_reported_before_the_completion_policy(team: Team) -> None:
    task = team.new_task(team.ben)  # incomplete AND todo: both rules would reject the move

    response = move(team.ben, task, "completed")

    assert response.status_code == 422  # the workflow error, not 403


# ---- the completion policy ---


def to_in_progress(team: Team, **fields: Any) -> dict[str, Any]:
    task = team.new_task(team.ben, **fields)
    assert move(team.ben, task, "in_progress").status_code == 200
    return task


def test_completing_invokes_task_update_and_task_complete(
    team: Team, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = to_in_progress(
        team, description="d", priority="low", due_date="2026-12-01", assignee_id=str(team.cy.id)
    )
    asked: list[str] = []
    original = AuthorizationService._enforce

    def spy(self: AuthorizationService, ctx: Any) -> Any:
        asked.append(str(ctx.action))  # enforced decisions only, not the dry-run allowed_actions
        return original(self, ctx)

    monkeypatch.setattr(AuthorizationService, "_enforce", spy)

    assert move(team.ben, task, "completed").status_code == 200

    assert asked == ["task.update", "task.complete"]


def test_other_status_moves_do_not_invoke_the_completion_policy(
    team: Team, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = team.new_task(team.ben)
    asked: list[str] = []
    original = AuthorizationService._enforce

    def spy(self: AuthorizationService, ctx: Any) -> Any:
        asked.append(str(ctx.action))  # enforced decisions only, not the dry-run allowed_actions
        return original(self, ctx)

    monkeypatch.setattr(AuthorizationService, "_enforce", spy)

    move(team.ben, task, "in_progress")

    assert asked == ["task.update"]


def test_a_task_without_an_assignee_cannot_be_completed(team: Team, db_session: Session) -> None:
    task = to_in_progress(team, description="d", priority="low", due_date="2026-12-01")

    response = move(team.ben, task, "completed")

    assert response.status_code == 403
    body = error_of(response)
    assert body["code"] == "FORBIDDEN"
    assert body["details"][0]["policy_id"] == "task-complete"
    row = task_row(db_session, task["id"])
    assert row is not None and row.status == "in_progress" and row.completed_at is None


@pytest.mark.parametrize(
    "missing",
    ["description", "due_date"],
)
def test_a_task_missing_required_information_cannot_be_completed(team: Team, missing: str) -> None:
    fields: dict[str, Any] = {
        "description": "d",
        "priority": "low",
        "due_date": "2026-12-01",
        "assignee_id": str(team.cy.id),
    }
    del fields[missing]
    task = to_in_progress(team, **fields)

    response = move(team.ben, task, "completed")

    assert response.status_code == 403
    assert error_of(response)["details"][0]["policy_id"] == "task-complete"


def test_a_whitespace_only_description_does_not_count(team: Team) -> None:
    task = to_in_progress(
        team, description="   ", priority="low", due_date="2026-12-01", assignee_id=str(team.cy.id)
    )

    assert move(team.ben, task, "completed").status_code == 403


def test_completing_works_once_the_missing_information_is_filled_in(team: Team) -> None:
    task = to_in_progress(team, priority="low")
    assert move(team.ben, task, "completed").status_code == 403

    team.ben.patch(
        f"{TASKS}/{task['id']}",
        {"description": "Now written", "due_date": "2026-12-31", "assignee_id": str(team.cy.id)},
    )

    assert move(team.ben, task, "completed").status_code == 200


# ---- who may change the status ---


def test_a_member_who_is_neither_creator_nor_assignee_cannot_change_status(
    team: Team, db_session: Session
) -> None:
    task = team.new_task(team.ben, assignee_id=str(team.cy.id))

    response = move(team.ana, task, "in_progress")  # the owner has no update right

    assert response.status_code == 403
    assert error_of(response)["details"][0]["policy_id"] == "task-update"
    row = task_row(db_session, task["id"])
    assert row is not None and row.status == "todo"


def test_a_non_member_cannot_change_the_status(team: Team) -> None:
    task = team.new_task()

    assert move(team.dan, task, "in_progress").status_code == 404


def test_a_removed_member_cannot_change_the_status(team: Team) -> None:
    task = team.new_task(team.ben)
    team.ana.delete(f"/api/v1/projects/{team.pid}/members/{team.ben.id}")

    assert move(team.ben, task, "in_progress").status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"status": "blocked"},
        {"status": None},
        {"status": "todo", "title": "x"},
        {"position": 1.0},
    ],
)
def test_invalid_status_requests_are_rejected(team: Team, payload: dict[str, Any]) -> None:
    task = team.new_task()

    assert team.ben.patch(status_url(task), payload).status_code == 422


def test_status_changes_require_authentication_and_csrf(app: FastAPI, team: Team) -> None:
    task = team.new_task()
    anonymous = TestClient(app, raise_server_exceptions=False)

    assert anonymous.patch(status_url(task), json={"status": "in_progress"}).status_code == 401
    assert (
        team.ben.client.patch(status_url(task), json={"status": "in_progress"}).status_code == 403
    )


# ---- activity and atomicity ---


def test_status_changes_are_recorded(team: Team, db_session: Session) -> None:
    task = team.new_task(team.ben)

    move(team.ben, task, "in_progress")

    entry = task_activity(db_session, task["id"], "task.status_changed")[0]
    assert entry.user_id == team.ben.id
    assert entry.meta == {"from": "todo", "to": "in_progress", "position": 1024.0}


def test_a_status_change_is_all_or_nothing(
    team: Team, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = team.new_task(team.ben)
    db_session.commit()

    def explode(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("activity failed")

    monkeypatch.setattr(ActivityRepository, "record", explode)

    response = move(team.ben, task, "in_progress")

    assert response.status_code == 500
    row = task_row(db_session, task["id"])
    assert row is not None and row.status == "todo"
