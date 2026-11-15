"""Every mandatory policy: a positive, a negative and boundary tests.

These run the real policies.json through the real engine on in-memory contexts, so they test
the policies exactly as shipped.
"""

from datetime import date

import pytest

from app.authorization.decision import Decision, ReasonCode
from app.authorization.engine import PolicyEngine
from app.authorization.policies import Action
from tests.authorization.helpers import (
    ASSIGNEE,
    MEMBER,
    OTHER_PROJECT_ID,
    OUTSIDER,
    OWNER,
    PROJECT,
    make_context,
    make_task,
    shipped_engine,
)


@pytest.fixture(scope="module")
def policy_engine() -> PolicyEngine:
    return shipped_engine()


def assert_allowed(decision: Decision, policy_id: str) -> None:
    assert decision.allowed is True
    assert decision.policy_id == policy_id
    assert decision.reason_code is ReasonCode.ALLOWED
    assert decision.failed_conditions == ()


def assert_denied(decision: Decision, policy_id: str | None, *failed: str) -> None:
    assert decision.allowed is False
    assert decision.policy_id == policy_id
    assert decision.reason_code is not ReasonCode.ALLOWED
    for name in failed:
        assert name in decision.failed_conditions


# ---- project.create -------------------------------------------------------------------------


def test_project_create_allows_any_authenticated_user(policy_engine: PolicyEngine) -> None:
    decision = policy_engine.evaluate(
        make_context(Action.PROJECT_CREATE, OUTSIDER, member=False, project=None)
    )

    assert_allowed(decision, "project-create")


def test_project_create_denies_an_inactive_user(policy_engine: PolicyEngine) -> None:
    decision = policy_engine.evaluate(
        make_context(Action.PROJECT_CREATE, OUTSIDER, project=None, active=False)
    )

    assert decision.allowed is False
    assert decision.reason_code is ReasonCode.SUBJECT_INACTIVE


def test_project_create_needs_no_project_and_no_membership(policy_engine: PolicyEngine) -> None:
    # Boundary: the very first project of a brand-new user, who is a member of nothing.
    ctx = make_context(Action.PROJECT_CREATE, MEMBER, member=False, project=None)

    assert policy_engine.evaluate(ctx).allowed is True


# ---- project.member.manage -------------------------------------------------------------------


def test_member_management_allows_the_owner(policy_engine: PolicyEngine) -> None:
    assert_allowed(
        policy_engine.evaluate(make_context(Action.PROJECT_MEMBER_MANAGE, OWNER)),
        "project-member-manage",
    )


def test_member_management_denies_a_member_who_is_not_the_owner(
    policy_engine: PolicyEngine,
) -> None:
    decision = policy_engine.evaluate(make_context(Action.PROJECT_MEMBER_MANAGE, MEMBER))

    assert_denied(decision, "project-member-manage", "is_project_owner")


def test_member_management_denies_an_owner_who_is_no_longer_a_member(
    policy_engine: PolicyEngine,
) -> None:
    decision = policy_engine.evaluate(
        make_context(Action.PROJECT_MEMBER_MANAGE, OWNER, member=False)
    )

    assert decision.allowed is False


def test_member_management_denies_without_a_project(policy_engine: PolicyEngine) -> None:
    ctx = make_context(Action.PROJECT_MEMBER_MANAGE, OWNER, project=None)

    assert policy_engine.evaluate(ctx).allowed is False


# ---- project.view -------------------------------------------------------------------------


def test_project_view_allows_a_current_member(policy_engine: PolicyEngine) -> None:
    decision = policy_engine.evaluate(make_context(Action.PROJECT_VIEW, MEMBER, member=True))

    assert_allowed(decision, "project-view")


def test_project_view_denies_a_non_member(policy_engine: PolicyEngine) -> None:
    decision = policy_engine.evaluate(make_context(Action.PROJECT_VIEW, OUTSIDER, member=False))

    assert_denied(decision, "project-view", "is_project_member")
    assert decision.reason_code is ReasonCode.CONDITIONS_NOT_MET


def test_project_view_denies_the_owner_once_their_membership_is_gone(
    policy_engine: PolicyEngine,
) -> None:
    decision = policy_engine.evaluate(make_context(Action.PROJECT_VIEW, OWNER, member=False))

    assert_denied(decision, "project-view", "is_project_member")


