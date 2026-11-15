"""The policy enforcement point (PEP) used by the service layer.

Services call ``require(...)`` BEFORE mutating anything. This class contains no policy logic:
it gathers facts (PIP), asks the engine (PDP) and converts a denial into a domain error that
the central exception handlers turn into 403 or 404. It does not import FastAPI.
"""

import logging
import uuid
from dataclasses import replace

from app.authorization.context import (
    AuthorizationContext,
    ProjectFacts,
    TaskChanges,
)
from app.authorization.decision import Decision, ReasonCode
from app.authorization.engine import PolicyEngine
from app.authorization.information import PolicyInformationPoint
from app.authorization.policies import Action
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.models import User
from app.schemas.common import ErrorDetail

logger = logging.getLogger(__name__)

DEFAULT_DENIAL_MESSAGE = "You are not allowed to perform this action."
COMPLETED = "completed"
# Evaluated against already-loaded project facts to fill `allowed_actions`.
PROJECT_LEVEL_ACTIONS = (
    Action.PROJECT_UPDATE,
    Action.PROJECT_DELETE,
    Action.PROJECT_MEMBER_MANAGE,
    Action.TASK_CREATE,
)


class AuthorizationService:
    def __init__(self, engine: PolicyEngine, information: PolicyInformationPoint) -> None:
        self.engine = engine
        self.information = information

    # ---- non-raising ------------------------------------------------------------------------

    def evaluate(
        self,
        user: User,
        action: Action | str,
        *,
        project_id: uuid.UUID | None = None,
        task_id: uuid.UUID | None = None,
        changes: TaskChanges | None = None,
    ) -> Decision:
        """The decision for an action, without raising. Used for ``allowed_actions``."""
        try:
            ctx = self.information.build_context(
                user, str(action), project_id=project_id, task_id=task_id, changes=changes
            )
        except NotFoundError:
            return Decision.deny(str(action), ReasonCode.RESOURCE_NOT_FOUND)
        return self.engine.evaluate(ctx)

    def allowed_project_actions(
        self, user: User, project: ProjectFacts, *, is_member: bool
    ) -> frozenset[Action]:
        """Project-level actions the user may perform, from facts the caller already loaded.

        Runs the same engine and policies but issues no queries, so a list of N projects needs
        no extra round trips. Callers pass facts read from the database in the same request.
        """
        subject = self.information.subject(user)
        return frozenset(
            action
            for action in PROJECT_LEVEL_ACTIONS
            if self.engine.evaluate(
                AuthorizationContext(
                    subject=subject,
                    action=action.value,
                    project=project,
                    is_project_member=is_member,
                )
            ).allowed
        )

    # ---- enforcing --------------------------------------------------------------------------

    def require(
        self,
        user: User,
        action: Action | str,
        *,
        project_id: uuid.UUID | None = None,
        task_id: uuid.UUID | None = None,
        changes: TaskChanges | None = None,
    ) -> AuthorizationContext:
        """Allow the action or raise. Returns the facts the decision was based on.

        Raises NotFoundError when the resource does not exist OR the user is not a member of its
        project (identical, so existence is never revealed), and PermissionDeniedError when a
        member is denied by a policy.
        """
        ctx = self.information.build_context(
            user, str(action), project_id=project_id, task_id=task_id, changes=changes
        )
        return self._enforce(ctx)

    def require_task_create(
        self, user: User, project_id: uuid.UUID, changes: TaskChanges
    ) -> AuthorizationContext:
        """task.create, plus task.complete when the new task would already be completed."""
        ctx = self.require(user, Action.TASK_CREATE, project_id=project_id, changes=changes)
        return self._also_require_completion(ctx)

    def require_task_update(
        self, user: User, task_id: uuid.UUID, changes: TaskChanges
    ) -> AuthorizationContext:
        """task.update, plus task.complete when the RESULTING status is completed."""
        ctx = self.require(user, Action.TASK_UPDATE, task_id=task_id, changes=changes)
        return self._also_require_completion(ctx)

    # ---- internals --------------------------------------------------------------------------

    def _also_require_completion(self, ctx: AuthorizationContext) -> AuthorizationContext:
        resulting = ctx.resulting_task
        if resulting is not None and str(resulting.status) == COMPLETED:
            # Same facts, different action: both decisions describe the same moment.
            self._enforce(replace(ctx, action=Action.TASK_COMPLETE.value))
        return ctx

    def _enforce(self, ctx: AuthorizationContext) -> AuthorizationContext:
        decision = self.engine.evaluate(ctx)
        if decision.allowed:
            logger.debug(
                "Authorization allowed user_id=%s action=%s policy=%s",
                ctx.subject.id,
                decision.action,
                decision.policy_id,
            )
            return ctx

        logger.info(
            "Authorization denied user_id=%s action=%s policy=%s reason=%s failed=%s",
            ctx.subject.id,
            decision.action,
            decision.policy_id,
            decision.reason_code.value,
            ",".join(decision.failed_conditions) or "-",
        )
        if ctx.project is not None and not ctx.is_project_member:
            raise NotFoundError()  # a non-member must not learn that the project/task exists
        raise self._denial_error(decision)

    def _denial_error(self, decision: Decision) -> PermissionDeniedError:
        policy = self.engine.registry.get(decision.policy_id) if decision.policy_id else None
        message = (policy.description if policy else "") or DEFAULT_DENIAL_MESSAGE
        return PermissionDeniedError(
            message,
            details=[ErrorDetail(policy_id=decision.policy_id, message=message)],
        )
