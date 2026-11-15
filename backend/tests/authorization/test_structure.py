"""Structural guarantees: the decision side is framework-free, nothing is evaluated as code,
and there is no RBAC anywhere."""

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from app.database.base import Base
from tests.conftest import BACKEND_DIR

APP_DIR = BACKEND_DIR / "app"
AUTHZ_DIR = APP_DIR / "authorization"
AUTHZ_FILES = sorted(AUTHZ_DIR.glob("*.py"))
EXPECTED_MODULES = {
    "__init__",
    "conditions",
    "context",
    "decision",
    "dependencies",
    "engine",
    "information",
    "policies",
    "policy_loader",
    "registry",
    "service",
}


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(), filename=str(path))


def imported_modules(tree: ast.Module) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_the_authorization_package_has_the_expected_files() -> None:
    assert {path.stem for path in AUTHZ_FILES} == EXPECTED_MODULES
    assert (AUTHZ_DIR / "policies.json").is_file()


# ---- framework independence ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "path", [p for p in AUTHZ_FILES if p.stem != "dependencies"], ids=lambda p: p.stem
)
def test_only_dependencies_py_imports_the_web_framework(path: Path) -> None:
    tree = parse(path)

    web = {m for m in imported_modules(tree) if m.split(".")[0] in {"fastapi", "starlette"}}
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}

    assert web == set(), f"{path.name} imports {web}"
    assert "HTTPException" not in names


def test_the_decision_engine_can_be_imported_without_loading_fastapi() -> None:
    code = (
        "import sys; import app.authorization.engine, app.authorization.policy_loader; "
        "loaded = [m for m in sys.modules if m.split('.')[0] in ('fastapi', 'starlette')]; "
        "assert not loaded, loaded"
    )

    result = subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND_DIR, capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr


def test_repositories_contain_no_authorization_logic() -> None:
    for path in (APP_DIR / "repositories").glob("*.py"):
        imports = imported_modules(parse(path))
        assert not any(m.startswith("app.authorization") for m in imports), path.name


def test_routers_do_not_import_the_policy_engine_or_conditions() -> None:
    for path in (APP_DIR / "routers").glob("*.py"):
        imports = imported_modules(parse(path))
        forbidden = {"app.authorization.engine", "app.authorization.conditions"}
        assert not (imports & forbidden), path.name


# ---- no code execution ------------------------------------------------------------------------


FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__"}
FORBIDDEN_MODULES = {"importlib", "pickle", "marshal", "subprocess", "ctypes", "runpy"}


@pytest.mark.parametrize("path", AUTHZ_FILES, ids=lambda p: p.stem)
def test_policy_code_never_evaluates_strings_as_code(path: Path) -> None:
    tree = parse(path)

    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    modules = {m.split(".")[0] for m in imported_modules(tree)}

    assert not (calls & FORBIDDEN_CALLS), f"{path.name} calls {calls & FORBIDDEN_CALLS}"
    assert not (modules & FORBIDDEN_MODULES), f"{path.name} imports {modules & FORBIDDEN_MODULES}"


def test_the_json_policy_file_contains_no_code_like_values() -> None:
    text = (AUTHZ_DIR / "policies.json").read_text()

    for fragment in ("lambda", "import", "eval(", "exec(", "__", "os.", "subprocess"):
        assert fragment not in text, fragment


# ---- there is no RBAC ---------------------------------------------------------------------------

FORBIDDEN_TOKENS = {
    "role",
    "roles",
    "rbac",
    "admin",
    "administrator",
    "manager",
    "developer",
    "employee",
    "superuser",
    "staff",
}


def tokens(identifier: str) -> set[str]:
    """Split snake_case and CamelCase identifiers into lowercase words."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", identifier)
    return {part.lower() for part in spaced.split("_") if part}


def identifiers(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.keyword):
            if node.arg:
                names.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.alias):
            names.add(node.asname or node.name)
    return names


def test_no_role_like_identifiers_exist_anywhere_in_the_application_code() -> None:
    offenders: dict[str, set[str]] = {}
    for path in APP_DIR.rglob("*.py"):
        bad = {name for name in identifiers(parse(path)) if tokens(name) & FORBIDDEN_TOKENS}
        if bad:
            offenders[str(path.relative_to(APP_DIR))] = bad

    assert offenders == {}


def test_no_database_column_or_table_models_roles_or_permissions() -> None:
    names = set(Base.metadata.tables)
    for table in Base.metadata.tables.values():
        names.update(column.name for column in table.columns)

    offenders = {
        name for name in names if tokens(name) & (FORBIDDEN_TOKENS | {"permission", "permissions"})
    }

    assert offenders == set()


def test_users_table_stores_identity_only() -> None:
    columns = {column.name for column in Base.metadata.tables["users"].columns}

    assert columns == {
        "id",
        "name",
        "email",
        "password_hash",
        "is_active",
        "created_at",
        "updated_at",
    }


def test_policy_file_defines_no_roles_only_relationship_conditions() -> None:
    document = json.loads((AUTHZ_DIR / "policies.json").read_text())

    assert set(document) == {"version", "default_effect", "policies"}
    raw = json.dumps(document).lower()
    assert not (tokens(re.sub(r"[^a-z_]+", "_", raw)) & FORBIDDEN_TOKENS)
    for policy in document["policies"]:
        assert set(policy) <= {"id", "action", "effect", "operator", "conditions", "description"}