def test_project_view_denies_when_there_is_no_project_in_the_context(
    policy_engine: PolicyEngine,
) -> None:
    decision = policy_engine.evaluate(
        make_context(Action.PROJECT_VIEW, MEMBER, member=True, project=None)
    )

    assert decision.allowed is False


def test_project_view_denies_an_inactive_user_even_if_a_member(policy_engine: PolicyEngine) -> None:
    decision = policy_engine.evaluate(make_context(Action.PROJECT_VIEW, MEMBER, active=False))

    assert decision.allowed is False
    assert decision.reason_code is ReasonCode.SUBJECT_INACTIVE


# ---- project.update and project.delete (identical rule, same three tests each) ----------------

OWNER_ONLY = [(Action.PROJECT_UPDATE, "project-update"), (Action.PROJECT_DELETE, "project-delete")]


@pytest.mark.parametrize(("action", "policy_id"), OWNER_ONLY)
def test_project_owner_actions_allow_the_owner(
    policy_engine: PolicyEngine, action: Action, policy_id: str
) -> None:
    assert_allowed(policy_engine.evaluate(make_context(action, OWNER)), policy_id)


@pytest.mark.parametrize(("action", "policy_id"), OWNER_ONLY)
def test_project_owner_actions_deny_a_member_who_is_not_the_owner(
    policy_engine: PolicyEngine, action: Action, policy_id: str
) -> None:
    decision = policy_engine.evaluate(make_context(action, MEMBER, member=True))

    assert_denied(decision, policy_id, "is_project_owner")


@pytest.mark.parametrize(("action", "policy_id"), OWNER_ONLY)
def test_project_owner_actions_deny_an_owner_who_is_no_longer_a_member(
    policy_engine: PolicyEngine, action: Action, policy_id: str
) -> None:
    decision = policy_engine.evaluate(make_context(action, OWNER, member=False))

    assert_denied(decision, policy_id, "is_project_owner")


@pytest.mark.parametrize(("action", "policy_id"), OWNER_ONLY)
def test_project_owner_actions_deny_the_owner_of_a_different_project(
    policy_engine: PolicyEngine, action: Action, policy_id: str
) -> None:
    other_project = PROJECT.__class__(id=OTHER_PROJECT_ID, owner_id=MEMBER)

    decision = policy_engine.evaluate(
        make_context(action, OWNER, project=other_project, member=True)
    )

    assert_denied(decision, policy_id, "is_project_owner")


@pytest.mark.parametrize(("action", "policy_id"), OWNER_ONLY)
def test_project_owner_actions_deny_without_a_project(
    policy_engine: PolicyEngine, action: Action, policy_id: str
) -> None:
    assert policy_engine.evaluate(make_context(action, OWNER, project=None)).allowed is False


# ---- task.create ---------------------------------------------------------------------------


def test_task_create_allows_a_member(policy_engine: PolicyEngine) -> None:
    assert_allowed(policy_engine.evaluate(make_context(Action.TASK_CREATE, MEMBER)), "task-create")


def test_task_create_denies_a_non_member(policy_engine: PolicyEngine) -> None:
    decision = policy_engine.evaluate(make_context(Action.TASK_CREATE, OUTSIDER, member=False))

    assert_denied(decision, "task-create", "is_project_member")


def test_task_create_denies_a_removed_member(policy_engine: PolicyEngine) -> None:
    # Someone who used to create tasks here, removed since: no leftover rights.
    decision = policy_engine.evaluate(make_context(Action.TASK_CREATE, MEMBER, member=False))

    assert decision.allowed is False


def test_task_create_denies_without_a_project(policy_engine: PolicyEngine) -> None:
    assert (
        policy_engine.evaluate(make_context(Action.TASK_CREATE, MEMBER, project=None)).allowed
        is False
    )


def test_task_create_allows_the_owner_because_the_owner_is_a_member(
    policy_engine: PolicyEngine,
) -> None:
    assert policy_engine.evaluate(make_context(Action.TASK_CREATE, OWNER)).allowed is True


# ---- task.update ---------------------------------------------------------------------------


def test_task_update_allows_the_creator(policy_engine: PolicyEngine) -> None:
    task = make_task(creator_id=MEMBER, assignee_id=ASSIGNEE)

    assert_allowed(
        policy_engine.evaluate(make_context(Action.TASK_UPDATE, MEMBER, task=task)), "task-update"
    )


