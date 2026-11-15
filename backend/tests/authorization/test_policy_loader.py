"""The policy file is validated strictly; anything unrecognised aborts startup."""

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app.authorization.conditions import CONDITIONS, REQUIRED_FIELD_NAMES
from app.authorization.policies import Action, PolicyConfigError
from app.authorization.policy_loader import (
    MAX_GROUP_DEPTH,
    load_policy_registry,
    parse_policy_document,
)
from app.core.config import DEFAULT_POLICY_FILE
from tests.authorization.helpers import shipped_document

Mutator = Callable[[dict[str, Any]], Any]


def policy_named(document: dict[str, Any], policy_id: str) -> dict[str, Any]:
    return next(p for p in document["policies"] if p["id"] == policy_id)


# ---- the shipped file ----------------------------------------------------------------------


def test_the_shipped_policy_file_is_valid_and_covers_every_action() -> None:
    registry = load_policy_registry(DEFAULT_POLICY_FILE)

    assert registry.actions() == {
        "project.create",
        "project.member.manage",
        "project.view",
        "project.update",
        "project.delete",
        "task.create",
        "task.update",
        "task.delete",
        "task.complete",
    }
    assert registry.policy_ids() == {
        "project-create",
        "project-member-manage",
        "project-view",
        "project-update",
        "project-delete",
        "task-create",
        "task-update",
        "task-delete",
        "task-complete",
    }


def test_every_shipped_policy_states_action_id_effect_and_conditions() -> None:
    for policy in shipped_document()["policies"]:
        assert {"id", "action", "effect", "operator", "conditions"} <= set(policy)
        assert policy["effect"] == "allow"
        assert policy["conditions"]


def test_the_required_completion_fields_are_the_documented_ones() -> None:
    complete = policy_named(shipped_document(), "task-complete")
    fields = next(
        c["fields"] for c in complete["conditions"] if isinstance(c, dict) and "fields" in c
    )

    assert set(fields) == {"title", "description", "priority", "due_date", "assignee"}
    assert set(fields) == REQUIRED_FIELD_NAMES


def test_default_effect_in_the_shipped_file_is_deny() -> None:
    assert shipped_document()["default_effect"] == "deny"


# ---- invalid documents -----------------------------------------------------------------------


def remove_policy(policy_id: str) -> Mutator:
    def mutate(doc: dict[str, Any]) -> None:
        doc["policies"] = [p for p in doc["policies"] if p["id"] != policy_id]

    return mutate


def set_policy_field(policy_id: str, key: str, value: Any) -> Mutator:
    def mutate(doc: dict[str, Any]) -> None:
        policy_named(doc, policy_id)[key] = value

    return mutate


def delete_policy_field(policy_id: str, key: str) -> Mutator:
    def mutate(doc: dict[str, Any]) -> None:
        del policy_named(doc, policy_id)[key]

    return mutate


def set_conditions(policy_id: str, conditions: Any) -> Mutator:
    return set_policy_field(policy_id, "conditions", conditions)


def nested_groups(depth: int) -> Any:
    node: Any = "is_project_member"
    for _ in range(depth):
        node = {"operator": "all", "conditions": [node]}
    return node


