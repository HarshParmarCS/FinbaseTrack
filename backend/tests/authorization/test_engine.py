"""The decision engine fails closed and follows the documented algorithm."""

import dataclasses
import uuid
from typing import Any

import pytest

from app.authorization.conditions import CONDITIONS
from app.authorization.context import AuthorizationContext, Subject, TaskChanges, TaskFacts
from app.authorization.decision import Decision, ReasonCode
from app.authorization.engine import PolicyEngine
from app.authorization.policies import (
    Action,
    ConditionCall,
    ConditionGroup,
    Effect,
    Operator,
    Policy,
)
from app.authorization.registry import PolicyRegistry
from tests.authorization.helpers import (
    MEMBER,
    OWNER,
    PROJECT,
    make_context,
    make_task,
    shipped_engine,
)


def call(name: str, **params: Any) -> ConditionCall:
    return ConditionCall(name=name, func=CONDITIONS[name].func, params=params)


def policy(
    policy_id: str,
    action: Action,
    effect: Effect,
    *children: ConditionCall | ConditionGroup,
    operator: Operator = Operator.ALL,
) -> Policy:
    return Policy(policy_id, action, effect, ConditionGroup(operator, tuple(children)))


# ---- default deny ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action", ["project.nuke", "", "PROJECT.VIEW", "project:view", "*", "task"]
)
def test_unknown_actions_are_denied(action: str) -> None:
    decision = shipped_engine().evaluate(make_context(action, OWNER))

    assert decision.allowed is False
    assert decision.reason_code is ReasonCode.UNKNOWN_ACTION
    assert decision.policy_id is None


def test_a_known_action_without_a_policy_is_denied() -> None:
    registry = PolicyRegistry(
        [policy("project-view", Action.PROJECT_VIEW, Effect.ALLOW, call("is_project_member"))]
    )

    decision = PolicyEngine(registry).evaluate(make_context(Action.TASK_CREATE, MEMBER))

    assert decision.allowed is False
    assert decision.reason_code is ReasonCode.NO_POLICY


def test_an_empty_registry_denies_everything() -> None:
    engine = PolicyEngine(PolicyRegistry([]))

    for action in Action:
        assert engine.evaluate(make_context(action, OWNER)).allowed is False


def test_a_registry_with_only_deny_policies_never_allows() -> None:
    registry = PolicyRegistry(
        [policy("never", Action.PROJECT_VIEW, Effect.DENY, call("is_project_owner"))]
    )

    decision = PolicyEngine(registry).evaluate(make_context(Action.PROJECT_VIEW, MEMBER))

    assert decision.allowed is False
    assert decision.reason_code is ReasonCode.NO_POLICY


def test_an_inactive_subject_is_denied_before_any_policy_runs() -> None:
    decision = shipped_engine().evaluate(make_context(Action.PROJECT_VIEW, OWNER, active=False))

    assert decision.allowed is False
    assert decision.reason_code is ReasonCode.SUBJECT_INACTIVE


# ---- fail closed -----------------------------------------------------------------------------


def test_a_condition_that_raises_denies_instead_of_propagating() -> None:
    def explode(ctx: AuthorizationContext) -> bool:
        raise RuntimeError("database exploded")

    boom = ConditionCall(name="boom", func=explode, params={})
    registry = PolicyRegistry([policy("boom-policy", Action.PROJECT_VIEW, Effect.ALLOW, boom)])

    decision = PolicyEngine(registry).evaluate(make_context(Action.PROJECT_VIEW, MEMBER))

    assert decision.allowed is False
    assert decision.reason_code is ReasonCode.EVALUATION_ERROR


@pytest.mark.parametrize("truthy_but_not_true", [1, "yes", [1], object(), None])
def test_only_an_explicit_true_counts_as_a_passing_condition(truthy_but_not_true: object) -> None:
    sloppy = ConditionCall(name="sloppy", func=lambda ctx: truthy_but_not_true, params={})  # type: ignore[arg-type,return-value]
    registry = PolicyRegistry([policy("sloppy", Action.PROJECT_VIEW, Effect.ALLOW, sloppy)])

    decision = PolicyEngine(registry).evaluate(make_context(Action.PROJECT_VIEW, MEMBER))

    assert decision.allowed is False


def test_a_failure_in_one_policy_does_not_allow_via_another_action() -> None:
    def explode(ctx: AuthorizationContext) -> bool:
        raise ValueError("bad data")

    registry = PolicyRegistry(
        [
            policy("ok", Action.PROJECT_UPDATE, Effect.ALLOW, call("is_project_owner")),
            policy("bad", Action.PROJECT_VIEW, Effect.ALLOW, ConditionCall("x", explode, {})),
        ]
    )
    engine = PolicyEngine(registry)

    assert engine.evaluate(make_context(Action.PROJECT_VIEW, OWNER)).allowed is False
    assert engine.evaluate(make_context(Action.PROJECT_UPDATE, OWNER)).allowed is True


def test_the_engine_never_raises_for_odd_contexts() -> None:
    engine = shipped_engine()
    odd = AuthorizationContext(subject=Subject(id=uuid.uuid4()), action=str(Action.TASK_UPDATE))

    assert engine.evaluate(odd).allowed is False  # nothing loaded: no project, no task


# ---- explicit deny and operators ------------------------------------------------------------


