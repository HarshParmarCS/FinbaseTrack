"""Membership management: add, list, remove, and immediate access revocation."""

import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import ProjectMember, Task, TaskStatus
from app.repositories.project_member_repository import ProjectMemberRepository
from tests.auth.helpers import register
from tests.factories import make_task
from tests.projects.helpers import (
    PROJECTS,
    Actor,
    activity_for,
    error_of,
    membership_row,
    project_row,
)


def members_url(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/members"


# ---- add ---------------------------------------------------------------------------------------


def test_owner_adds_a_member_by_email(ana: Actor, ben: Actor, db_session: Session) -> None:
    project = ana.create_project("Team")

    response = ana.post(members_url(project["id"]), {"email": ben.email})

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["user"] == {"id": str(ben.id), "email": ben.email, "name": "Ben"}
    assert data["is_owner"] is False
    assert data["joined_at"]
    membership = membership_row(db_session, project["id"], ben.id)
    assert membership is not None and membership.added_by == ana.id


def test_owner_adds_a_member_by_user_id(ana: Actor, ben: Actor) -> None:
    project = ana.create_project("Team")

    response = ana.post(members_url(project["id"]), {"user_id": str(ben.id)})

    assert response.status_code == 201
    assert response.json()["data"]["user"]["id"] == str(ben.id)


def test_the_email_is_normalized_before_lookup(ana: Actor, ben: Actor) -> None:
    project = ana.create_project("Team")

    response = ana.post(members_url(project["id"]), {"email": f"  {ben.email.upper()} "})

    assert response.status_code == 201


def test_adding_a_member_is_recorded_and_counted(
    ana: Actor, ben: Actor, db_session: Session
) -> None:
    project = ana.create_project("Team")

    ana.add_member(project["id"], ben)

    entry = activity_for(db_session, project["id"], "member.added")[0]
    assert entry.user_id == ana.id
    assert entry.meta == {"member_user_id": str(ben.id)}
    assert ana.get(f"{PROJECTS}/{project['id']}").json()["data"]["member_count"] == 2


def test_the_new_member_gets_access_immediately(ana: Actor, ben: Actor) -> None:
    project = ana.create_project("Team")
    assert ben.get(f"{PROJECTS}/{project['id']}").status_code == 404

    ana.add_member(project["id"], ben)

    assert ben.get(f"{PROJECTS}/{project['id']}").status_code == 200
    assert [p["name"] for p in ben.get(PROJECTS).json()["data"]] == ["Team"]


def test_adding_the_same_member_twice_is_a_conflict(
    ana: Actor, ben: Actor, db_session: Session
) -> None:
    project = ana.create_project("Team")
    assert ana.add_member(project["id"], ben).status_code == 201

    response = ana.add_member(project["id"], ben)

    assert response.status_code == 409
    assert error_of(response)["code"] == "CONFLICT"
    assert "already a member" in error_of(response)["message"]
    count = db_session.scalar(
        select(func.count())
        .select_from(ProjectMember)
        .where(ProjectMember.project_id == uuid.UUID(project["id"]))
    )
    assert count == 2  # owner + ben, no duplicate


def test_adding_the_owner_again_is_a_conflict(ana: Actor) -> None:
    project = ana.create_project("Team")

    assert ana.post(members_url(project["id"]), {"email": ana.email}).status_code == 409


def test_a_duplicate_that_slips_past_the_check_is_still_a_conflict(
    ana: Actor, ben: Actor, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two owners' requests racing: the first check says 'not a member', the database says no."""
    project = ana.create_project("Team")
    ana.add_member(project["id"], ben)
    monkeypatch.setattr(ProjectMemberRepository, "get", lambda self, project_id, user_id: None)

    response = ana.add_member(project["id"], ben)

    assert response.status_code == 409
    assert error_of(response)["code"] == "CONFLICT"


def test_adding_a_user_that_does_not_exist_is_404(ana: Actor) -> None:
    project = ana.create_project("Team")

    by_email = ana.post(members_url(project["id"]), {"email": "nobody@example.com"})
    by_id = ana.post(members_url(project["id"]), {"user_id": str(uuid.uuid4())})

    for response in (by_email, by_id):
        assert response.status_code == 404
        assert error_of(response)["code"] == "NOT_FOUND"
        assert error_of(response)["message"] == "User not found."


def test_an_inactive_user_cannot_be_added(ana: Actor, ben: Actor, db_session: Session) -> None:
    project = ana.create_project("Team")
    ben.user.is_active = False
    db_session.flush()

    response = ana.add_member(project["id"], ben)

    assert response.status_code == 404
    assert error_of(response)["message"] == "User not found."


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"email": None},
        {"email": "a@example.com", "user_id": str(uuid.uuid4())},
        {"email": "not-an-email"},
        {"user_id": "not-a-uuid"},
        {"email": "a@example.com", "role": "admin"},
        {"name": "Ben"},
    ],
)
def test_invalid_member_requests_are_rejected(ana: Actor, payload: dict[str, Any]) -> None:
    project = ana.create_project("Team")

    response = ana.post(members_url(project["id"]), payload)

    assert response.status_code == 422
    assert error_of(response)["code"] == "VALIDATION_ERROR"


