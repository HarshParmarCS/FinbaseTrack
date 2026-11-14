"""Small helpers that build valid rows for model tests."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Project, ProjectMember, Task, User


def make_user(session: Session, name: str = "Ana Lopez", email: str | None = None) -> User:
    user = User(
        name=name,
        email=email or f"{uuid.uuid4().hex}@example.com",
        password_hash="argon2-hash-placeholder",
    )
    session.add(user)
    session.flush()
    return user


def add_member(
    session: Session, project: Project, user: User, added_by: User | None = None
) -> ProjectMember:
    member = ProjectMember(
        project_id=project.id, user_id=user.id, added_by=(added_by or project.owner).id
    )
    session.add(member)
    session.flush()
    return member


def make_project(session: Session, owner: User, name: str = "Website redesign") -> Project:
    """A project plus its owner's membership, built the way the service will build it."""
    project = Project(
        name=name,
        owner=owner,
        members=[ProjectMember(user=owner, added_by=owner.id)],
    )
    session.add(project)
    session.flush()
    return project


def make_task(session: Session, project: Project, creator: User, **fields: Any) -> Task:
    fields.setdefault("title", "Design login")
    task = Task(project_id=project.id, creator_id=creator.id, **fields)
    session.add(task)
    session.flush()
    return task


def check_deferred_constraints(session: Session) -> None:
    """Run deferred constraint checks now (they are normally checked at COMMIT)."""
    session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    session.execute(text("SET CONSTRAINTS ALL DEFERRED"))


@contextmanager
def expect_violation(session: Session, constraint: str) -> Iterator[None]:
    """Assert that the block violates the named database constraint.

    The block runs in a savepoint so the test session stays usable afterwards.
    """
    with pytest.raises(IntegrityError) as info, session.begin_nested():
        yield
    violated = getattr(info.value.orig, "diag", None)
    assert violated is not None
    assert violated.constraint_name == constraint, str(info.value.orig)


@contextmanager
def expect_not_null_violation(session: Session, column: str) -> Iterator[None]:
    """Assert that the block inserts NULL into the named NOT NULL column."""
    with pytest.raises(IntegrityError) as info, session.begin_nested():
        yield
    diag = getattr(info.value.orig, "diag", None)
    assert diag is not None
    assert diag.column_name == column, str(info.value.orig)
