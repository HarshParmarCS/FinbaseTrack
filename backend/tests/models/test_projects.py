import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Session

from app.models import Project, ProjectMember, ProjectStatus, Task, User
from tests.factories import (
    add_member,
    check_deferred_constraints,
    expect_violation,
    make_project,
    make_task,
    make_user,
)


def test_project_defaults(db_session: Session) -> None:
    owner = make_user(db_session)
    project = make_project(db_session, owner)
    db_session.refresh(project)

    assert project.status is ProjectStatus.ACTIVE
    assert project.description is None
    assert project.created_at.tzinfo is not None
    assert project.owner_id == owner.id


def test_blank_project_name_is_rejected(db_session: Session) -> None:
    owner = make_user(db_session)

    with expect_violation(db_session, "ck_projects_name_not_blank"):
        make_project(db_session, owner, name="  ")


def test_invalid_project_status_is_rejected_by_the_orm(db_session: Session) -> None:
    owner = make_user(db_session)
    project = Project(name="X", owner=owner, status="bogus")
    db_session.add(project)

    with pytest.raises(StatementError):
        db_session.flush()


def test_invalid_project_status_is_rejected_by_the_database(db_session: Session) -> None:
    owner = make_user(db_session)

    with expect_violation(db_session, "ck_projects_status_valid"):
        db_session.execute(
            text("insert into projects (name, status, owner_id) values ('X', 'bogus', :o)"),
            {"o": owner.id},
        )


# ---- owner must be a member --------------------------------------------------------------------


def test_owner_becomes_member_when_project_is_created_in_one_flush(db_session: Session) -> None:
    owner = make_user(db_session)

    project = make_project(db_session, owner)
    check_deferred_constraints(db_session)

    members = db_session.scalars(
        select(ProjectMember).where(ProjectMember.project_id == project.id)
    )
    assert [m.user_id for m in members] == [owner.id]


def test_project_without_owner_membership_cannot_be_committed(db_session: Session) -> None:
    owner = make_user(db_session)
    db_session.add(Project(name="Orphan", owner=owner))
    db_session.flush()  # the INSERT itself is accepted: the check is deferred to commit

    with expect_violation(db_session, "fk_projects_owner_member"):
        check_deferred_constraints(db_session)


def test_membership_row_may_be_inserted_after_the_project_in_the_same_transaction(
    db_session: Session,
) -> None:
    owner = make_user(db_session)
    project = Project(name="Late member", owner=owner)
    db_session.add(project)
    db_session.flush()

    add_member(db_session, project, owner, added_by=owner)

    check_deferred_constraints(db_session)  # passes: owner is a member now


def test_owner_membership_cannot_be_removed_while_the_project_exists(db_session: Session) -> None:
    owner = make_user(db_session)
    project = make_project(db_session, owner)
    check_deferred_constraints(db_session)

    db_session.execute(
        text("delete from project_members where project_id = :p and user_id = :u"),
        {"p": project.id, "u": owner.id},
    )

    with expect_violation(db_session, "fk_projects_owner_member"):
        check_deferred_constraints(db_session)


def test_non_owner_member_can_be_removed(db_session: Session) -> None:
    owner = make_user(db_session)
    other = make_user(db_session)
    project = make_project(db_session, owner)
    member = add_member(db_session, project, other)

    db_session.delete(member)
    db_session.flush()

    check_deferred_constraints(db_session)


# ---- ownership and deletion ------------------------------------------------------------------


def test_user_who_owns_a_project_cannot_be_deleted(db_session: Session) -> None:
    owner = make_user(db_session)
    make_project(db_session, owner)

    with expect_violation(db_session, "fk_projects_owner_id_users"):
        db_session.execute(text("delete from users where id = :id"), {"id": owner.id})


def test_deleting_a_project_removes_members_and_tasks_even_with_assigned_tasks(
    db_session: Session,
) -> None:
    owner = make_user(db_session)
    member = make_user(db_session)
    project = make_project(db_session, owner)
    add_member(db_session, project, member)
    make_task(db_session, project, owner, assignee_id=member.id)
    make_task(db_session, project, owner)
    project_id = project.id

    db_session.execute(text("delete from projects where id = :id"), {"id": project_id})
    check_deferred_constraints(db_session)

    for table in ("project_members", "tasks"):
        remaining = db_session.execute(
            text(f"select count(*) from {table} where project_id = :id"),  # noqa: S608 (fixed names)
            {"id": project_id},
        ).scalar_one()
        assert remaining == 0, table


def test_orm_delete_of_a_project_cascades_through_the_database(db_session: Session) -> None:
    owner = make_user(db_session)
    project = make_project(db_session, owner)
    make_task(db_session, project, owner)

    db_session.delete(project)
    db_session.flush()
    check_deferred_constraints(db_session)

    assert db_session.scalars(select(Task)).all() == []


# ---- relationships -----------------------------------------------------------------------------


def test_a_user_can_belong_to_many_projects_and_a_project_has_many_members(
    db_session: Session,
) -> None:
    ana, bob, cy = (make_user(db_session) for _ in range(3))
    first = make_project(db_session, ana, name="First")
    second = make_project(db_session, bob, name="Second")
    add_member(db_session, first, cy)
    add_member(db_session, second, cy)
    add_member(db_session, second, ana)
    db_session.expire_all()

    assert {m.project_id for m in cy.memberships} == {first.id, second.id}
    assert {m.user_id for m in second.members} == {bob.id, cy.id, ana.id}
    assert {m.user_id for m in first.members} == {ana.id, cy.id}


def test_a_project_has_many_tasks_and_an_owner(db_session: Session) -> None:
    owner = make_user(db_session)
    project = make_project(db_session, owner)
    make_task(db_session, project, owner, title="One")
    make_task(db_session, project, owner, title="Two")
    db_session.expire_all()

    assert {t.title for t in project.tasks} == {"One", "Two"}
    assert project.owner.id == owner.id
    assert [p.id for p in owner.owned_projects] == [project.id]


def test_membership_requires_existing_project_and_user(db_session: Session) -> None:
    owner = make_user(db_session)
    project = make_project(db_session, owner)

    with expect_violation(db_session, "fk_project_members_user_id_users"):
        db_session.add(
            ProjectMember(project_id=project.id, user_id=uuid.uuid4(), added_by=owner.id)
        )
        db_session.flush()

    with expect_violation(db_session, "fk_project_members_project_id_projects"):
        db_session.add(ProjectMember(project_id=uuid.uuid4(), user_id=owner.id, added_by=owner.id))
        db_session.flush()


def test_membership_must_be_unique_per_project_and_user(db_session: Session) -> None:
    owner = make_user(db_session)
    other = make_user(db_session)
    project = make_project(db_session, owner)
    add_member(db_session, project, other)

    with expect_violation(db_session, "uq_project_members_project_user"):
        add_member(db_session, project, other)

    with expect_violation(db_session, "uq_project_members_project_user"):
        add_member(db_session, project, owner)  # the owner is already a member


def test_user_loaded_through_membership_is_the_same_user(db_session: Session) -> None:
    owner = make_user(db_session)
    project = make_project(db_session, owner)
    db_session.expire_all()

    member = project.members[0]

    assert isinstance(member.user, User)
    assert member.user.id == owner.id
    assert member.project.id == project.id
