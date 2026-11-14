import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Session

from app.models import Task, TaskPriority, TaskStatus
from tests.factories import (
    add_member,
    expect_violation,
    make_project,
    make_task,
    make_user,
)


def test_task_defaults(db_session: Session) -> None:
    owner = make_user(db_session)
    project = make_project(db_session, owner)

    task = make_task(db_session, project, owner)
    db_session.refresh(task)

    assert task.status is TaskStatus.TODO
    assert task.priority is TaskPriority.MEDIUM
    assert task.assignee_id is None
    assert task.due_date is None
    assert task.completed_at is None
    assert task.position == 0
    assert task.created_at.tzinfo is not None
    assert task.updated_at.tzinfo is not None


def test_task_stores_due_date_and_enum_values(db_session: Session) -> None:
    owner = make_user(db_session)
    project = make_project(db_session, owner)

    task = make_task(
        db_session,
        project,
        owner,
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        due_date=date(2026, 12, 1),
    )
    stored = db_session.execute(
        text("select status, priority, due_date from tasks where id = :id"), {"id": task.id}
    ).one()

    assert tuple(stored) == ("in_progress", "high", date(2026, 12, 1))


# ---- status and priority are constrained ---------------------------------------------------


@pytest.mark.parametrize("column", ["status", "priority"])
def test_invalid_enum_values_are_rejected_by_the_orm(db_session: Session, column: str) -> None:
    owner = make_user(db_session)
    project = make_project(db_session, owner)
    task = Task(project_id=project.id, creator_id=owner.id, title="T")
    setattr(task, column, "bogus")
    db_session.add(task)

    with pytest.raises(StatementError):
        db_session.flush()


@pytest.mark.parametrize(
    ("column", "constraint"),
    [("status", "ck_tasks_status_valid"), ("priority", "ck_tasks_priority_valid")],
)
def test_invalid_enum_values_are_rejected_by_the_database(
    db_session: Session, column: str, constraint: str
) -> None:
    owner = make_user(db_session)
    project = make_project(db_session, owner)

    with expect_violation(db_session, constraint):
        db_session.execute(
            text(
                f"insert into tasks (project_id, title, creator_id, {column}) "
                "values (:p, 'T', :c, 'bogus')"  # column is a fixed test value
            ),
            {"p": project.id, "c": owner.id},
        )


@pytest.mark.parametrize("status", ["todo", "in_progress"])
def test_valid_non_completed_statuses_are_accepted(db_session: Session, status: str) -> None:
    owner = make_user(db_session)
    project = make_project(db_session, owner)

    task = make_task(db_session, project, owner, status=TaskStatus(status))

    assert task.status == status


def test_blank_title_is_rejected(db_session: Session) -> None:
    owner = make_user(db_session)
    project = make_project(db_session, owner)

    with expect_violation(db_session, "ck_tasks_title_not_blank"):
        make_task(db_session, project, owner, title="   ")


# ---- completed_at matches status ----------------------------------------------------------


def test_completed_task_needs_a_completion_timestamp(db_session: Session) -> None:
    owner = make_user(db_session)
    project = make_project(db_session, owner)

    with expect_violation(db_session, "ck_tasks_completed_at_matches_status"):
        make_task(db_session, project, owner, status=TaskStatus.COMPLETED)


def test_completed_task_with_timestamp_is_accepted(db_session: Session) -> None:
    owner = make_user(db_session)
    project = make_project(db_session, owner)

    task = make_task(
        db_session,
        project,
        owner,
        status=TaskStatus.COMPLETED,
        completed_at=datetime(2026, 11, 15, tzinfo=UTC),
    )

    assert task.completed_at is not None


def test_open_task_cannot_have_a_completion_timestamp(db_session: Session) -> None:
    owner = make_user(db_session)
    project = make_project(db_session, owner)

    with expect_violation(db_session, "ck_tasks_completed_at_matches_status"):
        make_task(db_session, project, owner, completed_at=datetime(2026, 11, 15, tzinfo=UTC))


# ---- assignee must be a member of the task's project -----------------------------------------


def test_task_can_be_assigned_to_a_project_member(db_session: Session) -> None:
    owner = make_user(db_session)
    member = make_user(db_session)
    project = make_project(db_session, owner)
    add_member(db_session, project, member)

    task = make_task(db_session, project, owner, assignee_id=member.id)
    db_session.expire_all()

    assert task.assignee is not None
    assert task.assignee.id == member.id


