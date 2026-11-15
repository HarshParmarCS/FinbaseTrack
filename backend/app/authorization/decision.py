"""The result of an authorization check. Plain data: no HTTP, no framework."""

from dataclasses import dataclass
from enum import StrEnum


class ReasonCode(StrEnum):
    ALLOWED = "allowed"
    EXPLICIT_DENY = "explicit_deny"  # a deny policy matched
    CONDITIONS_NOT_MET = "conditions_not_met"  # no allow policy matched
    NO_POLICY = "no_policy"  # known action, but no policy registered (default deny)
    UNKNOWN_ACTION = "unknown_action"  # not an action this system defines (default deny)
    SUBJECT_INACTIVE = "subject_inactive"
    RESOURCE_NOT_FOUND = "resource_not_found"
    EVALUATION_ERROR = "evaluation_error"  # something failed while evaluating: fail closed


@dataclass(frozen=True, slots=True)
class Decision:
    allowed: bool
    action: str
    policy_id: str | None
    reason_code: ReasonCode
    # Names of the conditions that were not satisfied (empty when allowed).
    failed_conditions: tuple[str, ...] = ()

    @classmethod
    def allow(cls, action: str, policy_id: str) -> "Decision":
        return cls(True, action, policy_id, ReasonCode.ALLOWED)

    @classmethod
    def deny(
        cls,
        action: str,
        reason_code: ReasonCode,
        *,
        policy_id: str | None = None,
        failed_conditions: tuple[str, ...] = (),
    ) -> "Decision":
        if reason_code is ReasonCode.ALLOWED:
            raise ValueError("A denial cannot have the reason code ALLOWED")
        return cls(False, action, policy_id, reason_code, failed_conditions)
