"""The policy decision point (PDP): evaluates policies and returns a Decision.

Fails closed: every path that is not an explicit, successful allow ends in a denial, and the
engine itself never raises. It knows nothing about HTTP, FastAPI or the database.
"""

import logging

from app.authorization.context import AuthorizationContext
from app.authorization.decision import Decision, ReasonCode
from app.authorization.policies import Effect
from app.authorization.registry import PolicyRegistry

logger = logging.getLogger(__name__)


class PolicyEngine:
    def __init__(self, registry: PolicyRegistry) -> None:
        self.registry = registry

    def evaluate(self, ctx: AuthorizationContext) -> Decision:
        """Decide whether ``ctx.subject`` may perform ``ctx.action``. Never raises."""
        action = str(ctx.action)
        try:
            return self._evaluate(ctx, action)
        except Exception:
            # Deliberately broad: a bug or bad data while evaluating must mean "deny".
            logger.exception("Authorization evaluation failed; denying action=%s", action)
            return Decision.deny(action, ReasonCode.EVALUATION_ERROR)

    def _evaluate(self, ctx: AuthorizationContext, action: str) -> Decision:
        if not ctx.subject.is_active:
            return Decision.deny(action, ReasonCode.SUBJECT_INACTIVE)

        if not self.registry.is_known_action(action):
            return Decision.deny(action, ReasonCode.UNKNOWN_ACTION)

        policies = self.registry.policies_for(action)
        if not policies:
            return Decision.deny(action, ReasonCode.NO_POLICY)

        # 1. An explicit deny always wins.
        for policy in policies:
            if policy.effect is Effect.DENY and policy.evaluate(ctx).matched:
                return Decision.deny(action, ReasonCode.EXPLICIT_DENY, policy_id=policy.id)

        # 2. Any allow policy whose conditions all hold grants the action.
        first_failure: tuple[str, tuple[str, ...]] | None = None
        for policy in policies:
            if policy.effect is not Effect.ALLOW:
                continue
            result = policy.evaluate(ctx)
            if result.matched:
                return Decision.allow(action, policy.id)
            if first_failure is None:
                first_failure = (policy.id, result.failed)

        # 3. Default deny.
        if first_failure is None:
            return Decision.deny(action, ReasonCode.NO_POLICY)
        policy_id, failed = first_failure
        return Decision.deny(
            action,
            ReasonCode.CONDITIONS_NOT_MET,
            policy_id=policy_id,
            failed_conditions=failed,
        )
