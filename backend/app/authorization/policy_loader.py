"""Load and strictly validate ``policies.json`` (the policy administration point's input).

Validation is allow-list based: every key, name and value must be recognised, otherwise the
whole configuration is rejected with a PolicyConfigError and the application does not start.
The JSON is only ever parsed with ``json`` and mapped onto predefined classes and functions.
"""

import json
import re
from pathlib import Path
from typing import Any

from app.authorization.conditions import CONDITIONS
from app.authorization.policies import (
    Action,
    ConditionCall,
    ConditionGroup,
    Effect,
    Operator,
    Policy,
    PolicyConfigError,
)
from app.authorization.registry import PolicyRegistry

SUPPORTED_VERSION = 1
MAX_GROUP_DEPTH = 4
_POLICY_ID = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
_TOP_LEVEL_KEYS = {"version", "default_effect", "policies"}
_POLICY_KEYS = {"id", "action", "effect", "operator", "conditions", "description"}
_REQUIRED_POLICY_KEYS = {"id", "action", "effect", "conditions"}


def load_policy_registry(path: Path) -> PolicyRegistry:
    """Read, validate and compile the policy file. Raises PolicyConfigError if anything is off."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PolicyConfigError(f"Cannot read policy file '{path}': {exc.strerror}") from exc
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PolicyConfigError(
            f"Policy file is not valid JSON: {exc.msg} (line {exc.lineno})"
        ) from exc
    return parse_policy_document(document)


def parse_policy_document(document: object) -> PolicyRegistry:
    """Validate an already-parsed policy document and build the registry."""
    if not isinstance(document, dict):
        raise PolicyConfigError("Policy document must be a JSON object")
    _reject_unknown_keys(document, _TOP_LEVEL_KEYS, "policy document")

    if document.get("version") != SUPPORTED_VERSION:
        raise PolicyConfigError(f"Unsupported policy version; expected {SUPPORTED_VERSION}")
    if document.get("default_effect") != "deny":
        raise PolicyConfigError("'default_effect' must be \"deny\" (default-deny is mandatory)")

    raw_policies = document.get("policies")
    if not isinstance(raw_policies, list) or not raw_policies:
        raise PolicyConfigError("'policies' must be a non-empty list")

    policies = [_parse_policy(raw, index) for index, raw in enumerate(raw_policies)]
    registry = PolicyRegistry(policies)  # rejects duplicate ids

    missing = registry.missing_actions()
    if missing:
        names = ", ".join(sorted(action.value for action in missing))
        raise PolicyConfigError(f"Missing policy definition for action(s): {names}")
    return registry


def _reject_unknown_keys(mapping: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = set(mapping) - allowed
    if unknown:
        raise PolicyConfigError(f"Unknown key(s) {sorted(unknown)} in {where}")


def _parse_policy(raw: object, index: int) -> Policy:
    where = f"policy #{index + 1}"
    if not isinstance(raw, dict):
        raise PolicyConfigError(f"{where} must be an object")
    _reject_unknown_keys(raw, _POLICY_KEYS, where)
    missing = _REQUIRED_POLICY_KEYS - set(raw)
    if missing:
        raise PolicyConfigError(f"{where} is missing key(s) {sorted(missing)}")

    policy_id = raw["id"]
    if not isinstance(policy_id, str) or not _POLICY_ID.match(policy_id):
        raise PolicyConfigError(f"{where}: 'id' must be lowercase words separated by hyphens")
    where = f"policy '{policy_id}'"

    try:
        action = Action(raw["action"])
    except ValueError as exc:
        raise PolicyConfigError(f"{where}: unknown action {raw['action']!r}") from exc
    try:
        effect = Effect(raw["effect"])
    except ValueError as exc:
        raise PolicyConfigError(f"{where}: unsupported effect {raw['effect']!r}") from exc

    description = raw.get("description", "")
    if not isinstance(description, str):
        raise PolicyConfigError(f"{where}: 'description' must be a string")

    root = _parse_group(
        {"operator": raw.get("operator", "all"), "conditions": raw["conditions"]}, where, depth=0
    )
    return Policy(id=policy_id, action=action, effect=effect, root=root, description=description)


def _parse_group(node: dict[str, Any], where: str, depth: int) -> ConditionGroup:
    if depth > MAX_GROUP_DEPTH:
        raise PolicyConfigError(f"{where}: condition groups are nested too deeply")
    try:
        operator = Operator(node["operator"])
    except ValueError as exc:
        raise PolicyConfigError(f"{where}: unsupported operator {node['operator']!r}") from exc

    conditions = node["conditions"]
    if not isinstance(conditions, list) or not conditions:
        raise PolicyConfigError(f"{where}: 'conditions' must be a non-empty list")
    children = tuple(_parse_node(child, where, depth) for child in conditions)
    return ConditionGroup(operator=operator, children=children)


def _parse_node(node: object, where: str, depth: int) -> ConditionGroup | ConditionCall:
    if isinstance(node, str):
        return _build_call(node, {}, where)
    if not isinstance(node, dict):
        raise PolicyConfigError(f"{where}: a condition must be a name or an object")

    if "operator" in node or "conditions" in node:
        if "name" in node:
            raise PolicyConfigError(f"{where}: a condition cannot be both a group and a call")
        _reject_unknown_keys(node, {"operator", "conditions"}, f"{where} condition group")
        if "operator" not in node or "conditions" not in node:
            raise PolicyConfigError(f"{where}: a group needs both 'operator' and 'conditions'")
        return _parse_group(node, where, depth + 1)

    if "name" not in node:
        raise PolicyConfigError(f"{where}: a condition object needs a 'name'")
    params = {key: value for key, value in node.items() if key != "name"}
    return _build_call(node["name"], params, where)


def _build_call(name: object, params: dict[str, Any], where: str) -> ConditionCall:
    # Names are looked up in a fixed dictionary; nothing in the file is ever executed.
    if not isinstance(name, str) or name not in CONDITIONS:
        raise PolicyConfigError(f"{where}: unknown condition {str(name)[:60]!r}")
    spec = CONDITIONS[name]
    try:
        validated = spec.validate_params(params)
    except ValueError as exc:
        raise PolicyConfigError(f"{where}: {exc}") from exc
    return ConditionCall(name=name, func=spec.func, params=validated)