def test_a_member_who_is_not_the_owner_cannot_add_members(
    ana: Actor, ben: Actor, cy: Actor, db_session: Session
) -> None:
    project = ana.create_project("Team")
    ana.add_member(project["id"], ben)

    response = ben.add_member(project["id"], cy)

    assert response.status_code == 403
    assert error_of(response)["details"][0]["policy_id"] == "project-member-manage"
    assert membership_row(db_session, project["id"], cy.id) is None


def test_a_non_member_cannot_add_anyone_including_themselves(
    ana: Actor, ben: Actor, db_session: Session
) -> None:
    project = ana.create_project("Team")

    assert ben.add_member(project["id"], ben).status_code == 404
    assert membership_row(db_session, project["id"], ben.id) is None


def test_adding_to_a_missing_project_is_404(ana: Actor, ben: Actor) -> None:
    assert ana.add_member(str(uuid.uuid4()), ben).status_code == 404


def test_adding_requires_authentication_and_csrf(app: FastAPI, ana: Actor, ben: Actor) -> None:
    project = ana.create_project("Team")
    anonymous = TestClient(app, raise_server_exceptions=False)

    assert anonymous.post(members_url(project["id"]), json={"email": ben.email}).status_code == 401
    no_csrf = ana.client.post(members_url(project["id"]), json={"email": ben.email})
    assert no_csrf.status_code == 403


# ---- list --------------------------------------------------------------------------------------


def test_members_are_listed_owner_first_then_by_join_time(
    ana: Actor, ben: Actor, cy: Actor, db_session: Session
) -> None:
    project = ana.create_project("Team")
    ana.add_member(project["id"], cy)
    ana.add_member(project["id"], ben)
    db_session.execute(
        text("update project_members set joined_at = :t where user_id = :u and project_id = :p"),
        {"t": datetime(2026, 1, 1, tzinfo=UTC), "u": cy.id, "p": project["id"]},
    )
    db_session.execute(
        text("update project_members set joined_at = :t where user_id = :u and project_id = :p"),
        {"t": datetime(2026, 2, 1, tzinfo=UTC), "u": ben.id, "p": project["id"]},
    )

    response = ana.get(members_url(project["id"]))

    assert response.status_code == 200
    data = response.json()["data"]
    assert [m["user"]["name"] for m in data] == ["Ana", "Cy", "Ben"]
    assert [m["is_owner"] for m in data] == [True, False, False]
    assert all(set(m) == {"user", "is_owner", "joined_at"} for m in data)


def test_any_member_can_list_members(ana: Actor, ben: Actor) -> None:
    project = ana.create_project("Team")
    ana.add_member(project["id"], ben)

    response = ben.get(members_url(project["id"]))

    assert response.status_code == 200
    assert len(response.json()["data"]) == 2


def test_a_non_member_cannot_list_members(ana: Actor, ben: Actor) -> None:
    project = ana.create_project("Team")

    response = ben.get(members_url(project["id"]))

    assert response.status_code == 404
    assert response.status_code == ben.get(members_url(str(uuid.uuid4()))).status_code


def test_listing_members_requires_authentication(app: FastAPI, ana: Actor) -> None:
    project = ana.create_project("Team")

    anonymous = TestClient(app, raise_server_exceptions=False)
    assert anonymous.get(members_url(project["id"])).status_code == 401


# ---- remove ------------------------------------------------------------------------------------


def test_owner_removes_a_member(ana: Actor, ben: Actor, db_session: Session) -> None:
    project = ana.create_project("Team")
    ana.add_member(project["id"], ben)

    response = ana.delete(f"{members_url(project['id'])}/{ben.id}")

    assert response.status_code == 204
    assert response.content == b""
    assert membership_row(db_session, project["id"], ben.id) is None
    assert ana.get(f"{PROJECTS}/{project['id']}").json()["data"]["member_count"] == 1
    entry = activity_for(db_session, project["id"], "member.removed")[0]
    assert entry.user_id == ana.id
    assert entry.meta == {"member_user_id": str(ben.id), "unassigned_task_count": 0}


