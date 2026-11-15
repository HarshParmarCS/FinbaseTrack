"""Structural guards: the properties that must hold for EVERY route and service method.

Individual feature tests prove behavior. These prove nothing was forgotten: a new route without
authentication, a service method that mutates before asking the policy engine, or a route that
is missing from the published contract fails here.
"""

import ast
import inspect
import json
import re
import textwrap
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from app.auth.dependencies import get_current_user
from app.core.openapi import EXAMPLES_FILE
from app.routers import auth, dashboard, health, project_members, projects, tasks
from app.services.dashboard_service import DashboardService
from app.services.project_member_service import ProjectMemberService
from app.services.project_service import ProjectService
from app.services.task_service import TaskService

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "docs" / "api-contract.md"
OPENAPI_FILE = ROOT / "docs" / "openapi.json"
PREFIX = "/api/v1"

# Reachable without an access token. Refresh and logout use the refresh cookie instead.
PUBLIC = {
    ("GET", "/health"),
    ("POST", "/auth/register"),
    ("POST", "/auth/login"),
    ("POST", "/auth/refresh"),
    ("POST", "/auth/logout"),
}


def _routes() -> Iterator[APIRoute]:
    for module in (health, auth, projects, project_members, tasks, dashboard):
        for route in module.router.routes:
            assert isinstance(route, APIRoute)
            yield route


def _dependencies(dependant: Any) -> Iterator[Any]:
    for sub in dependant.dependencies:
        yield sub.call
        yield from _dependencies(sub)


def _method(route: APIRoute) -> str:
    assert route.methods is not None
    (method,) = route.methods
    return method


ALL_ROUTES = [(_method(r), r.path, r) for r in _routes()]


def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", lambda _: str(uuid.uuid4()), PREFIX + path)


# ---- authentication ----------------------------------------------------------------------


@pytest.mark.parametrize(("method", "path", "route"), ALL_ROUTES)
def test_every_non_public_route_depends_on_get_current_user(
    method: str, path: str, route: APIRoute
) -> None:
    protected = get_current_user in set(_dependencies(route.dependant))

    assert protected == ((method, path) not in PUBLIC)


@pytest.mark.parametrize(("method", "path", "route"), ALL_ROUTES)
def test_anonymous_request_never_reaches_a_protected_route(
    method: str, path: str, route: APIRoute, client: TestClient
) -> None:
    response = client.request(method, _concrete(path), json={} if method != "GET" else None)

    if (method, path) == ("GET", "/health"):
        assert response.status_code == 200
    elif (method, path) == ("POST", "/auth/logout"):
        assert response.status_code == 204
    elif (method, path) in PUBLIC:
        assert response.status_code in {401, 409, 422}
    else:
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_route_inventory_matches_the_exported_openapi_paths() -> None:
    published = {
        (method.upper(), path.removeprefix(PREFIX))
        for path, item in json.loads(OPENAPI_FILE.read_text())["paths"].items()
        for method in item
    }

    assert published == {(m, p) for m, p, _ in ALL_ROUTES}


# ---- authorization is requested before any change ---------------------------------------

# Listings and dashboards are scoped to the caller's own projects by a repository filter,
# which docs/authorization-design.md documents as data scoping, not a policy decision.
DATA_SCOPED = {
    (ProjectService, "list_projects"),
    (DashboardService, "dashboard"),
    (DashboardService, "user_activity"),
}
READ_ONLY_PREFIXES = ("get", "list", "find", "count", "exists", "view", "build", "_")
SERVICES = [ProjectService, ProjectMemberService, TaskService, DashboardService]


def _public_methods(service: type) -> list[ast.FunctionDef]:
    tree = ast.parse(textwrap.dedent(inspect.getsource(service)))
    (cls,) = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    return [n for n in cls.body if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]


def _self_calls(function: ast.FunctionDef) -> list[tuple[int, str, str]]:
    """(line, collaborator, method) for every ``self.<collaborator>.<method>(...)`` call."""
    found = []
    for node in ast.walk(function):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            target = node.func.value
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                found.append((node.lineno, target.attr, node.func.attr))
    return sorted(found)


CASES = [
    (service, function)
    for service in SERVICES
    for function in _public_methods(service)
    if (service, function.name) not in DATA_SCOPED
]


@pytest.mark.parametrize(
    ("service", "function"), CASES, ids=[f"{s.__name__}.{f.name}" for s, f in CASES]
)
def test_service_method_asks_the_policy_engine_before_touching_data(
    service: type, function: ast.FunctionDef
) -> None:
    calls = _self_calls(function)
    authz_lines = [line for line, who, _ in calls if who == "authz"]
    data_lines = [line for line, who, _ in calls if who != "authz"]

    assert authz_lines, f"{service.__name__}.{function.name} never calls self.authz"
    assert not data_lines or min(authz_lines) < min(data_lines)


def test_data_scoped_allowlist_names_real_methods() -> None:
    for service, name in DATA_SCOPED:
        assert hasattr(service, name)


# ---- the contract documents every route ------------------------------------------------------

SECTION_LABELS = [
    "Authentication",
    "Authorization policy",
    "Query parameters",
    "Request body",
    "Response",
    "Error responses",
    "Example request",
    "Example response",
]


def _contract_sections() -> dict[tuple[str, str], str]:
    text = CONTRACT.read_text()
    parts = re.split(r"^#### \d+\.\d+\.\d+ ", text, flags=re.MULTILINE)[1:]
    sections = {}
    for part in parts:
        heading, _, body = part.partition("\n")
        method, path = heading.split(maxsplit=1)
        sections[(method, path.strip())] = body
    return sections


def test_contract_documents_exactly_the_implemented_routes() -> None:
    documented = {(m, p.removeprefix(PREFIX)) for m, p in _contract_sections()}

    assert documented == {(m, p) for m, p, _ in ALL_ROUTES}


@pytest.mark.parametrize(("method", "path"), sorted(_contract_sections()))
def test_every_contract_entry_has_all_required_sections(method: str, path: str) -> None:
    body = _contract_sections()[(method, path)]

    missing = [label for label in SECTION_LABELS if label not in body]

    assert not missing, f"{method} {path} lacks: {missing}"


def test_contract_examples_validate_against_the_response_models() -> None:
    examples = json.loads(EXAMPLES_FILE.read_text())
    models = {(f"{m} {PREFIX}{p}"): r.response_model for m, p, r in ALL_ROUTES}

    assert set(examples) == set(models)
    for key, example in examples.items():
        success = example["success"]
        if success.get("body") is not None:
            TypeAdapter(models[key]).validate_python(success["body"])


def test_exported_openapi_file_is_current(app: Any) -> None:
    assert json.loads(OPENAPI_FILE.read_text()) == json.loads(json.dumps(app.openapi()))
