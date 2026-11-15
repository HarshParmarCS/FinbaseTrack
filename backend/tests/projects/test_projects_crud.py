"""Create, read, update and delete projects through the HTTP API."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import ActivityLog, Project, ProjectMember, Task, TaskStatus, User
from app.repositories.activity_repository import ActivityRepository
from app.repositories.project_repository import ProjectRepository
from tests.factories import make_task
from tests.projects.helpers import (
    PROJECTS,
    Actor,
    activity_for,
    error_of,
    membership_row,
    project_row,
)

# ---- create ----------------------------------------------------------------------------------


def test_create_project_returns_the_project_with_its_owner_and_member(
    ana: Actor, db_session: Session
) -> None:
    response = ana.post(PROJECTS, {"name": "Website redesign", "description": "Q4 launch"})

    assert response.status_code == 201
    data = response.json()["data"]
    assert uuid.UUID(data["id"])
    assert data["name"] == "Website redesign"
    assert data["description"] == "Q4 launch"
    assert data["status"] == "active"
    assert data["owner"] == {"id": str(ana.id), "email": ana.email, "name": "Ana"}
    assert data["member_count"] == 1
    assert data["task_counts"] == {"todo": 0, "in_progress": 0, "completed": 0}
    assert data["allowed_actions"] == ["update", "delete", "manage_members", "create_task"]
    assert [m["user"]["id"] for m in data["members"]] == [str(ana.id)]
    assert data["members"][0]["is_owner"] is True
    assert data["created_at"] and data["updated_at"]


def test_create_project_sets_the_owner_and_the_owner_membership_atomically(
    ana: Actor, db_session: Session
) -> None:
    data = ana.create_project("Alpha")

    project = project_row(db_session, data["id"])
    membership = membership_row(db_session, data["id"], ana.id)
    assert project is not None and project.owner_id == ana.id
    assert membership is not None and membership.added_by == ana.id


def test_create_project_is_all_or_nothing(
    ana: Actor, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("activity log failed")

    monkeypatch.setattr(ActivityRepository, "record", explode)

    response = ana.post(PROJECTS, {"name": "Doomed"})

    assert response.status_code == 500
    db_session.expire_all()
    assert db_session.scalar(select(func.count()).select_from(Project)) == 0
    assert db_session.scalar(select(func.count()).select_from(ProjectMember)) == 0


def test_create_project_records_activity(ana: Actor, db_session: Session) -> None:
    data = ana.create_project("Alpha")

    entries = activity_for(db_session, data["id"], "project.created")

    assert len(entries) == 1
    assert entries[0].user_id == ana.id
    assert entries[0].meta == {"name": "Alpha"}


def test_create_project_can_start_archived(ana: Actor) -> None:
    assert ana.create_project("Old", status="archived")["status"] == "archived"


@pytest.mark.parametrize("spoof", ["owner_id", "created_by", "user_id", "members", "id"])
def test_identity_fields_in_the_body_are_rejected(ana: Actor, ben: Actor, spoof: str) -> None:
    response = ana.post(PROJECTS, {"name": "X", spoof: str(ben.id)})

    assert response.status_code == 422
    assert spoof in [d["field"] for d in error_of(response)["details"]]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": ""},
        {"name": "   "},
        {"name": "x" * 121},
        {"name": "ok", "description": "d" * 5001},
        {"name": "ok", "status": "bogus"},
        {"name": None},
    ],
)
def test_invalid_project_input_is_rejected(ana: Actor, payload: dict[str, Any]) -> None:
    response = ana.post(PROJECTS, payload)

    assert response.status_code == 422
    assert error_of(response)["code"] == "VALIDATION_ERROR"


def test_name_is_trimmed_and_blank_description_becomes_null(ana: Actor) -> None:
    data = ana.create_project("  Padded  ", description="   ")

    assert data["name"] == "Padded"
    assert data["description"] is None


def test_creating_a_project_requires_authentication(app: FastAPI) -> None:
    anonymous = TestClient(app, raise_server_exceptions=False)

    response = anonymous.post(PROJECTS, json={"name": "X"})

    assert response.status_code == 401
    assert error_of(response)["code"] == "UNAUTHENTICATED"


def test_creating_a_project_needs_the_csrf_header_when_cookies_are_used(ana: Actor) -> None:
    response = ana.client.post(PROJECTS, json={"name": "X"})  # no X-CSRF-Token

    assert response.status_code == 403


def test_two_projects_can_share_a_name(ana: Actor) -> None:
    assert ana.create_project("Same")["id"] != ana.create_project("Same")["id"]


# ---- read: details and visibility ---------------------------------------------------------------


def test_a_member_sees_the_project_with_owner_and_members(
    ana: Actor, ben: Actor, db_session: Session
) -> None:
    project = ana.create_project("Shared")
    assert ana.add_member(project["id"], ben).status_code == 201

    response = ben.get(f"{PROJECTS}/{project['id']}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["owner"]["id"] == str(ana.id)
    assert data["member_count"] == 2
    assert [m["user"]["name"] for m in data["members"]] == ["Ana", "Ben"]
    assert [m["is_owner"] for m in data["members"]] == [True, False]
    # A plain member may create tasks but not manage the project.
    assert data["allowed_actions"] == ["create_task"]


def test_the_owner_sees_every_allowed_action(ana: Actor) -> None:
    project = ana.create_project("Mine")

    data = ana.get(f"{PROJECTS}/{project['id']}").json()["data"]

    assert data["allowed_actions"] == ["update", "delete", "manage_members", "create_task"]


def test_a_non_member_gets_404_not_403(ana: Actor, ben: Actor) -> None:
    project = ana.create_project("Private")

    response = ben.get(f"{PROJECTS}/{project['id']}")

    assert response.status_code == 404
    assert error_of(response)["code"] == "NOT_FOUND"


def test_a_hidden_project_looks_exactly_like_a_missing_one(ana: Actor, ben: Actor) -> None:
    project = ana.create_project("Private")

    hidden = ben.get(f"{PROJECTS}/{project['id']}")
    missing = ben.get(f"{PROJECTS}/{uuid.uuid4()}")

    assert hidden.status_code == missing.status_code == 404
    assert error_of(hidden)["message"] == error_of(missing)["message"]
    assert error_of(hidden)["details"] == error_of(missing)["details"]


def test_a_malformed_project_id_is_a_validation_error(ana: Actor) -> None:
    assert ana.get(f"{PROJECTS}/not-a-uuid").status_code == 422


def test_reading_requires_authentication(app: FastAPI, ana: Actor) -> None:
    project = ana.create_project("Alpha")
    anonymous = TestClient(app, raise_server_exceptions=False)

    assert anonymous.get(f"{PROJECTS}/{project['id']}").status_code == 401
    assert anonymous.get(PROJECTS).status_code == 401


# ---- list: scoping, search, pagination, counters -------------------------------


def test_list_returns_only_projects_the_user_is_a_member_of(
    ana: Actor, ben: Actor, cy: Actor
) -> None:
    mine = ana.create_project("Ana private")
    shared = ben.create_project("Shared by Ben")
    ben.create_project("Ben private")
    ben.add_member(shared["id"], ana)

    response = ana.get(PROJECTS)

    assert response.status_code == 200
    names = {p["name"] for p in response.json()["data"]}
    assert names == {"Ana private", "Shared by Ben"}
    assert mine["id"] in {p["id"] for p in response.json()["data"]}
    assert cy.get(PROJECTS).json()["data"] == []
    assert cy.get(PROJECTS).json()["meta"]["total"] == 0


def test_list_uses_the_pagination_envelope(ana: Actor) -> None:
    for index in range(5):
        ana.create_project(f"P{index}")

    first = ana.get(PROJECTS, params={"page": 1, "page_size": 2}).json()
    third = ana.get(PROJECTS, params={"page": 3, "page_size": 2}).json()
    beyond = ana.get(PROJECTS, params={"page": 9, "page_size": 2}).json()

    assert first["meta"] == {"page": 1, "page_size": 2, "total": 5, "total_pages": 3}
    assert len(first["data"]) == 2 and len(third["data"]) == 1
    assert beyond["data"] == [] and beyond["meta"]["total"] == 5
    assert len({p["id"] for p in first["data"]} | {p["id"] for p in third["data"]}) == 3


def test_pages_do_not_overlap_and_cover_everything(ana: Actor) -> None:
    created = {ana.create_project(f"P{i}")["id"] for i in range(7)}

    seen: list[str] = []
    for page in (1, 2, 3, 4):
        seen += [
            p["id"] for p in ana.get(PROJECTS, params={"page": page, "page_size": 2}).json()["data"]
        ]

    assert len(seen) == len(set(seen)) == 7
    assert set(seen) == created


@pytest.mark.parametrize(
    "params", [{"page": 0}, {"page": -1}, {"page_size": 0}, {"page_size": 101}, {"page": "x"}]
)
def test_invalid_pagination_is_rejected(ana: Actor, params: dict[str, Any]) -> None:
    assert ana.get(PROJECTS, params=params).status_code == 422


def test_list_is_ordered_by_most_recently_updated(ana: Actor, db_session: Session) -> None:
    old = ana.create_project("Old")
    new = ana.create_project("New")
    db_session.execute(
        text("update projects set updated_at = :t where id = :id"),
        {"t": datetime(2026, 1, 1, tzinfo=UTC), "id": old["id"]},
    )
    db_session.execute(
        text("update projects set updated_at = :t where id = :id"),
        {"t": datetime(2026, 6, 1, tzinfo=UTC), "id": new["id"]},
    )

    names = [p["name"] for p in ana.get(PROJECTS).json()["data"]]

    assert names == ["New", "Old"]


def test_search_by_name_is_case_insensitive_and_partial(ana: Actor) -> None:
    ana.create_project("Website Redesign")
    ana.create_project("Mobile app")
    ana.create_project("Redis cache")

    found = ana.get(PROJECTS, params={"q": "REDe"}).json()

    assert [p["name"] for p in found["data"]] == ["Website Redesign"]
    assert found["meta"]["total"] == 1


def test_search_treats_percent_and_underscore_literally(ana: Actor) -> None:
    ana.create_project("100% done")
    ana.create_project("100 percent")
    ana.create_project("a_b")
    ana.create_project("axb")

    percent = ana.get(PROJECTS, params={"q": "100%"}).json()["data"]
    underscore = ana.get(PROJECTS, params={"q": "a_b"}).json()["data"]
    wildcard = ana.get(PROJECTS, params={"q": "%"}).json()["data"]

    assert [p["name"] for p in percent] == ["100% done"]
    assert [p["name"] for p in underscore] == ["a_b"]
    assert [p["name"] for p in wildcard] == ["100% done"]


def test_search_never_reveals_other_users_projects(ana: Actor, ben: Actor) -> None:
    ben.create_project("Secret roadmap")

    assert ana.get(PROJECTS, params={"q": "Secret"}).json()["data"] == []


def test_filter_by_status(ana: Actor) -> None:
    ana.create_project("Live")
    ana.create_project("Done", status="archived")

    archived = ana.get(PROJECTS, params={"status": "archived"}).json()
    assert [p["name"] for p in archived["data"]] == ["Done"]
    assert ana.get(PROJECTS, params={"status": "bogus"}).status_code == 422


def test_list_reports_member_count_task_counts_and_allowed_actions(
    ana: Actor, ben: Actor, db_session: Session
) -> None:
    project = ana.create_project("Busy")
    ana.add_member(project["id"], ben)
    project_orm = project_row(db_session, project["id"])
    assert project_orm is not None
    for status in (TaskStatus.TODO, TaskStatus.TODO, TaskStatus.IN_PROGRESS):
        make_task(db_session, project_orm, ana.user, status=status)
    make_task(
        db_session,
        project_orm,
        ana.user,
        status=TaskStatus.COMPLETED,
        completed_at=datetime(2026, 11, 1, tzinfo=UTC),
    )

    item = ana.get(PROJECTS).json()["data"][0]

    assert item["member_count"] == 2
    assert item["task_counts"] == {"todo": 2, "in_progress": 1, "completed": 1}
    assert item["allowed_actions"] == ["update", "delete", "manage_members", "create_task"]
    assert "members" not in item  # the list is a summary; details carry the member list
    ben_item = ben.get(PROJECTS).json()["data"][0]
    assert ben_item["allowed_actions"] == ["create_task"]


def test_list_issues_the_same_number_of_queries_however_many_projects_exist(
    ana: Actor, ben: Actor, db_session: Session
) -> None:
    from sqlalchemy import event

    statements: list[str] = []
    connection = db_session.connection()

    def count(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        statements.append(statement)

    def queries_for_list() -> int:
        statements.clear()
        event.listen(connection, "before_cursor_execute", count)
        try:
            assert ana.get(PROJECTS, params={"page_size": 100}).status_code == 200
        finally:
            event.remove(connection, "before_cursor_execute", count)
        return len(statements)

    ana.create_project("P0")
    ana.add_member(ana.create_project("P1")["id"], ben)
    few = queries_for_list()
    for index in range(2, 15):
        project = ana.create_project(f"P{index}")
        ana.add_member(project["id"], ben)
    many = queries_for_list()

    assert few == many  # no per-project queries (no N+1)
    assert many <= 6


# ---- update -----------------------------------------------------------------------------------


def test_owner_updates_the_name_and_leaves_the_rest_alone(ana: Actor, db_session: Session) -> None:
    project = ana.create_project("Old name", description="Keep me")

    response = ana.patch(f"{PROJECTS}/{project['id']}", {"name": "New name"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "New name"
    assert data["description"] == "Keep me"  # partial update: untouched
    assert data["status"] == "active"
    assert data["members"][0]["is_owner"] is True


def test_owner_updates_the_description_only(ana: Actor) -> None:
    project = ana.create_project("Name", description="Old")

    data = ana.patch(f"{PROJECTS}/{project['id']}", {"description": "New"}).json()["data"]

    assert (data["name"], data["description"]) == ("Name", "New")


def test_an_explicit_null_clears_the_description(ana: Actor) -> None:
    project = ana.create_project("Name", description="Something")

    data = ana.patch(f"{PROJECTS}/{project['id']}", {"description": None}).json()["data"]

    assert data["description"] is None


def test_owner_can_archive_a_project(ana: Actor) -> None:
    project = ana.create_project("Name")

    data = ana.patch(f"{PROJECTS}/{project['id']}", {"status": "archived"}).json()["data"]

    assert data["status"] == "archived"


def test_update_moves_updated_at_forward(ana: Actor, db_session: Session) -> None:
    project = ana.create_project("Name")
    db_session.execute(
        text("update projects set updated_at = now() - interval '1 day' where id = :id"),
        {"id": project["id"]},
    )
    before = project_row(db_session, project["id"])
    assert before is not None
    before_time = before.updated_at

    ana.patch(f"{PROJECTS}/{project['id']}", {"name": "Changed"})

    after = project_row(db_session, project["id"])
    assert after is not None and after.updated_at > before_time


def test_update_records_the_change_in_the_activity_log(ana: Actor, db_session: Session) -> None:
    project = ana.create_project("Before")

    ana.patch(f"{PROJECTS}/{project['id']}", {"name": "After", "status": "archived"})

    entry = activity_for(db_session, project["id"], "project.updated")[0]
    assert entry.user_id == ana.id
    assert entry.meta == {
        "changes": {"name": ["Before", "After"], "status": ["active", "archived"]}
    }


def test_an_update_that_changes_nothing_succeeds_without_activity(
    ana: Actor, db_session: Session
) -> None:
    project = ana.create_project("Same")

    response = ana.patch(f"{PROJECTS}/{project['id']}", {"name": "Same"})

    assert response.status_code == 200
    assert activity_for(db_session, project["id"], "project.updated") == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": None},
        {"name": "  "},
        {"name": "x" * 121},
        {"status": None},
        {"status": "bogus"},
    ],
)
def test_invalid_updates_are_rejected(ana: Actor, payload: dict[str, Any]) -> None:
    project = ana.create_project("Name")

    assert ana.patch(f"{PROJECTS}/{project['id']}", payload).status_code == 422


@pytest.mark.parametrize("field", ["owner_id", "id", "members", "created_at"])
def test_protected_fields_cannot_be_updated(ana: Actor, ben: Actor, field: str) -> None:
    project = ana.create_project("Name")

    response = ana.patch(f"{PROJECTS}/{project['id']}", {field: str(ben.id)})

    assert response.status_code == 422


def test_a_member_who_is_not_the_owner_cannot_update(
    ana: Actor, ben: Actor, db_session: Session
) -> None:
    project = ana.create_project("Name")
    ana.add_member(project["id"], ben)

    response = ben.patch(f"{PROJECTS}/{project['id']}", {"name": "Hijacked"})

    assert response.status_code == 403
    body = error_of(response)
    assert body["code"] == "FORBIDDEN"
    assert body["details"][0]["policy_id"] == "project-update"
    persisted = project_row(db_session, project["id"])
    assert persisted is not None and persisted.name == "Name"


def test_a_non_member_cannot_update_and_gets_404(ana: Actor, ben: Actor) -> None:
    project = ana.create_project("Name")

    assert ben.patch(f"{PROJECTS}/{project['id']}", {"name": "X"}).status_code == 404


def test_updating_requires_authentication(app: FastAPI, ana: Actor) -> None:
    project = ana.create_project("Name")
    anonymous = TestClient(app, raise_server_exceptions=False)

    assert anonymous.patch(f"{PROJECTS}/{project['id']}", json={"name": "X"}).status_code == 401


# ---- delete -----------------------------------------------------------------------------------


def test_owner_deletes_the_project(ana: Actor, db_session: Session) -> None:
    project = ana.create_project("Doomed")

    response = ana.delete(f"{PROJECTS}/{project['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert project_row(db_session, project["id"]) is None
    assert ana.get(f"{PROJECTS}/{project['id']}").status_code == 404
    assert ana.get(PROJECTS).json()["data"] == []


def test_deleting_cascades_members_and_tasks_but_keeps_users(
    ana: Actor, ben: Actor, db_session: Session
) -> None:
    project = ana.create_project("Doomed")
    ana.add_member(project["id"], ben)
    project_orm = project_row(db_session, project["id"])
    assert project_orm is not None
    make_task(db_session, project_orm, ana.user, assignee_id=ben.id)  # an ASSIGNED task
    make_task(db_session, project_orm, ben.user)

    assert ana.delete(f"{PROJECTS}/{project['id']}").status_code == 204

    pid = uuid.UUID(project["id"])
    db_session.expire_all()
    assert (
        db_session.scalar(select(func.count()).select_from(Task).where(Task.project_id == pid)) == 0
    )
    assert (
        db_session.scalar(
            select(func.count()).select_from(ProjectMember).where(ProjectMember.project_id == pid)
        )
        == 0
    )
    assert db_session.scalar(select(func.count()).select_from(User)) == 2


def test_deleting_keeps_the_activity_history_and_adds_a_deletion_entry(
    ana: Actor, ben: Actor, db_session: Session
) -> None:
    project = ana.create_project("Doomed")
    ana.add_member(project["id"], ben)
    project_orm = project_row(db_session, project["id"])
    assert project_orm is not None
    make_task(db_session, project_orm, ana.user)

    ana.delete(f"{PROJECTS}/{project['id']}")

    actions = [entry.action for entry in activity_for(db_session, project["id"])]
    assert "project.created" in actions and "member.added" in actions
    deleted = activity_for(db_session, project["id"], "project.deleted")
    assert len(deleted) == 1
    assert deleted[0].user_id == ana.id
    assert deleted[0].meta == {"name": "Doomed", "member_count": 2, "task_count": 1}


def test_deleting_is_all_or_nothing(
    ana: Actor, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = ana.create_project("Survivor")

    def explode(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("delete failed")

    monkeypatch.setattr(ProjectRepository, "delete", explode)

    response = ana.delete(f"{PROJECTS}/{project['id']}")

    assert response.status_code == 500
    assert project_row(db_session, project["id"]) is not None
    assert activity_for(db_session, project["id"], "project.deleted") == []  # rolled back too


def test_a_member_who_is_not_the_owner_cannot_delete(
    ana: Actor, ben: Actor, db_session: Session
) -> None:
    project = ana.create_project("Keep")
    ana.add_member(project["id"], ben)

    response = ben.delete(f"{PROJECTS}/{project['id']}")

    assert response.status_code == 403
    assert error_of(response)["details"][0]["policy_id"] == "project-delete"
    assert project_row(db_session, project["id"]) is not None


def test_a_non_member_cannot_delete_and_gets_404(
    ana: Actor, ben: Actor, db_session: Session
) -> None:
    project = ana.create_project("Keep")

    assert ben.delete(f"{PROJECTS}/{project['id']}").status_code == 404
    assert project_row(db_session, project["id"]) is not None


def test_deleting_twice_gives_404_the_second_time(ana: Actor) -> None:
    project = ana.create_project("Once")

    assert ana.delete(f"{PROJECTS}/{project['id']}").status_code == 204
    assert ana.delete(f"{PROJECTS}/{project['id']}").status_code == 404


def test_deleting_requires_authentication_and_csrf(app: FastAPI, ana: Actor) -> None:
    project = ana.create_project("Keep")
    anonymous = TestClient(app, raise_server_exceptions=False)

    assert anonymous.delete(f"{PROJECTS}/{project['id']}").status_code == 401
    assert ana.client.delete(f"{PROJECTS}/{project['id']}").status_code == 403  # no CSRF header


# ---- every endpoint asks the policy engine ------------------------------------------------------


def test_each_endpoint_invokes_the_expected_policy_action(
    ana: Actor, ben: Actor, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.authorization.service import AuthorizationService

    asked: list[str] = []
    original = AuthorizationService.require

    def spy(self: AuthorizationService, user: User, action: Any, **kwargs: Any) -> Any:
        asked.append(str(action))
        return original(self, user, action, **kwargs)

    monkeypatch.setattr(AuthorizationService, "require", spy)

    project = ana.create_project("Alpha")
    pid = project["id"]
    ana.get(f"{PROJECTS}/{pid}")
    ana.patch(f"{PROJECTS}/{pid}", {"name": "Beta"})
    ana.add_member(pid, ben)
    ana.get(f"{PROJECTS}/{pid}/members")
    ana.delete(f"{PROJECTS}/{pid}/members/{ben.id}")
    ana.delete(f"{PROJECTS}/{pid}")

    assert asked == [
        "project.create",
        "project.view",
        "project.update",
        "project.member.manage",
        "project.view",
        "project.member.manage",
        "project.delete",
    ]


def test_activity_rows_hold_no_secrets(ana: Actor, ben: Actor, db_session: Session) -> None:
    project = ana.create_project("Alpha")
    ana.add_member(project["id"], ben)
    ana.patch(f"{PROJECTS}/{project['id']}", {"name": "Beta"})
    ana.delete(f"{PROJECTS}/{project['id']}")

    rows = db_session.scalars(select(ActivityLog)).all()
    blob = " ".join(str(r.meta) for r in rows)

    assert rows
    assert "password" not in blob.lower() and "argon2" not in blob and "token" not in blob.lower()
