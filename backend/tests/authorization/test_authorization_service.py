"""The enforcement point against real PostgreSQL data (PIP + PDP + PEP together)."""

import logging
import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.authorization.context import TaskChanges
from app.authorization.decision import ReasonCode
from app.authorization.engine import PolicyEngine
from app.authorization.information import PolicyInformationPoint
from app.authorization.policies import Action
from app.authorization.service import AuthorizationService
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.models import ProjectMember, TaskStatus, User
from tests.authorization.helpers import shipped_engine
from tests.factories import add_member, make_project, make_task, make_user


@pytest.fixture
def authz(db_session: Session) -> AuthorizationService:
    return AuthorizationService(shipped_engine(), PolicyInformationPoint(db_session))


class World:
    """owner + member + assignee are in the project; outsider is not."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.owner = make_user(db, name="Owner")
        self.member = make_user(db, name="Member")
        self.assignee = make_user(db, name="Assignee")
        self.outsider = make_user(db, name="Outsider")
        self.project = make_project(db, self.owner)
        add_member(db, self.project, self.member)
        add_member(db, self.project, self.assignee)

    def task(self, **fields: object) -> "object":
        fields.setdefault("creator_id", self.member.id)
        creator = self.db.get(User, fields.pop("creator_id"))
        assert creator is not None
        return make_task(self.db, self.project, creator, **fields)


@pytest.fixture
def world(db_session: Session) -> World:
    return World(db_session)


def complete_task_fields(world: World) -> dict[str, object]:
    return {
        "description": "Wireframes",
        "priority": "high",
        "due_date": date(2026, 12, 1),
        "assignee_id": world.assignee.id,
    }


# ---- project.* ---------------------------------------------------------------------------------


def test_member_can_view_the_project(authz: AuthorizationService, world: World) -> None:
    ctx = authz.require(world.member, Action.PROJECT_VIEW, project_id=world.project.id)

    assert ctx.is_project_member is True
    assert ctx.project is not None and ctx.project.owner_id == world.owner.id


def test_non_member_gets_not_found_not_forbidden(authz: AuthorizationService, world: World) -> None:
    with pytest.raises(NotFoundError):
        authz.require(world.outsider, Action.PROJECT_VIEW, project_id=world.project.id)


def test_missing_and_hidden_projects_are_indistinguishable(
    authz: AuthorizationService, world: World
) -> None:
    with pytest.raises(NotFoundError) as hidden:
        authz.require(world.outsider, Action.PROJECT_VIEW, project_id=world.project.id)
    with pytest.raises(NotFoundError) as missing:
        authz.require(world.outsider, Action.PROJECT_VIEW, project_id=uuid.uuid4())

    assert hidden.value.message == missing.value.message
    assert hidden.value.status_code == missing.value.status_code == 404


@pytest.mark.parametrize("action", [Action.PROJECT_UPDATE, Action.PROJECT_DELETE])
def test_only_the_owner_may_update_or_delete_a_project(
    authz: AuthorizationService, world: World, action: Action
) -> None:
    authz.require(world.owner, action, project_id=world.project.id)  # owner: no exception

    with pytest.raises(PermissionDeniedError) as denied:
        authz.require(world.member, action, project_id=world.project.id)
    assert denied.value.status_code == 403
    assert denied.value.details[0].policy_id == action.value.replace(".", "-")
    with pytest.raises(NotFoundError):
        authz.require(world.outsider, action, project_id=world.project.id)


# ---- removed members lose access immediately ----------------------------------------------------


def test_a_removed_member_loses_access_on_the_very_next_decision(
    authz: AuthorizationService, world: World, db_session: Session
) -> None:
    authz.require(world.member, Action.PROJECT_VIEW, project_id=world.project.id)
    # The session now knows the membership as an ORM object. Delete the row behind its back.
    membership = db_session.query(ProjectMember).filter_by(user_id=world.member.id).one()
    assert membership in db_session
    db_session.execute(
        text("delete from project_members where user_id = :u"), {"u": world.member.id}
    )

    with pytest.raises(NotFoundError):
        authz.require(world.member, Action.PROJECT_VIEW, project_id=world.project.id)
    with pytest.raises(NotFoundError):
        authz.require_task_create(world.member, world.project.id, TaskChanges(title="Sneaky"))


def test_a_removed_creator_can_no_longer_update_their_own_task(
    authz: AuthorizationService, world: World, db_session: Session
) -> None:
    task = world.task()
    authz.require(world.member, Action.TASK_UPDATE, task_id=task.id)  # type: ignore[attr-defined]
    db_session.execute(
        text("delete from project_members where user_id = :u"), {"u": world.member.id}
    )

    with pytest.raises(NotFoundError):
        authz.require(world.member, Action.TASK_UPDATE, task_id=task.id)  # type: ignore[attr-defined]


def test_a_removed_assignee_can_no_longer_update_the_task(
    authz: AuthorizationService, world: World, db_session: Session
) -> None:
    task = world.task(assignee_id=world.assignee.id)
    authz.require(world.assignee, Action.TASK_UPDATE, task_id=task.id)  # type: ignore[attr-defined]
    # Unassign (the real removal sequence), then remove the membership.
    db_session.execute(text("update tasks set assignee_id = null"))
    db_session.execute(
        text("delete from project_members where user_id = :u"), {"u": world.assignee.id}
    )

    with pytest.raises(NotFoundError):
        authz.require(world.assignee, Action.TASK_UPDATE, task_id=task.id)  # type: ignore[attr-defined]


# ---- guessed UUIDs ----------------------------------------------------------------------------


def test_a_task_in_a_project_the_user_cannot_access_is_not_found(
    authz: AuthorizationService, world: World, db_session: Session
) -> None:
    my_project_owner = world.outsider
    my_project = make_project(db_session, my_project_owner, name="Outsider's own project")
    assert my_project.id != world.project.id
    secret_task = world.task()

    for action in (Action.TASK_UPDATE, Action.TASK_DELETE, Action.TASK_COMPLETE):
        with pytest.raises(NotFoundError):
            authz.require(my_project_owner, action, task_id=secret_task.id)  # type: ignore[attr-defined]


def test_unknown_task_ids_look_the_same_as_hidden_ones(
    authz: AuthorizationService, world: World
) -> None:
    task = world.task()
    with pytest.raises(NotFoundError) as hidden:
        authz.require(world.outsider, Action.TASK_UPDATE, task_id=task.id)  # type: ignore[attr-defined]
    with pytest.raises(NotFoundError) as missing:
        authz.require(world.outsider, Action.TASK_UPDATE, task_id=uuid.uuid4())

    assert hidden.value.message == missing.value.message


def test_the_project_is_derived_from_the_task_not_supplied_by_the_caller(
    authz: AuthorizationService, world: World
) -> None:
    task = world.task()

    with pytest.raises(ValueError, match="either project_id or task_id"):
        authz.require(
            world.outsider,
            Action.TASK_UPDATE,
            task_id=task.id,  # type: ignore[attr-defined]
            project_id=world.project.id,
        )


# ---- task.update -----------------------------------------------------------------------------


def test_creator_and_assignee_may_update_but_the_owner_may_not(
    authz: AuthorizationService, world: World
) -> None:
    task = world.task(assignee_id=world.assignee.id)
    changes = TaskChanges(title="Renamed")

    authz.require_task_update(world.member, task.id, changes)  # type: ignore[attr-defined]
    authz.require_task_update(world.assignee, task.id, changes)  # type: ignore[attr-defined]
    with pytest.raises(PermissionDeniedError) as denied:
        authz.require_task_update(world.owner, task.id, changes)  # type: ignore[attr-defined]
    assert denied.value.details[0].policy_id == "task-update"


# ---- task.delete ----------------------------------------------------------------------------


def test_owner_can_delete_a_todo_task(authz: AuthorizationService, world: World) -> None:
    task = world.task(status=TaskStatus.TODO)

    authz.require(world.owner, Action.TASK_DELETE, task_id=task.id)  # type: ignore[attr-defined]


def test_project_owner_cannot_delete_an_in_progress_task(
    authz: AuthorizationService, world: World
) -> None:
    task = world.task(status=TaskStatus.IN_PROGRESS)

    with pytest.raises(PermissionDeniedError) as denied:
        authz.require(world.owner, Action.TASK_DELETE, task_id=task.id)  # type: ignore[attr-defined]

    assert denied.value.status_code == 403
    assert denied.value.details[0].policy_id == "task-delete"
    assert "todo" in denied.value.message


def test_a_creator_who_is_not_the_owner_cannot_delete_even_a_todo_task(
    authz: AuthorizationService, world: World
) -> None:
    task = world.task(status=TaskStatus.TODO)

    with pytest.raises(PermissionDeniedError):
        authz.require(world.member, Action.TASK_DELETE, task_id=task.id)  # type: ignore[attr-defined]


def test_owner_cannot_delete_a_completed_task(authz: AuthorizationService, world: World) -> None:
    task = world.task(
        status=TaskStatus.COMPLETED,
        completed_at=datetime(2026, 11, 15, tzinfo=UTC),
        **complete_task_fields(world),
    )

    with pytest.raises(PermissionDeniedError):
        authz.require(world.owner, Action.TASK_DELETE, task_id=task.id)  # type: ignore[attr-defined]


# ---- task.complete (enforced together with update/create) --------------------------------------


def test_completing_a_task_without_an_assignee_is_denied_by_the_completion_policy(
    authz: AuthorizationService, world: World
) -> None:
    task = world.task(description="d", priority="high", due_date=date(2026, 12, 1))  # no assignee
    changes = TaskChanges(status="completed")

    with pytest.raises(PermissionDeniedError) as denied:
        authz.require_task_update(world.member, task.id, changes)  # type: ignore[attr-defined]

    assert denied.value.details[0].policy_id == "task-complete"


def test_completing_a_complete_assigned_task_is_allowed(
    authz: AuthorizationService, world: World
) -> None:
    task = world.task(**complete_task_fields(world))

    authz.require_task_update(world.member, task.id, TaskChanges(status="completed"))  # type: ignore[attr-defined]


def test_completing_with_missing_information_is_denied_and_the_message_explains(
    authz: AuthorizationService, world: World
) -> None:
    fields = complete_task_fields(world)
    fields["description"] = "   "
    task = world.task(**fields)

    with pytest.raises(PermissionDeniedError) as denied:
        authz.require_task_update(world.member, task.id, TaskChanges(status="completed"))  # type: ignore[attr-defined]

    assert "title, description, priority and due date" in denied.value.message


def test_the_same_change_can_complete_a_task_by_filling_in_what_was_missing(
    authz: AuthorizationService, world: World
) -> None:
    task = world.task(assignee_id=world.assignee.id)  # no description, priority default, no date

    authz.require_task_update(
        world.member,
        task.id,  # type: ignore[attr-defined]
        TaskChanges(status="completed", description="Now written", due_date=date(2026, 12, 2)),
    )


def test_clearing_required_information_on_a_completed_task_is_denied(
    authz: AuthorizationService, world: World
) -> None:
    task = world.task(
        status=TaskStatus.COMPLETED,
        completed_at=datetime(2026, 11, 15, tzinfo=UTC),
        **complete_task_fields(world),
    )

    with pytest.raises(PermissionDeniedError):
        authz.require_task_update(world.member, task.id, TaskChanges(due_date=None))  # type: ignore[attr-defined]


def test_assigning_a_non_member_while_completing_is_denied(
    authz: AuthorizationService, world: World
) -> None:
    task = world.task(**complete_task_fields(world))

    with pytest.raises(PermissionDeniedError) as denied:
        authz.require_task_update(
            world.member,
            task.id,  # type: ignore[attr-defined]
            TaskChanges(status="completed", assignee_id=world.outsider.id),
        )

    assert denied.value.details[0].policy_id == "task-complete"


def test_creating_an_already_completed_task_needs_the_completion_information(
    authz: AuthorizationService, world: World
) -> None:
    bare = TaskChanges(title="Ship it", status="completed")
    full = TaskChanges(
        title="Ship it",
        status="completed",
        description="Done",
        priority="low",
        due_date=date(2026, 12, 1),
        assignee_id=world.assignee.id,
    )

    with pytest.raises(PermissionDeniedError):
        authz.require_task_create(world.member, world.project.id, bare)
    authz.require_task_create(world.member, world.project.id, full)


def test_creating_an_ordinary_task_needs_only_membership(
    authz: AuthorizationService, world: World
) -> None:
    authz.require_task_create(world.member, world.project.id, TaskChanges(title="Plain"))
    with pytest.raises(NotFoundError):
        authz.require_task_create(world.outsider, world.project.id, TaskChanges(title="Plain"))


# ---- non-raising evaluation, inactive users, unknown actions, logging ---------------------------


def test_evaluate_returns_a_decision_without_raising(
    authz: AuthorizationService, world: World
) -> None:
    allowed = authz.evaluate(world.owner, Action.PROJECT_DELETE, project_id=world.project.id)
    denied = authz.evaluate(world.member, Action.PROJECT_DELETE, project_id=world.project.id)
    missing = authz.evaluate(world.owner, Action.PROJECT_DELETE, project_id=uuid.uuid4())

    assert allowed.allowed is True and allowed.reason_code is ReasonCode.ALLOWED
    assert denied.allowed is False and denied.policy_id == "project-delete"
    assert missing.allowed is False and missing.reason_code is ReasonCode.RESOURCE_NOT_FOUND


def test_an_inactive_member_is_denied(authz: AuthorizationService, world: World) -> None:
    world.member.is_active = False
    world.db.flush()

    with pytest.raises(PermissionDeniedError):
        authz.require(world.member, Action.PROJECT_VIEW, project_id=world.project.id)


def test_an_unknown_action_is_denied_for_a_member(
    authz: AuthorizationService, world: World
) -> None:
    decision = authz.evaluate(world.owner, "project.nuke", project_id=world.project.id)

    assert decision.reason_code is ReasonCode.UNKNOWN_ACTION
    with pytest.raises(PermissionDeniedError):
        authz.require(world.owner, "project.nuke", project_id=world.project.id)


def test_a_denial_is_logged_with_ids_only(
    authz: AuthorizationService, world: World, caplog: pytest.LogCaptureFixture
) -> None:
    with (
        caplog.at_level(logging.INFO, logger="app.authorization.service"),
        pytest.raises(PermissionDeniedError),
    ):
        authz.require(world.member, Action.PROJECT_DELETE, project_id=world.project.id)

    line = caplog.text
    assert "Authorization denied" in line
    assert str(world.member.id) in line
    assert "project.delete" in line and "project-delete" in line
    assert "conditions_not_met" in line
    assert world.member.email not in line


def test_the_engine_in_the_service_is_the_shipped_one(authz: AuthorizationService) -> None:
    assert isinstance(authz.engine, PolicyEngine)
    assert len(authz.engine.registry) == 9
