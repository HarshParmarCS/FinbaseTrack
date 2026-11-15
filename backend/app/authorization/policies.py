"""Policy definitions and their evaluation.

A policy is data: an action, an effect and a tree of conditions. Evaluating it runs only the
registered condition functions it references. There is no expression language and no code
execution.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.authorization.conditions import ConditionFunc
from app.authorization.context import AuthorizationContext


class PolicyConfigError(Exception):
    """The policy configuration is invalid. The application must not start with it."""


class Action(StrEnum):
    """Every action the authorization system knows. Anything else is denied."""

    PROJECT_CREATE = "project.create"
    PROJECT_VIEW = "project.view"
    PROJECT_UPDATE = "project.update"
    PROJECT_DELETE = "project.delete"
    PROJECT_MEMBER_MANAGE = "project.member.manage"
    TASK_CREATE = "task.create"
    TASK_UPDATE = "task.update"
    TASK_DELETE = "task.delete"
    TASK_COMPLETE = "task.complete"


# Every one of these needs an allow policy, or the configuration is rejected.
REQUIRED_ACTIONS: frozenset[Action] = frozenset(Action)


class Effect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class Operator(StrEnum):
    ALL = "all"
    ANY = "any"


@dataclass(frozen=True, slots=True)
class Evaluation:
    matched: bool
    # Names of conditions that were false and caused the mismatch (for explanations).
    failed: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ConditionCall:
    """A leaf: one registered condition with validated parameters."""

    name: str
    func: ConditionFunc
    params: Mapping[str, Any]

    def evaluate(self, ctx: AuthorizationContext) -> Evaluation:
        # Only an explicit True counts. Anything else (None, 1, "yes") is false: fail closed.
        if self.func(ctx, **self.params) is True:
            return Evaluation(True)
        return Evaluation(False, (self.name,))


@dataclass(frozen=True, slots=True)
class ConditionGroup:
    """A branch: ``all`` (AND) or ``any`` (OR) over child nodes."""

    operator: Operator
    children: tuple["ConditionGroup | ConditionCall", ...]

    def evaluate(self, ctx: AuthorizationContext) -> Evaluation:
        if self.operator is Operator.ALL:
            for child in self.children:
                result = child.evaluate(ctx)
                if not result.matched:
                    return result  # report the first condition that failed
            return Evaluation(True)

        failed: list[str] = []
        for child in self.children:
            result = child.evaluate(ctx)
            if result.matched:
                return Evaluation(True)
            failed.extend(result.failed)
        return Evaluation(False, tuple(failed))


@dataclass(frozen=True, slots=True)
class Policy:
    id: str
    action: Action
    effect: Effect
    root: ConditionGroup
    description: str = ""

    def evaluate(self, ctx: AuthorizationContext) -> Evaluation:
        return self.root.evaluate(ctx)
