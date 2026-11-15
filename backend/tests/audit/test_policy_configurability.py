"""The JSON policy file really drives the running application (configurable PBAC).

Every test serves the SAME database through two apps, the default one and one started with an
edited policy file, and replays the SAME request through both. Only the policy file differs.
"""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_POLICY_FILE, Settings, get_settings
from app.database.session import get_db
from app.main import create_app
from tests.projects.helpers import PROJECTS, Actor
from tests.tasks.helpers import TASKS, Team, error_of


def edited_app(
    db_session: Session, tmp_path: Path, edit: Any, name: str = "policies.json"
) -> FastAPI:
    document = json.loads(DEFAULT_POLICY_FILE.read_text())
    edit(document["policies"] if False else document)
    path = tmp_path / name
    path.write_text(json.dumps(document))
    settings = Settings(
        _env_file=None,
        database_url=get_settings().database_url,
        jwt_secret_key=get_settings().jwt_secret_key,
        policy_file=path,
    )
    application = create_app(settings)

    def override() -> Any:
        try:
            yield db_session
        except Exception:
            db_session.rollback()
            raise

    application.dependency_overrides[get_db] = override
    return application


def policy(document: dict[str, Any], policy_id: str) -> dict[str, Any]:
    return next(p for p in document["policies"] if p["id"] == policy_id)


def as_user_on(app: FastAPI, actor: Actor) -> TestClient:
    """The same logged-in user (same cookies), talking to a different app instance."""
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.update(actor.client.cookies)
    return client


def csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("csrf_token") or ""}


def test_relaxing_a_policy_in_json_lets_members_update_projects(
    team: Team, db_session: Session, tmp_path: Path
) -> None:
    def relax(document: dict[str, Any]) -> None:
        policy(document, "project-update")["conditions"] = ["is_project_member"]

    relaxed = as_user_on(edited_app(db_session, tmp_path, relax), team.ben)
    url = f"{PROJECTS}/{team.pid}"

    default = team.ben.patch(url, {"name": "By Ben"})
    changed = relaxed.patch(url, json={"name": "By Ben"}, headers=csrf(relaxed))

    assert default.status_code == 403
    assert changed.status_code == 200
    assert changed.json()["data"]["name"] == "By Ben"


def test_tightening_a_policy_in_json_takes_rights_away(
    team: Team, db_session: Session, tmp_path: Path
) -> None:
    def tighten(document: dict[str, Any]) -> None:
        policy(document, "task-update")["conditions"] = ["is_project_owner"]

    tight = as_user_on(edited_app(db_session, tmp_path, tighten), team.ben)
    task = team.new_task(team.ben)
    url = f"{TASKS}/{task['id']}"

    default = team.ben.patch(url, {"title": "Mine"})
    changed = tight.patch(url, json={"title": "Mine again"}, headers=csrf(tight))

    assert default.status_code == 200  # the creator may update by default
    assert changed.status_code == 403  # but not once the policy file says owner-only
    assert error_of(changed)["details"][0]["policy_id"] == "task-update"


def test_a_condition_parameter_in_json_changes_the_delete_rule(
    team: Team, db_session: Session, tmp_path: Path
) -> None:
    def only_in_progress(document: dict[str, Any]) -> None:
        conditions = policy(document, "task-delete")["conditions"]
        conditions[1]["value"] = "in_progress"

    flipped = as_user_on(edited_app(db_session, tmp_path, only_in_progress), team.ana)
    todo = team.new_task(team.ben, title="todo task")
    running = team.new_task(team.ben, title="running", status="in_progress")

    assert team.ana.delete(f"{TASKS}/{running['id']}").status_code == 403  # default: todo only
    assert flipped.delete(f"{TASKS}/{todo['id']}", headers=csrf(flipped)).status_code == 403
    assert flipped.delete(f"{TASKS}/{running['id']}", headers=csrf(flipped)).status_code == 204


def test_the_required_completion_fields_are_configurable(
    team: Team, db_session: Session, tmp_path: Path
) -> None:
    def drop_description(document: dict[str, Any]) -> None:
        for condition in policy(document, "task-complete")["conditions"]:
            if isinstance(condition, dict) and "fields" in condition:
                condition["fields"] = ["title", "priority", "due_date", "assignee"]

    relaxed = as_user_on(edited_app(db_session, tmp_path, drop_description), team.ben)
    task = team.new_task(
        team.ben, priority="low", due_date="2026-12-01", assignee_id=str(team.cy.id)
    )  # no description
    assert (
        team.ben.patch(f"{TASKS}/{task['id']}/status", {"status": "in_progress"}).status_code == 200
    )
    status_url = f"{TASKS}/{task['id']}/status"

    default = team.ben.patch(status_url, {"status": "completed"})
    changed = relaxed.patch(status_url, json={"status": "completed"}, headers=csrf(relaxed))

    assert default.status_code == 403
    assert changed.status_code == 200


def test_an_explicit_deny_policy_in_json_overrides_an_allow(
    team: Team, db_session: Session, tmp_path: Path
) -> None:
    def block_owner(document: dict[str, Any]) -> None:
        document["policies"].append(
            {
                "id": "no-owner-view",
                "action": "project.view",
                "effect": "deny",
                "conditions": ["is_project_owner"],
                "description": "Owners may not view their own project in this test.",
            }
        )

    blocked_app = edited_app(db_session, tmp_path, block_owner)
    blocked = as_user_on(blocked_app, team.ana)
    url = f"{PROJECTS}/{team.pid}"

    assert team.ana.get(url).status_code == 200
    response = blocked.get(url)
    assert response.status_code == 403
    assert error_of(response)["details"][0]["policy_id"] == "no-owner-view"
    assert as_user_on(blocked_app, team.ben).get(url).status_code == 200  # others unaffected


def test_an_edited_policy_that_breaks_the_rules_stops_the_application(
    db_session: Session, tmp_path: Path
) -> None:
    def break_it(document: dict[str, Any]) -> None:
        policy(document, "project-view")["conditions"] = ["is_admin"]  # no such condition

    with pytest.raises(Exception, match="unknown condition"):
        edited_app(db_session, tmp_path, break_it)


def test_the_shipped_policy_file_is_not_modified_by_these_tests() -> None:
    document = json.loads(DEFAULT_POLICY_FILE.read_text())

    assert len(document["policies"]) == 9
    assert copy.deepcopy(document)["default_effect"] == "deny"