INVALID_DOCUMENTS: list[tuple[str, Mutator, str]] = [
    ("unknown top-level key", lambda d: d.update(extra=1), "Unknown key"),
    ("wrong version", lambda d: d.update(version=2), "version"),
    ("missing version", lambda d: d.pop("version"), "version"),
    ("default effect allow", lambda d: d.update(default_effect="allow"), "default_effect"),
    ("default effect missing", lambda d: d.pop("default_effect"), "default_effect"),
    ("policies not a list", lambda d: d.update(policies={}), "non-empty list"),
    ("policies empty", lambda d: d.update(policies=[]), "non-empty list"),
    ("policy not an object", lambda d: d["policies"].append("project-view"), "must be an object"),
    ("unknown policy key", set_policy_field("project-view", "role", "admin"), "Unknown key"),
    ("missing conditions", delete_policy_field("project-view", "conditions"), "missing key"),
    ("missing action", delete_policy_field("project-view", "action"), "missing key"),
    ("bad policy id", set_policy_field("project-view", "id", "Project_View"), "'id'"),
    (
        "unknown action",
        set_policy_field("project-view", "action", "project.nuke"),
        "unknown action",
    ),
    (
        "action colon notation",
        set_policy_field("project-view", "action", "project:view"),
        "unknown action",
    ),
    (
        "unsupported effect",
        set_policy_field("project-view", "effect", "permit"),
        "unsupported effect",
    ),
    (
        "unsupported operator",
        set_policy_field("project-view", "operator", "xor"),
        "unsupported operator",
    ),
    ("operator not", set_policy_field("project-view", "operator", "not"), "unsupported operator"),
    (
        "operator wrong type",
        set_policy_field("project-view", "operator", ["all"]),
        "unsupported operator",
    ),
    ("bad description", set_policy_field("project-view", "description", 5), "description"),
    ("empty conditions", set_conditions("project-view", []), "non-empty list"),
    (
        "conditions not a list",
        set_conditions("project-view", "is_project_member"),
        "non-empty list",
    ),
    ("unknown condition", set_conditions("project-view", ["is_admin"]), "unknown condition"),
    (
        "role-style condition",
        set_conditions("project-view", ["has_role_manager"]),
        "unknown condition",
    ),
    (
        "code injection as condition name",
        set_conditions("project-view", ["__import__('os').system('echo pwned')"]),
        "unknown condition",
    ),
    (
        "condition name is an expression object",
        set_conditions("project-view", [{"name": "lambda ctx: True"}]),
        "unknown condition",
    ),
    (
        "condition not a string or object",
        set_conditions("project-view", [123]),
        "name or an object",
    ),
    (
        "condition object without name",
        set_conditions("project-view", [{"value": 1}]),
        "needs a 'name'",
    ),
    (
        "group with unsupported operator",
        set_conditions("project-view", [{"operator": "xor", "conditions": ["is_project_member"]}]),
        "unsupported operator",
    ),
    (
        "group with unknown key",
        set_conditions(
            "project-view",
            [{"operator": "any", "conditions": ["is_project_member"], "negate": True}],
        ),
        "Unknown key",
    ),
    (
        "group without conditions",
        set_conditions("project-view", [{"operator": "any"}]),
        "needs both",
    ),
    (
        "group that is also a call",
        set_conditions(
            "project-view",
            [{"name": "is_project_member", "operator": "any", "conditions": ["is_project_member"]}],
        ),
        "both a group and a call",
    ),
    (
        "empty nested group",
        set_conditions("project-view", [{"operator": "any", "conditions": []}]),
        "non-empty list",
    ),
    (
        "groups nested too deeply",
        set_conditions("project-view", [nested_groups(MAX_GROUP_DEPTH + 3)]),
        "too deeply",
    ),
    (
        "status value not a status",
        set_conditions(
            "task-delete", ["is_project_owner", {"name": "task_status_is", "value": "archived"}]
        ),
        "'value' must be one of",
    ),
    (
        "status value missing",
        set_conditions("task-delete", ["is_project_owner", {"name": "task_status_is"}]),
        "missing parameter",
    ),
    (
        "status condition used without parameters",
        set_conditions("task-delete", ["is_project_owner", "task_status_is"]),
        "missing parameter",
    ),
    (
        "unknown parameter",
        set_conditions("task-delete", [{"name": "task_status_is", "value": "todo", "extra": 1}]),
        "unknown parameter",
    ),
    (
        "parameter on a parameterless condition",
        set_conditions("project-view", [{"name": "is_project_member", "anything": 1}]),
        "unknown parameter",
    ),
    (
        "unknown required field",
        set_conditions(
            "task-complete",
            [{"name": "task_required_fields_complete", "fields": ["title", "salary"]}],
        ),
        "unknown field",
    ),
    (
        "required fields empty",
        set_conditions("task-complete", [{"name": "task_required_fields_complete", "fields": []}]),
        "non-empty list",
    ),
    (
        "required fields not a list",
        set_conditions(
            "task-complete", [{"name": "task_required_fields_complete", "fields": "title"}]
        ),
        "non-empty list",
    ),
    (
        "required fields duplicated",
        set_conditions(
            "task-complete",
            [{"name": "task_required_fields_complete", "fields": ["title", "title"]}],
        ),
        "duplicates",
    ),
    (
        "required fields contain a non-string",
        set_conditions("task-complete", [{"name": "task_required_fields_complete", "fields": [1]}]),
        "only strings",
    ),
    (
        "duplicate policy id",
        lambda d: d["policies"].append(copy.deepcopy(policy_named(d, "project-view"))),
        "Duplicate policy id",
    ),
]