def test_a_removed_member_loses_access_to_everything_immediately(ana: Actor, ben: Actor) -> None:
    project = ana.create_project("Team")
    pid = project["id"]
    ana.add_member(pid, ben)
    assert ben.get(f"{PROJECTS}/{pid}").status_code == 200
    assert ben.get(members_url(pid)).status_code == 200
    assert len(ben.get(PROJECTS).json()["data"]) == 1

    assert ana.delete(f"{members_url(pid)}/{ben.id}").status_code == 204

    # Same session, same tokens: nothing cached, the very next request is refused.
    assert ben.get(f"{PROJECTS}/{pid}").status_code == 404
    assert ben.get(members_url(pid)).status_code == 404
    assert ben.patch(f"{PROJECTS}/{pid}", {"name": "x"}).status_code == 404
    assert ben.delete(f"{PROJECTS}/{pid}").status_code == 404
    assert ben.add_member(pid, ben).status_code == 404
    assert ben.get(PROJECTS).json()["data"] == []
    assert ben.get(PROJECTS).json()["meta"]["total"] == 0


def test_a_removed_member_can_be_added_again(ana: Actor, ben: Actor) -> None:
    project = ana.create_project("Team")
    ana.add_member(project["id"], ben)
    ana.delete(f"{members_url(project['id'])}/{ben.id}")

    assert ana.add_member(project["id"], ben).status_code == 201
    assert ben.get(f"{PROJECTS}/{project['id']}").status_code == 200


def test_the_project_owner_cannot_be_removed(ana: Actor, db_session: Session) -> None:
    project = ana.create_project("Team")

    response = ana.delete(f"{members_url(project['id'])}/{ana.id}")

    assert response.status_code == 422
    assert error_of(response)["code"] == "BUSINESS_RULE_VIOLATION"
    assert "owner cannot be removed" in error_of(response)["message"]
    assert membership_row(db_session, project["id"], ana.id) is not None
    assert ana.get(f"{PROJECTS}/{project['id']}").status_code == 200


def test_removing_someone_who_is_not_a_member_is_404(ana: Actor, ben: Actor) -> None:
    project = ana.create_project("Team")

    stranger = ana.delete(f"{members_url(project['id'])}/{ben.id}")
    unknown = ana.delete(f"{members_url(project['id'])}/{uuid.uuid4()}")

    for response in (stranger, unknown):
        assert response.status_code == 404
        assert error_of(response)["message"] == "Member not found."


def test_a_malformed_user_id_is_a_validation_error(ana: Actor) -> None:
    project = ana.create_project("Team")

    assert ana.delete(f"{members_url(project['id'])}/not-a-uuid").status_code == 422


def test_a_member_who_is_not_the_owner_cannot_remove_members(
    ana: Actor, ben: Actor, cy: Actor, db_session: Session
) -> None:
    project = ana.create_project("Team")
    ana.add_member(project["id"], ben)
    ana.add_member(project["id"], cy)

    response = ben.delete(f"{members_url(project['id'])}/{cy.id}")

    assert response.status_code == 403
    assert error_of(response)["details"][0]["policy_id"] == "project-member-manage"
    assert membership_row(db_session, project["id"], cy.id) is not None


def test_a_member_cannot_remove_themselves_or_the_owner(ana: Actor, ben: Actor) -> None:
    project = ana.create_project("Team")
    ana.add_member(project["id"], ben)

    assert ben.delete(f"{members_url(project['id'])}/{ben.id}").status_code == 403
    assert ben.delete(f"{members_url(project['id'])}/{ana.id}").status_code == 403


def test_a_non_member_cannot_remove_members(ana: Actor, ben: Actor, cy: Actor) -> None:
    project = ana.create_project("Team")
    ana.add_member(project["id"], ben)

    assert cy.delete(f"{members_url(project['id'])}/{ben.id}").status_code == 404


def test_removing_requires_authentication_and_csrf(app: FastAPI, ana: Actor, ben: Actor) -> None:
    project = ana.create_project("Team")
    ana.add_member(project["id"], ben)
    anonymous = TestClient(app, raise_server_exceptions=False)
    url = f"{members_url(project['id'])}/{ben.id}"

    assert anonymous.delete(url).status_code == 401
    assert ana.client.delete(url).status_code == 403  # no CSRF header


# ---- removal handles task assignments ------------------------------------------------------------