def test_task_update_allows_the_assignee(policy_engine: PolicyEngine) -> None:
    task = make_task(creator_id=MEMBER, assignee_id=ASSIGNEE)

    assert_allowed(
        policy_engine.evaluate(make_context(Action.TASK_UPDATE, ASSIGNEE, task=task)), "task-update"
    )


def test_task_update_denies_a_member_who_is_neither_creator_nor_assignee(
    policy_engine: PolicyEngine,
) -> None:
    task = make_task(creator_id=MEMBER, assignee_id=ASSIGNEE)
    bystander = OUTSIDER

    decision = policy_engine.evaluate(
        make_context(Action.TASK_UPDATE, bystander, task=task, member=True)
    )

    assert_denied(decision, "task-update", "is_task_creator", "is_task_assignee")


def test_task_update_denies_the_project_owner_when_not_creator_or_assignee(
    policy_engine: PolicyEngine,
) -> None:
    # Ownership grants no update right: only creator or assignee (assumption A7).
    task = make_task(creator_id=MEMBER, assignee_id=ASSIGNEE)

    decision = policy_engine.evaluate(
        make_context(Action.TASK_UPDATE, OWNER, task=task, member=True)
    )

    assert decision.allowed is False


def test_task_update_denies_a_creator_who_was_removed_from_the_project(
    policy_engine: PolicyEngine,
) -> None:
    task = make_task(creator_id=MEMBER)

    decision = policy_engine.evaluate(
        make_context(Action.TASK_UPDATE, MEMBER, task=task, member=False)
    )

    assert_denied(decision, "task-update", "is_project_member")


def test_task_update_denies_an_assignee_who_is_not_a_project_member(
    policy_engine: PolicyEngine,
) -> None:
    # "Task assignee not belonging to the project": being named as assignee is not enough.
    task = make_task(creator_id=MEMBER, assignee_id=ASSIGNEE)

    decision = policy_engine.evaluate(
        make_context(Action.TASK_UPDATE, ASSIGNEE, task=task, member=False, assignee_member=False)
    )

    assert_denied(decision, "task-update", "is_project_member")


def test_task_update_allows_a_user_who_is_both_creator_and_assignee(
    policy_engine: PolicyEngine,
) -> None:
    task = make_task(creator_id=MEMBER, assignee_id=MEMBER)

    assert (
        policy_engine.evaluate(make_context(Action.TASK_UPDATE, MEMBER, task=task)).allowed is True
    )


def test_task_update_denies_an_unassigned_task_to_a_non_creator(
    policy_engine: PolicyEngine,
) -> None:
    task = make_task(creator_id=MEMBER, assignee_id=None)

    assert (
        policy_engine.evaluate(make_context(Action.TASK_UPDATE, ASSIGNEE, task=task)).allowed
        is False
    )


def test_task_update_denies_when_there_is_no_task(policy_engine: PolicyEngine) -> None:
    assert (
        policy_engine.evaluate(make_context(Action.TASK_UPDATE, MEMBER, task=None)).allowed is False
    )


# ---- task.delete ---------------------------------------------------------------------------


def test_task_delete_allows_the_owner_when_the_task_is_todo(policy_engine: PolicyEngine) -> None:
    task = make_task(status="todo")

    assert_allowed(
        policy_engine.evaluate(make_context(Action.TASK_DELETE, OWNER, task=task)), "task-delete"
    )


def test_task_delete_denies_a_member_who_is_not_the_owner_even_for_a_todo_task(
    policy_engine: PolicyEngine,
) -> None:
    task = make_task(status="todo", creator_id=MEMBER)  # even the creator cannot delete

    decision = policy_engine.evaluate(make_context(Action.TASK_DELETE, MEMBER, task=task))

    assert_denied(decision, "task-delete", "is_project_owner")


def test_project_owner_cannot_delete_an_in_progress_task(policy_engine: PolicyEngine) -> None:
    task = make_task(status="in_progress")

    decision = policy_engine.evaluate(make_context(Action.TASK_DELETE, OWNER, task=task))

    assert_denied(decision, "task-delete", "task_status_is")
    assert decision.reason_code is ReasonCode.CONDITIONS_NOT_MET


def test_task_delete_denies_the_owner_for_a_completed_task(policy_engine: PolicyEngine) -> None:
    task = make_task(status="completed")

    assert (
        policy_engine.evaluate(make_context(Action.TASK_DELETE, OWNER, task=task)).allowed is False
    )