@pytest.mark.parametrize(
    ("mutator", "message"),
    [(m, msg) for _, m, msg in INVALID_DOCUMENTS],
    ids=[name for name, _, _ in INVALID_DOCUMENTS],
)
def test_invalid_policy_documents_are_rejected(mutator: Mutator, message: str) -> None:
    document = shipped_document()
    mutator(document)

    with pytest.raises(PolicyConfigError, match=message):
        parse_policy_document(document)


@pytest.mark.parametrize("not_an_object", [[], "policies", 7, None, [{"id": "x"}]])
def test_a_document_that_is_not_an_object_is_rejected(not_an_object: object) -> None:
    with pytest.raises(PolicyConfigError, match="JSON object"):
        parse_policy_document(not_an_object)


@pytest.mark.parametrize("action", list(Action))
def test_a_missing_policy_for_any_mandatory_action_is_rejected(action: Action) -> None:
    document = shipped_document()
    document["policies"] = [p for p in document["policies"] if p["action"] != action.value]

    with pytest.raises(PolicyConfigError, match=f"Missing policy definition.*{action.value}"):
        parse_policy_document(document)


def test_an_action_covered_only_by_a_deny_policy_counts_as_missing() -> None:
    document = shipped_document()
    set_policy_field("project-view", "effect", "deny")(document)

    with pytest.raises(PolicyConfigError, match="Missing policy definition.*project.view"):
        parse_policy_document(document)


def test_nesting_up_to_the_limit_is_accepted() -> None:
    document = shipped_document()
    set_conditions("project-view", [nested_groups(MAX_GROUP_DEPTH)])(document)

    assert parse_policy_document(document) is not None


# ---- files --------------------------------------------------------------------------------------


def test_a_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(PolicyConfigError, match="Cannot read"):
        load_policy_registry(tmp_path / "nope.json")


def test_a_directory_instead_of_a_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(PolicyConfigError, match="Cannot read"):
        load_policy_registry(tmp_path)


@pytest.mark.parametrize(
    "content", ["", "{", "not json", "{'single': 'quotes'}", '{"version": 1,}']
)
def test_invalid_json_is_rejected(tmp_path: Path, content: str) -> None:
    path = tmp_path / "policies.json"
    path.write_text(content)

    with pytest.raises(PolicyConfigError, match="not valid JSON"):
        load_policy_registry(path)


def test_a_valid_file_elsewhere_loads(tmp_path: Path) -> None:
    path = tmp_path / "policies.json"
    path.write_text(json.dumps(shipped_document()))

    assert len(load_policy_registry(path)) == 9


# ---- safety: configuration is data, never code -------------------------------------------------


def test_configuration_cannot_execute_code(tmp_path: Path) -> None:
    marker = tmp_path / "pwned"
    document = shipped_document()
    payload = f"__import__('pathlib').Path({str(marker)!r}).write_text('x')"
    set_conditions("project-view", [payload])(document)

    with pytest.raises(PolicyConfigError, match="unknown condition"):
        parse_policy_document(document)

    assert not marker.exists()


def test_only_the_fixed_set_of_conditions_is_available() -> None:
    assert set(CONDITIONS) == {
        "is_authenticated",
        "is_project_member",
        "is_project_owner",
        "is_task_creator",
        "is_task_assignee",
        "task_status_is",
        "task_has_assignee",
        "task_required_fields_complete",
    }


def test_condition_parameter_validation_returns_normalized_values() -> None:
    spec = CONDITIONS["task_required_fields_complete"]

    assert spec.validate_params({"fields": ["title", "due_date"]}) == {
        "fields": ("title", "due_date")
    }
    with pytest.raises(ValueError, match="missing parameter"):
        spec.validate_params({})