def test_removing_a_member_unassigns_their_tasks_in_this_project(
    ana: Actor, ben: Actor, db_session: Session
) -> None:
    project = ana.create_project("Team")
    other = ana.create_project("Other project")
    ana.add_member(project["id"], ben)
    ana.add_member(other["id"], ben)
    project_orm = project_row(db_session, project["id"])
    other_orm = project_row(db_session, other["id"])
    assert project_orm is not None and other_orm is not None
    todo = make_task(db_session, project_orm, ana.user, assignee_id=ben.id)
    doing = make_task(
        db_session, project_orm, ana.user, assignee_id=ben.id, status=TaskStatus.IN_PROGRESS
    )
    done = make_task(
        db_session,
        project_orm,
        ana.user,
        assignee_id=ben.id,
        status=TaskStatus.COMPLETED,
        completed_at=datetime(2026, 11, 1, tzinfo=UTC),
        description="d",
        due_date=date(2026, 12, 1),
    )
    elsewhere = make_task(db_session, other_orm, ana.user, assignee_id=ben.id)
    created_by_ben = make_task(db_session, project_orm, ben.user, title="Ben's own")

    response = ana.delete(f"{members_url(project['id'])}/{ben.id}")

    assert response.status_code == 204
    db_session.expire_all()
    for task in (todo, doing, done):
        assert db_session.get(Task, task.id).assignee_id is None  # type: ignore[union-attr]
    assert db_session.get(Task, elsewhere.id).assignee_id == ben.id  # type: ignore[union-attr]
    kept = db_session.get(Task, created_by_ben.id)
    assert kept is not None and kept.creator_id == ben.id and kept.assignee_id is None
    assert membership_row(db_session, project["id"], ben.id) is None
    assert membership_row(db_session, other["id"], ben.id) is not None


def test_task_unassignments_are_recorded(ana: Actor, ben: Actor, db_session: Session) -> None:
    project = ana.create_project("Team")
    ana.add_member(project["id"], ben)
    project_orm = project_row(db_session, project["id"])
    assert project_orm is not None
    first = make_task(db_session, project_orm, ana.user, assignee_id=ben.id)
    second = make_task(db_session, project_orm, ana.user, assignee_id=ben.id)

    ana.delete(f"{members_url(project['id'])}/{ben.id}")

    removed = activity_for(db_session, project["id"], "member.removed")[0]
    assert removed.meta["unassigned_task_count"] == 2
    unassigned = activity_for(db_session, project["id"], "task.unassigned")
    assert {entry.task_id for entry in unassigned} == {first.id, second.id}
    assert all(entry.meta["former_assignee_id"] == str(ben.id) for entry in unassigned)


def test_removing_a_member_is_all_or_nothing(
    ana: Actor, ben: Actor, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = ana.create_project("Team")
    ana.add_member(project["id"], ben)
    project_orm = project_row(db_session, project["id"])
    assert project_orm is not None
    task = make_task(db_session, project_orm, ana.user, assignee_id=ben.id)
    db_session.commit()  # the setup data is committed; only the failing request must roll back

    def explode(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("delete failed")

    monkeypatch.setattr(ProjectMemberRepository, "delete", explode)

    response = ana.delete(f"{members_url(project['id'])}/{ben.id}")

    assert response.status_code == 500
    db_session.expire_all()
    assert membership_row(db_session, project["id"], ben.id) is not None
    assert db_session.get(Task, task.id).assignee_id == ben.id  # type: ignore[union-attr]
    assert activity_for(db_session, project["id"], "member.removed") == []


# ---- visibility across users -----------------------------------------------------------------


def test_users_only_ever_see_their_own_projects(ana: Actor, ben: Actor) -> None:
    ana_project = ana.create_project("Ana's")
    ben_project = ben.create_project("Ben's")

    assert [p["id"] for p in ana.get(PROJECTS).json()["data"]] == [ana_project["id"]]
    assert [p["id"] for p in ben.get(PROJECTS).json()["data"]] == [ben_project["id"]]
    assert ana.get(f"{PROJECTS}/{ben_project['id']}").status_code == 404
    assert ben.get(f"{PROJECTS}/{ana_project['id']}").status_code == 404
    assert ana.get(members_url(ben_project["id"])).status_code == 404


def test_registering_a_third_user_does_not_leak_anything(
    ana: Actor, app: FastAPI, db_session: Session
) -> None:
    ana.create_project("Private")
    newcomer = TestClient(app, raise_server_exceptions=False)
    register(newcomer, email="new@example.com", name="New")

    assert newcomer.get(PROJECTS).json()["data"] == []
