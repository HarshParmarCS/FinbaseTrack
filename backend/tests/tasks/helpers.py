"""Helpers for task API tests."""

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

import pytest
from httpx2 import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActivityLog, Task
from tests.projects.helpers import PROJECTS, Actor

TASKS = "/api/v1/tasks"


def project_tasks(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/tasks"


@dataclass
class Team:
    """ana owns the project; ben and cy are members; dan is NOT a member."""

    project: dict[str, Any]
    ana: Actor
    ben: Actor
    cy: Actor
    dan: Actor

    @property
    def pid(self) -> str:
        return str(self.project["id"])

    def new_task(self, actor: Actor | None = None, **fields: Any) -> dict[str, Any]:
        """Create a task through the API (as ben by default) and return its JSON."""
        creator = actor or self.ben
        fields.setdefault("title", "Design login page")
        response = creator.post(project_tasks(self.pid), fields)
        assert response.status_code == 201, response.text
        data: dict[str, Any] = response.json()["data"]
        return data

    def complete_task(
        self, actor: Actor | None = None, assignee: Actor | None = None
    ) -> dict[str, Any]:
        """A task with everything the completion policy needs, still in `todo`."""
        return self.new_task(
            actor,
            description="Wireframes and copy",
            priority="high",
            due_date="2026-12-01",
            assignee_id=str((assignee or self.cy).id),
        )


@pytest.fixture
def team(ana: Actor, ben: Actor, cy: Actor, dan: Actor) -> Team:
    project = ana.create_project("Team project")
    assert ana.add_member(project["id"], ben).status_code == 201
    assert ana.add_member(project["id"], cy).status_code == 201
    return Team(project=project, ana=ana, ben=ben, cy=cy, dan=dan)


def error_of(response: Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return body


def task_row(db: Session, task_id: str) -> Task | None:
    db.expire_all()
    return db.get(Task, uuid.UUID(task_id))


def task_activity(db: Session, task_id: str, action: str | None = None) -> list[ActivityLog]:
    db.expire_all()
    statement = select(ActivityLog).where(ActivityLog.task_id == uuid.UUID(task_id))
    if action:
        statement = statement.where(ActivityLog.action == action)
    return list(db.scalars(statement.order_by(ActivityLog.created_at, ActivityLog.id)))


def ids(response: Response) -> list[str]:
    return [item["id"] for item in response.json()["data"]]


def titles(response: Response) -> list[str]:
    return [item["title"] for item in response.json()["data"]]


TODAY = date(2026, 11, 15)
