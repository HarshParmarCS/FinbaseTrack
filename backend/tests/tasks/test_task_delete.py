"""Deleting tasks: project owner only, and only while the task is todo."""

import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.repositories.task_repository import TaskRepository
from tests.projects.helpers import PROJECTS, project_row
from tests.tasks.helpers import TASKS, Team, error_of, task_activity, task_row


def url(task: dict[str, Any]) -> str:
    return f"{TASKS}/{task['id']}"


def to_status(team: Team, task: dict[str, Any], *steps: str) -> None:
    for step in steps:
        assert team.ben.patch(f"{url(task)}/status", {"status": step}).status_code == 200


def test_the_project_owner_deletes_a_todo_task(team: Team, db_session: Session) -> None:
    task = team.new_task(team.ben)

    response = team.ana.delete(url(task))

    assert response.status_code == 204
    assert response.content == b""
    assert task_row(db_session, task["id"]) is None
    assert team.ana.get(url(task)).status_code == 404


def test_deleting_a_task_leaves_the_project_and_other_tasks_alone(team: Team) -> None:
    doomed = team.new_task(team.ben, title="Doomed")
    kept = team.new_task(team.ben, title="Kept")

    team.ana.delete(url(doomed))

    assert team.ana.get(url(kept)).status_code == 200
    assert team.ana.get(f"{PROJECTS}/{team.pid}").json()["data"]["task_counts"]["todo"] == 1


def test_the_project_owner_cannot_delete_an_in_progress_task(
    team: Team, db_session: Session
) -> None:
    task = team.new_task(team.ben)
    to_status(team, task, "in_progress")

    response = team.ana.delete(url(task))

    assert response.status_code == 403
    body = error_of(response)
    assert body["code"] == "FORBIDDEN"
    assert body["details"][0]["policy_id"] == "task-delete"
    assert "todo" in body["message"]
    assert task_row(db_session, task["id"]) is not None


def test_the_project_owner_cannot_delete_a_completed_task(team: Team, db_session: Session) -> None:
    task = team.complete_task(team.ben)
    to_status(team, task, "in_progress", "completed")

    assert team.ana.delete(url(task)).status_code == 403
    assert task_row(db_session, task["id"]) is not None


def test_a_reopened_task_is_deletable_again_only_when_back_in_todo(team: Team) -> None:
    task = team.new_task(team.ben)
    to_status(team, task, "in_progress")
    assert team.ana.delete(url(task)).status_code == 403

    to_status(team, task, "todo")

    assert team.ana.delete(url(task)).status_code == 204


def test_the_creator_cannot_delete_even_their_own_todo_task(
    team: Team, db_session: Session
) -> None:
    task = team.new_task(team.ben)

    response = team.ben.delete(url(task))

    assert response.status_code == 403
    assert error_of(response)["details"][0]["policy_id"] == "task-delete"
    assert task_row(db_session, task["id"]) is not None


def test_the_assignee_cannot_delete_a_todo_task(team: Team) -> None:
    task = team.new_task(team.ben, assignee_id=str(team.cy.id))

    assert team.cy.delete(url(task)).status_code == 403


def test_a_non_member_gets_404_and_the_task_survives(team: Team, db_session: Session) -> None:
    task = team.new_task()

    assert team.dan.delete(url(task)).status_code == 404
    assert task_row(db_session, task["id"]) is not None


def test_deleting_twice_or_a_missing_task_is_404(team: Team) -> None:
    task = team.new_task()
    assert team.ana.delete(url(task)).status_code == 204

    assert team.ana.delete(url(task)).status_code == 404
    assert team.ana.delete(f"{TASKS}/{uuid.uuid4()}").status_code == 404


def test_deleting_requires_authentication_and_csrf(app: FastAPI, team: Team) -> None:
    task = team.new_task()
    anonymous = TestClient(app, raise_server_exceptions=False)

    assert anonymous.delete(url(task)).status_code == 401
    assert team.ana.client.delete(url(task)).status_code == 403


def test_a_deleted_task_leaves_audit_history(team: Team, db_session: Session) -> None:
    task = team.new_task(team.ben, title="History")

    team.ana.delete(url(task))

    actions = {e.action for e in task_activity(db_session, task["id"])}
    assert actions == {"task.created", "task.deleted"}
    deleted = task_activity(db_session, task["id"], "task.deleted")[0]
    assert deleted.user_id == team.ana.id
    assert deleted.project_id == uuid.UUID(team.pid)
    assert deleted.meta == {"title": "History", "status": "todo"}


def test_deleting_is_all_or_nothing(
    team: Team, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = team.new_task(team.ben)
    db_session.commit()

    def explode(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("delete failed")

    monkeypatch.setattr(TaskRepository, "delete", explode)

    response = team.ana.delete(url(task))

    assert response.status_code == 500
    assert task_row(db_session, task["id"]) is not None
    assert [e.action for e in task_activity(db_session, task["id"])] == ["task.created"]


def test_deleting_the_project_removes_its_tasks(team: Team, db_session: Session) -> None:
    task = team.new_task(team.ben, assignee_id=str(team.cy.id))
    assert project_row(db_session, team.pid) is not None

    assert team.ana.delete(f"{PROJECTS}/{team.pid}").status_code == 204

    assert task_row(db_session, task["id"]) is None
    assert team.ben.get(url(task)).status_code == 404