def test_task_can_be_assigned_to_the_owner(db_session: Session) -> None:
    owner = make_user(db_session)
    project = make_project(db_session, owner)

    task = make_task(db_session, project, owner, assignee_id=owner.id)

    assert task.assignee_id == owner.id


def test_task_cannot_be_assigned_to_a_non_member(db_session: Session) -> None:
    owner = make_user(db_session)
    outsider = make_user(db_session)
    project = make_project(db_session, owner)

    with expect_violation(db_session, "fk_tasks_assignee_member"):
        make_task(db_session, project, owner, assignee_id=outsider.id)


def test_member_of_another_project_cannot_be_assigned(db_session: Session) -> None:
    ana = make_user(db_session)
    bob = make_user(db_session)
    make_project(db_session, bob, name="Bob's project")  # bob is a member there only
    project = make_project(db_session, ana, name="Ana's project")

    with expect_violation(db_session, "fk_tasks_assignee_member"):
        make_task(db_session, project, ana, assignee_id=bob.id)


def test_task_can_be_reassigned_to_a_non_member_only_if_rejected(db_session: Session) -> None:
    owner = make_user(db_session)
    outsider = make_user(db_session)
    project = make_project(db_session, owner)
    task = make_task(db_session, project, owner)

    with expect_violation(db_session, "fk_tasks_assignee_member"):
        task.assignee_id = outsider.id
        db_session.flush()


def test_member_with_assigned_tasks_cannot_be_removed_until_unassigned(
    db_session: Session,
) -> None:
    owner = make_user(db_session)
    member = make_user(db_session)
    project = make_project(db_session, owner)
    membership = add_member(db_session, project, member)
    task = make_task(db_session, project, owner, assignee_id=member.id)

    with expect_violation(db_session, "fk_tasks_assignee_member"):
        db_session.execute(
            text("delete from project_members where id = :id"), {"id": membership.id}
        )

    # The service's removal sequence: unassign, then remove.
    task.assignee_id = None
    db_session.flush()
    db_session.delete(membership)
    db_session.flush()

    assert db_session.get(Task, task.id) is not None


# ---- creators ------------------------------------------------------------------------------


def test_task_requires_an_existing_creator_and_project(db_session: Session) -> None:
    owner = make_user(db_session)
    project = make_project(db_session, owner)

    with expect_violation(db_session, "fk_tasks_creator_id_users"):
        db_session.add(Task(project_id=project.id, creator_id=uuid.uuid4(), title="T"))
        db_session.flush()

    with expect_violation(db_session, "fk_tasks_project_id_projects"):
        db_session.add(Task(project_id=uuid.uuid4(), creator_id=owner.id, title="T"))
        db_session.flush()


def test_creator_who_created_tasks_cannot_be_deleted(db_session: Session) -> None:
    owner = make_user(db_session)
    member = make_user(db_session)
    project = make_project(db_session, owner)
    add_member(db_session, project, member)
    make_task(db_session, project, member)

    with expect_violation(db_session, "fk_tasks_creator_id_users"):
        db_session.execute(text("delete from users where id = :id"), {"id": member.id})


def test_task_relationships_load_creator_assignee_and_project(db_session: Session) -> None:
    owner = make_user(db_session)
    member = make_user(db_session)
    project = make_project(db_session, owner)
    add_member(db_session, project, member)
    task = make_task(db_session, project, owner, assignee_id=member.id)
    db_session.expire_all()

    assert task.creator.id == owner.id
    assert task.assignee is not None and task.assignee.id == member.id
    assert task.project.id == project.id


# ---- search -------------------------------------------------------------------------------


def test_case_insensitive_search_on_title_and_description(db_session: Session) -> None:
    owner = make_user(db_session)
    project = make_project(db_session, owner)
    make_task(db_session, project, owner, title="Design LOGIN page")
    make_task(db_session, project, owner, title="Write docs", description="explain the login flow")
    make_task(db_session, project, owner, title="Deploy")

    found = db_session.scalars(
        select(Task.title).where(Task.title.ilike("%login%") | Task.description.ilike("%login%"))
    ).all()

    assert sorted(found) == ["Design LOGIN page", "Write docs"]
