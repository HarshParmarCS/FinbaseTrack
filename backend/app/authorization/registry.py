"""Maps action identifiers to the policies that handle them."""

from collections.abc import Iterable

from app.authorization.policies import REQUIRED_ACTIONS, Action, Policy, PolicyConfigError


class PolicyRegistry:
    def __init__(self, policies: Iterable[Policy]) -> None:
        self._by_action: dict[str, list[Policy]] = {}
        self._by_id: dict[str, Policy] = {}
        for policy in policies:
            if policy.id in self._by_id:
                raise PolicyConfigError(f"Duplicate policy id '{policy.id}'")
            self._by_id[policy.id] = policy
            self._by_action.setdefault(policy.action.value, []).append(policy)

    def policies_for(self, action: str) -> tuple[Policy, ...]:
        """Policies registered for an action identifier. Empty if there are none."""
        return tuple(self._by_action.get(action, ()))

    def get(self, policy_id: str) -> Policy | None:
        return self._by_id.get(policy_id)

    @staticmethod
    def is_known_action(action: str) -> bool:
        return action in {a.value for a in Action}

    def actions(self) -> frozenset[str]:
        return frozenset(self._by_action)

    def policy_ids(self) -> frozenset[str]:
        return frozenset(self._by_id)

    def missing_actions(self) -> frozenset[Action]:
        """Required actions that have no allow policy."""
        covered = {
            Action(action)
            for action, policies in self._by_action.items()
            if any(p.effect.value == "allow" for p in policies)
        }
        return REQUIRED_ACTIONS - covered

    def __len__(self) -> int:
        return len(self._by_id)