def test_task_delete_denies_an_owner_who_is_no_longer_a_member(policy_engine: PolicyEngine) -> None:
    task = make_task(status="todo")

    assert (
        policy_engine.evaluate(
            make_context(Action.TASK_DELETE, OWNER, task=task, member=False)
        ).allowed
        is False
    )


def test_task_delete_denies_when_there_is_no_task(policy_engine: PolicyEngine) -> None:
    assert (
        policy_engine.evaluate(make_context(Action.TASK_DELETE, OWNER, task=None)).allowed is False
    )


def test_task_delete_uses_the_stored_status_not_the_proposed_one(
    policy_engine: PolicyEngine,
) -> None:
    stored = make_task(status="in_progress")
    proposed = make_task(status="todo")

    ctx = make_context(Action.TASK_DELETE, OWNER, task=stored, proposed=proposed)

    assert policy_engine.evaluate(ctx).allowed is False


# ---- task.complete -------------------------------------------------------------------------


def test_task_complete_allows_an_assigned_task_with_all_information(
    policy_engine: PolicyEngine,
) -> None:
    task = make_task()

    assert_allowed(
        policy_engine.evaluate(make_context(Action.TASK_COMPLETE, MEMBER, task=task)),
        "task-complete",
    )


def test_task_complete_denies_a_task_without_an_assignee(policy_engine: PolicyEngine) -> None:
    task = make_task(assignee_id=None)

    decision = policy_engine.evaluate(
        make_context(Action.TASK_COMPLETE, MEMBER, task=task, assignee_member=False)
    )

    assert_denied(decision, "task-complete", "task_has_assignee")


@pytest.mark.parametrize(
    ("field", "empty_value"),
    [
        ("title", "   "),
        ("description", None),
        ("description", ""),
        ("description", "   \n\t "),  # whitespace only counts as missing
        ("priority", None),
        ("due_date", None),
    ],
)
def test_task_complete_denies_when_required_information_is_missing(
    policy_engine: PolicyEngine, field: str, empty_value: object
) -> None:
    task = make_task(**{field: empty_value})

    decision = policy_engine.evaluate(make_context(Action.TASK_COMPLETE, MEMBER, task=task))

    assert_denied(decision, "task-complete", "task_required_fields_complete")


def test_task_complete_denies_when_the_assignee_is_not_a_project_member(
    policy_engine: PolicyEngine,
) -> None:
    task = make_task(assignee_id=OUTSIDER)

    decision = policy_engine.evaluate(
        make_context(Action.TASK_COMPLETE, MEMBER, task=task, assignee_member=False)
    )

    assert_denied(decision, "task-complete", "task_has_assignee")


def test_task_complete_denies_a_requester_who_is_not_a_member(policy_engine: PolicyEngine) -> None:
    task = make_task()

    decision = policy_engine.evaluate(
        make_context(Action.TASK_COMPLETE, OUTSIDER, task=task, member=False)
    )

    assert_denied(decision, "task-complete", "is_project_member")


def test_task_complete_judges_the_resulting_state_not_the_stored_one(
    policy_engine: PolicyEngine,
) -> None:
    stored = make_task(description=None, due_date=None)  # incomplete today...
    proposed = make_task()  # ...but complete after the requested change

    ctx = make_context(Action.TASK_COMPLETE, MEMBER, task=stored, proposed=proposed)

    assert policy_engine.evaluate(ctx).allowed is True


def test_task_complete_denies_a_change_that_would_clear_required_information(
    policy_engine: PolicyEngine,
) -> None:
    stored = make_task(status="completed")  # complete today...
    proposed = make_task(status="completed", due_date=None)  # ...incomplete after the change

    ctx = make_context(Action.TASK_COMPLETE, MEMBER, task=stored, proposed=proposed)

    assert policy_engine.evaluate(ctx).allowed is False


def test_task_complete_works_for_a_new_task_that_does_not_exist_yet(
    policy_engine: PolicyEngine,
) -> None:
    new_task = make_task(id=None, due_date=date(2026, 12, 31))

    ctx = make_context(Action.TASK_COMPLETE, MEMBER, task=None, proposed=new_task)

    assert policy_engine.evaluate(ctx).allowed is True


def test_task_complete_denies_without_any_task(policy_engine: PolicyEngine) -> None:
    assert (
        policy_engine.evaluate(make_context(Action.TASK_COMPLETE, MEMBER, task=None)).allowed
        is False
    )
