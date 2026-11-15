"""Helpers for project and membership API tests."""

import uuid
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActivityLog, Project, ProjectMember, User
from tests.auth.helpers import csrf_headers, register

PASSWORD = "correct-horse-battery"
PROJECTS = "/api/v1/projects"


class Actor:
    """A registered user with their own logged-in client (their own cookie jar)."""

    def __init__(self, app: FastAPI, db: Session, name: str) -> None:
        self.name = name
        self.email = f"{name.lower()}@example.com"
        self.client = TestClient(app, raise_server_exceptions=False)
        response = register(self.client, email=self.email, name=name, password=PASSWORD)
        assert response.status_code == 201, response.text
        self.id = uuid.UUID(response.json()["data"]["id"])
        self.db = db

    @property
    def user(self) -> User:
        found = self.db.get(User, self.id)
        assert found is not None
        return found

    # -- HTTP helpers that add the CSRF header, like the real frontend does -------------------

    def get(self, url: str, **kwargs: Any) -> Response:
        return self.client.get(url, **kwargs)

    def post(self, url: str, json: Any = None) -> Response:
        return self.client.post(url, json=json, headers=csrf_headers(self.client))

    def patch(self, url: str, json: Any = None) -> Response:
        return self.client.patch(url, json=json, headers=csrf_headers(self.client))

    def delete(self, url: str) -> Response:
        return self.client.delete(url, headers=csrf_headers(self.client))

    # -- shortcuts ----------------------------------------------------------------------------

    def create_project(self, name: str = "Alpha", **fields: Any) -> dict[str, Any]:
        response = self.post(PROJECTS, {"name": name, **fields})
        assert response.status_code == 201, response.text
        data: dict[str, Any] = response.json()["data"]
        return data

    def add_member(self, project_id: str, other: "Actor") -> Response:
        return self.post(f"{PROJECTS}/{project_id}/members", {"email": other.email})


def error_of(response: Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return body


def project_row(db: Session, project_id: str) -> Project | None:
    db.expire_all()
    return db.get(Project, uuid.UUID(project_id))


def membership_row(db: Session, project_id: str, user_id: uuid.UUID) -> ProjectMember | None:
    db.expire_all()
    return db.scalars(
        select(ProjectMember).where(
            ProjectMember.project_id == uuid.UUID(project_id), ProjectMember.user_id == user_id
        )
    ).first()


def activity_for(db: Session, project_id: str, action: str | None = None) -> list[ActivityLog]:
    db.expire_all()
    statement = select(ActivityLog).where(ActivityLog.project_id == uuid.UUID(project_id))
    if action:
        statement = statement.where(ActivityLog.action == action)
    return list(db.scalars(statement))