def test_an_explicit_deny_policy_beats_an_allow_policy() -> None:
    registry = PolicyRegistry(
        [
            policy("allow-members", Action.PROJECT_VIEW, Effect.ALLOW, call("is_project_member")),
            policy("block-owner", Action.PROJECT_VIEW, Effect.DENY, call("is_project_owner")),
        ]
    )
    engine = PolicyEngine(registry)

    owner = engine.evaluate(make_context(Action.PROJECT_VIEW, OWNER))
    member = engine.evaluate(make_context(Action.PROJECT_VIEW, MEMBER))

    assert owner.allowed is False
    assert owner.reason_code is ReasonCode.EXPLICIT_DENY
    assert owner.policy_id == "block-owner"
    assert member.allowed is True


def test_a_deny_policy_that_does_not_match_does_not_block() -> None:
    registry = PolicyRegistry(
        [
            policy("allow", Action.PROJECT_VIEW, Effect.ALLOW, call("is_project_member")),
            policy("deny", Action.PROJECT_VIEW, Effect.DENY, call("is_project_owner")),
        ]
    )

    assert PolicyEngine(registry).evaluate(make_context(Action.PROJECT_VIEW, MEMBER)).allowed


def test_the_any_operator_needs_only_one_true_condition() -> None:
    registry = PolicyRegistry(
        [
            policy(
                "either",
                Action.PROJECT_VIEW,
                Effect.ALLOW,
                call("is_project_owner"),
                call("is_project_member"),
                operator=Operator.ANY,
            )
        ]
    )
    engine = PolicyEngine(registry)

    assert engine.evaluate(make_context(Action.PROJECT_VIEW, MEMBER)).allowed is True
    denied = engine.evaluate(make_context(Action.PROJECT_VIEW, MEMBER, member=False))
    assert denied.allowed is False
    assert set(denied.failed_conditions) == {"is_project_owner", "is_project_member"}


def test_the_all_operator_needs_every_condition_and_reports_the_first_failure() -> None:
    registry = PolicyRegistry(
        [
            policy(
                "both",
                Action.PROJECT_VIEW,
                Effect.ALLOW,
                call("is_project_member"),
                call("is_project_owner"),
            )
        ]
    )

    decision = PolicyEngine(registry).evaluate(make_context(Action.PROJECT_VIEW, MEMBER))

    assert decision.allowed is False
    assert decision.failed_conditions == ("is_project_owner",)


def test_nested_groups_are_evaluated() -> None:
    nested = ConditionGroup(Operator.ANY, (call("is_task_creator"), call("is_task_assignee")))
    registry = PolicyRegistry(
        [policy("nested", Action.TASK_UPDATE, Effect.ALLOW, call("is_project_member"), nested)]
    )
    engine = PolicyEngine(registry)
    task = make_task(creator_id=MEMBER, assignee_id=None)

    assert engine.evaluate(make_context(Action.TASK_UPDATE, MEMBER, task=task)).allowed is True
    assert engine.evaluate(make_context(Action.TASK_UPDATE, OWNER, task=task)).allowed is False


# ---- decisions and contexts are plain, immutable data ------------------------------------------


def test_decisions_are_typed_frozen_data() -> None:
    decision = shipped_engine().evaluate(make_context(Action.PROJECT_VIEW, MEMBER))

    assert isinstance(decision, Decision)
    assert {f.name for f in dataclasses.fields(decision)} == {
        "allowed",
        "action",
        "policy_id",
        "reason_code",
        "failed_conditions",
    }
    assert decision.action == "project.view"
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.allowed = False  # type: ignore[misc]


def test_a_denial_cannot_carry_the_allowed_reason_code() -> None:
    with pytest.raises(ValueError, match="ALLOWED"):
        Decision.deny("project.view", ReasonCode.ALLOWED)


def test_contexts_are_immutable() -> None:
    ctx = make_context(Action.PROJECT_VIEW, MEMBER)

    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.is_project_member = False  # type: ignore[misc]


def test_action_accepts_the_enum_or_its_string_value() -> None:
    engine = shipped_engine()

    by_enum = engine.evaluate(make_context(Action.PROJECT_VIEW, MEMBER))
    by_string = engine.evaluate(make_context("project.view", MEMBER))

    assert by_enum == by_string


def test_every_mandatory_action_has_a_policy_in_the_shipped_configuration() -> None:
    registry = shipped_engine().registry

    assert registry.actions() == {action.value for action in Action}
    assert len(registry) == 9
    assert registry.missing_actions() == frozenset()


# ---- TaskChanges: the "resulting state" the policies judge -----------------------------------


def test_task_changes_apply_only_the_fields_that_were_given() -> None:
    base = make_task()

    result = TaskChanges(title="New title").apply(base)

    assert result.title == "New title"
    assert result.description == base.description
    assert result.assignee_id == base.assignee_id


def test_task_changes_can_explicitly_clear_a_field() -> None:
    base = make_task()

    result = TaskChanges(assignee_id=None, due_date=None).apply(base)

    assert result.assignee_id is None
    assert result.due_date is None


def test_task_changes_do_not_modify_the_original() -> None:
    base = make_task()

    TaskChanges(status="completed").apply(base)

    assert base.status == "todo"
    assert isinstance(base, TaskFacts)


def test_context_resulting_task_prefers_the_proposed_state() -> None:
    stored = make_task(status="todo")
    proposed = make_task(status="completed")

    assert (
        make_context(Action.TASK_UPDATE, task=stored, proposed=proposed).resulting_task is proposed
    )
    assert make_context(Action.TASK_UPDATE, task=stored).resulting_task is stored
    assert PROJECT.owner_id == OWNER
