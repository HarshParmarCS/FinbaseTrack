"""Regenerate the API documentation from the running application.

Run from ``backend/`` (needs the PostgreSQL test database from backend/.env):

    python -m scripts.generate_api_docs

It plays a realistic scenario against the real application (real commits on the dedicated
``*_test`` database, truncated afterwards), records the actual requests and responses, and writes:

* ``app/api/examples.json``  real examples, served inside the OpenAPI document
* ``docs/openapi.json``      the OpenAPI document (deterministic)
* ``docs/api-contract.md``   section 3 (the endpoint reference) is replaced; the rest is kept

Identifiers and timestamps are normalized, so re-running produces identical output.
"""

import json
import os
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
DOCS = BACKEND.parent / "docs"
EXAMPLES_FILE = BACKEND / "app" / "api" / "examples.json"
OPENAPI_FILE = DOCS / "openapi.json"
CONTRACT_FILE = DOCS / "api-contract.md"

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
TIME_RE = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|\+00:00)")


# --------------------------------------------------------------------------------------------
# Endpoint metadata (authoritative wording; everything else is captured from the real API)
# --------------------------------------------------------------------------------------------

AUTH_PUBLIC = "Public (no authentication)"
AUTH_ACCESS = "Access-token cookie (`access_token`)"
AUTH_ACCESS_CSRF = "Access-token cookie + `X-CSRF-Token` header"
AUTH_REFRESH = "Refresh-token cookie (`refresh_token`) + `X-CSRF-Token` header"

Q = list[tuple[str, str, str]]
E = list[tuple[int, str, str]]

ENDPOINTS: list[dict[str, Any]] = [
    # ---- health ----------------------------------------------------------------------
    dict(
        key="GET /api/v1/health",
        group="Health",
        auth=AUTH_PUBLIC,
        authz="None (liveness only; does not touch the database).",
        query=[],
        request=None,
        response='`Envelope<{status: "ok"}>`',
        errors=[],
        rules=["Intended for container and load-balancer health checks."],
    ),
    # ---- auth --------------------------------------------------------------------------
    dict(
        key="POST /api/v1/auth/register",
        group="Authentication",
        auth=AUTH_PUBLIC,
        authz="None. The new account is created and logged in.",
        query=[],
        request="`{ name: string (1-120), email: string, password: string (8-128) }`. "
        "Unknown fields give 422. The email is trimmed and lowercased.",
        response="`Envelope<UserOut>` and three `Set-Cookie` headers (`access_token`, "
        "`refresh_token`, `csrf_token`). No token appears in the body.",
        errors=[(409, "CONFLICT", "An account with this email already exists.")],
        rules=[
            "The password is stored only as an Argon2id hash.",
            "Identity fields (`id`, `is_active`, ...) cannot be supplied: they give 422.",
            "Writes a `user.registered` activity entry.",
        ],
    ),
    dict(
        key="POST /api/v1/auth/login",
        group="Authentication",
        auth=AUTH_PUBLIC,
        authz="None. Inactive accounts cannot log in.",
        query=[],
        request="`{ email: string, password: string }`",
        response="`Envelope<UserOut>` and three `Set-Cookie` headers (see register).",
        errors=[
            (
                401,
                "UNAUTHENTICATED",
                "Wrong email or password, or inactive account. "
                'The message is always "Invalid email or password."',
            )
        ],
        rules=[
            "Each login starts a new refresh-token family (one per device).",
            "A request whose `Origin` header is not allowed gets 403, even without cookies.",
            "Writes an `auth.login` activity entry.",
        ],
    ),
    dict(
        key="POST /api/v1/auth/refresh",
        group="Authentication",
        auth=AUTH_REFRESH,
        authz="None (the refresh token is the credential).",
        query=[],
        request="None (no body).",
        response="`Envelope<UserOut>` and three new `Set-Cookie` headers.",
        errors=[
            (
                401,
                "UNAUTHENTICATED",
                "Missing, invalid, expired, revoked or reused "
                "refresh token. The auth cookies are cleared in the response.",
            )
        ],
        rules=[
            "Rotation: the presented token is revoked and replaced in the same family.",
            "Presenting an already-rotated token is treated as theft: the whole family is "
            "revoked and an `auth.refresh_reuse_detected` activity entry is written.",
            "An access token is never accepted here (different audience and type).",
        ],
    ),
    dict(
        key="POST /api/v1/auth/logout",
        group="Authentication",
        auth=AUTH_REFRESH,
        authz="None.",
        query=[],
        request="None (no body).",
        response="`204 No Content` with `Set-Cookie` headers that clear all three cookies.",
        errors=[],
        rules=[
            "Always 204, also when not logged in or when the token is invalid (idempotent).",
            "Revokes the presented token's whole family. Writes `auth.logout` when it is known.",
            "A copied access token stays valid until its 15-minute expiry (stateless token).",
        ],
    ),
    dict(
        key="GET /api/v1/auth/me",
        group="Authentication",
        auth=AUTH_ACCESS,
        authz="None (returns the caller).",
        query=[],
        request="None.",
        response="`Envelope<UserOut>`",
        errors=[],
        rules=["The identity comes only from the verified token, never from the request."],
    ),
    # ---- projects ------------------------------------------------------------------------
    dict(
        key="POST /api/v1/projects",
        group="Projects",
        auth=AUTH_ACCESS_CSRF,
        authz="Policy `project.create`: any authenticated, active user.",
        query=[],
        request="`{ name: string (1-120), description?: string|null (max 5000), "
        'status?: "active"|"archived" }` (default status `active`). `owner_id` and other '
        "unknown fields give 422.",
        response="`Envelope<ProjectDetailOut>` (201). The caller is owner and first member.",
        errors=[],
        rules=[
            "The project and the owner's membership are written in ONE transaction.",
            "Writes a `project.created` activity entry.",
        ],
    ),
    dict(
        key="GET /api/v1/projects",
        group="Projects",
        auth=AUTH_ACCESS,
        authz="Data scoping: only projects the caller is a CURRENT member of.",
        query=[
            ("q", "string (max 100)", "Name contains, case-insensitive. `%` and `_` are literal."),
            ("status", "`active`|`archived`", "Filter by status."),
            ("page", "int 1-100000", "Default 1."),
            ("page_size / limit", "int 1-100", "Default 20. `limit` is an alias."),
        ],
        request="None.",
        response="`PagedEnvelope<ProjectOut>` ordered by most recently updated. Each item has "
        "`member_count`, `task_counts` and `allowed_actions`, computed in one query.",
        errors=[],
        rules=["Never lists a project the caller does not belong to."],
    ),
    dict(
        key="GET /api/v1/projects/{project_id}",
        group="Projects",
        auth=AUTH_ACCESS,
        authz="Policy `project.view`: current members only.",
        query=[],
        request="None.",
        response="`Envelope<ProjectDetailOut>`: project, owner, members (owner first), counts, "
        "`allowed_actions`.",
        errors=[
            (
                404,
                "NOT_FOUND",
                "The project does not exist, or the caller is not a member "
                "(the two cases are indistinguishable).",
            )
        ],
        rules=[],
    ),
    dict(
        key="PATCH /api/v1/projects/{project_id}",
        group="Projects",
        auth=AUTH_ACCESS_CSRF,
        authz="Policy `project.update`: the project owner only.",
        query=[],
        request="Any of `{ name, description, status }`; at least one. Omitted fields are "
        "unchanged, `description: null` clears it, `name` and `status` cannot be null.",
        response="`Envelope<ProjectDetailOut>`",
        errors=[
            (403, "FORBIDDEN", "A member who is not the owner (policy `project-update`)."),
            (404, "NOT_FOUND", "Missing project or not a member."),
        ],
        rules=[
            "A request that changes nothing succeeds and writes no activity entry.",
            "Writes `project.updated` with the old and new values.",
        ],
    ),
    dict(
        key="DELETE /api/v1/projects/{project_id}",
        group="Projects",
        auth=AUTH_ACCESS_CSRF,
        authz="Policy `project.delete`: the project owner only.",
        query=[],
        request="None.",
        response="`204 No Content`",
        errors=[
            (403, "FORBIDDEN", "A member who is not the owner (policy `project-delete`)."),
            (404, "NOT_FOUND", "Missing project or not a member."),
        ],
        rules=[
            "One transaction; the database cascades the project's members and tasks.",
            "Activity history is kept (no foreign keys) and a `project.deleted` entry is written.",
        ],
    ),
    # ---- members ---------------------------------------------------------------------------
    dict(
        key="GET /api/v1/projects/{project_id}/members",
        group="Project members",
        auth=AUTH_ACCESS,
        authz="Policy `project.view`: current members only.",
        query=[],
        request="None.",
        response="`Envelope<MemberOut[]>` (not paginated): the owner first, then by join time.",
        errors=[(404, "NOT_FOUND", "Missing project or not a member.")],
        rules=[],
    ),
    dict(
        key="POST /api/v1/projects/{project_id}/members",
        group="Project members",
        auth=AUTH_ACCESS_CSRF,
        authz="Policy `project.member.manage`: the project owner only.",
        query=[],
        request="Exactly one of `{ email: string }` or `{ user_id: uuid }` (the person being "
        "added, never the caller). Both or neither gives 422.",
        response="`Envelope<MemberOut>` (201)",
        errors=[
            (403, "FORBIDDEN", "A member who is not the owner (policy `project-member-manage`)."),
            (
                404,
                "NOT_FOUND",
                "Missing project or not a member, or no active user matches "
                '(message "User not found.").',
            ),
            (409, "CONFLICT", "The user is already a member (including the owner)."),
        ],
        rules=["The new member has access immediately.", "Writes a `member.added` entry."],
    ),
    dict(
        key="DELETE /api/v1/projects/{project_id}/members/{user_id}",
        group="Project members",
        auth=AUTH_ACCESS_CSRF,
        authz="Policy `project.member.manage`: the project owner only.",
        query=[],
        request="None.",
        response="`204 No Content`",
        errors=[
            (403, "FORBIDDEN", "A member who is not the owner (policy `project-member-manage`)."),
            (
                404,
                "NOT_FOUND",
                "Missing project or not a member, or the target is not a member "
                '(message "Member not found.").',
            ),
            (422, "BUSINESS_RULE_VIOLATION", "The target is the project owner."),
        ],
        rules=[
            "One transaction: the member's task assignments in this project are cleared (all "
            "statuses), then the membership is deleted. Tasks they created stay.",
            "Access is revoked immediately: the removed user's next request gets 404.",
            "Writes `member.removed` and one `task.unassigned` entry per cleared task.",
        ],
    ),
    # ---- tasks -------------------------------------------------------------------------------
    dict(
        key="POST /api/v1/projects/{project_id}/tasks",
        group="Tasks",
        auth=AUTH_ACCESS_CSRF,
        authz="Policy `task.create` (members only); plus `task.complete` when the new task is "
        "created already `completed`.",
        query=[],
        request="`{ title: string (1-200), description?: string|null (max 5000), "
        "priority?: low|medium|high, status?: todo|in_progress|completed, "
        "assignee_id?: uuid|null, due_date?: date|null }`. Defaults: priority `medium`, status "
        "`todo`. `creator_id`, `project_id`, `position` and unknown fields give 422.",
        response="`Envelope<TaskOut>` (201). The creator is the caller; `position` is the end of "
        "the status column.",
        errors=[
            (
                403,
                "FORBIDDEN",
                "Created as `completed` without an assignee or required "
                "information (policy `task-complete`).",
            ),
            (404, "NOT_FOUND", "Missing project or not a member."),
            (422, "BUSINESS_RULE_VIOLATION", "The assignee is not a project member."),
        ],
        rules=["Writes a `task.created` entry."],
    ),
    dict(
        key="GET /api/v1/projects/{project_id}/tasks",
        group="Tasks",
        auth=AUTH_ACCESS,
        authz="Policy `project.view`: current members only.",
        query=[
            ("q", "string (max 100)", "Title or description contains, case-insensitive."),
            ("status", "`todo`|`in_progress`|`completed`", "May be repeated."),
            ("priority", "`low`|`medium`|`high`", "May be repeated."),
            ("assignee_id", "uuid or `unassigned`", "Anything else gives 422."),
            ("due_after", "date", "Due on or after (tasks without a due date are excluded)."),
            ("due_before", "date", "Due on or before (tasks without a due date are excluded)."),
            (
                "overdue",
                "boolean",
                "`true`: due before today (UTC) and not completed. `false`: the complement.",
            ),
            (
                "sort",
                "enum",
                "`created_at`, `-created_at` (default), `updated_at`, "
                "`-updated_at`, `due_date`, `-due_date`, `priority`, `-priority`, `position`. "
                "Anything else gives 422. Ties are broken by `id`.",
            ),
            ("page", "int 1-100000", "Default 1."),
            ("page_size / limit", "int 1-100", "Default 20. `limit` is an alias."),
        ],
        request="None.",
        response="`PagedEnvelope<TaskOut>`",
        errors=[(404, "NOT_FOUND", "Missing project or not a member.")],
        rules=["Creators and assignees come from joins: two queries per page, whatever its size."],
    ),
    dict(
        key="GET /api/v1/tasks/{task_id}",
        group="Tasks",
        auth=AUTH_ACCESS,
        authz="Policy `project.view` evaluated on the task's project (the project is read from "
        "the database, never from the request).",
        query=[],
        request="None.",
        response="`Envelope<TaskOut>` with `creator` and `assignee` objects.",
        errors=[
            (
                404,
                "NOT_FOUND",
                "The task does not exist, or the caller is not a member of "
                "its project (indistinguishable).",
            )
        ],
        rules=[],
    ),
    dict(
        key="PATCH /api/v1/tasks/{task_id}",
        group="Tasks",
        auth=AUTH_ACCESS_CSRF,
        authz="Policy `task.update`: the task creator OR assignee, who must still be a project "
        "member. A task that is completed must stay complete (policy `task.complete`).",
        query=[],
        request="Any of `{ title, description, priority, due_date, assignee_id }`; at least one. "
        "`null` clears description, due_date and assignee. `status`, `position`, `creator_id`, "
        "`project_id` and timestamps are rejected (422): status changes use the status endpoint.",
        response="`Envelope<TaskOut>`",
        errors=[
            (
                403,
                "FORBIDDEN",
                "Not the creator or assignee (`task-update`), or the edit would "
                "make a completed task incomplete (`task-complete`).",
            ),
            (404, "NOT_FOUND", "Missing task or not a member of its project."),
            (422, "BUSINESS_RULE_VIOLATION", "The assignee is not a project member."),
        ],
        rules=[
            "Writes `task.updated` (old and new values) and `task.assigned` or "
            "`task.unassigned` when the assignee changes. A no-op writes nothing."
        ],
    ),
    dict(
        key="PATCH /api/v1/tasks/{task_id}/status",
        group="Tasks",
        auth=AUTH_ACCESS_CSRF,
        authz="Policy `task.update` (creator or assignee); also `task.complete` when the new "
        "status is `completed`: an assignee who is a member, a non-blank title and description, "
        "a priority and a due date.",
        query=[],
        request="`{ status: todo|in_progress|completed, position?: number }`. `position` places "
        "the task on the board (default: end of the new column). Numbers only, finite, within "
        "+-1e12.",
        response="`Envelope<TaskOut>`",
        errors=[
            (
                403,
                "FORBIDDEN",
                "Not the creator or assignee (`task-update`), or the completion "
                "information is missing (`task-complete`).",
            ),
            (404, "NOT_FOUND", "Missing task or not a member of its project."),
            (
                422,
                "BUSINESS_RULE_VIOLATION",
                "Invalid transition, or the task is already in "
                "that status and no `position` was given.",
            ),
        ],
        rules=[
            "Transitions form a line: `todo` <-> `in_progress` <-> `completed`. Direct "
            "`todo` <-> `completed` is rejected.",
            "`completed_at` is set when entering `completed` and cleared when leaving it.",
            "An invalid transition is reported (422) before the completion policy (403).",
            "Writes a `task.status_changed` entry.",
        ],
    ),
    dict(
        key="DELETE /api/v1/tasks/{task_id}",
        group="Tasks",
        auth=AUTH_ACCESS_CSRF,
        authz="Policy `task.delete`: the project owner AND the task status is `todo`.",
        query=[],
        request="None.",
        response="`204 No Content`",
        errors=[
            (
                403,
                "FORBIDDEN",
                "Not the owner, or the task is not `todo` (policy `task-delete`). "
                "The task creator cannot delete either.",
            ),
            (404, "NOT_FOUND", "Missing task or not a member of its project."),
        ],
        rules=["Writes a `task.deleted` entry; the history outlives the task."],
    ),
    # ---- dashboard and activity ------------------------------------------------------------------
    dict(
        key="GET /api/v1/dashboard/stats",
        group="Dashboard and activity",
        auth=AUTH_ACCESS,
        authz="Data scoping: only projects the caller is a CURRENT member of.",
        query=[],
        request="None.",
        response="`Envelope<DashboardStats>`. `pending` = todo + in_progress. `overdue` = due "
        "before today (UTC) and not completed. `assigned_to_me` = assigned to the caller and not "
        "completed. `recent_activity` = the 10 newest entries.",
        errors=[],
        rules=["Three queries in total, however much data exists."],
    ),
    dict(
        key="GET /api/v1/dashboard/activity",
        group="Dashboard and activity",
        auth=AUTH_ACCESS,
        authz="Data scoping: only projects the caller is a CURRENT member of.",
        query=[
            ("page", "int 1-100000", "Default 1."),
            ("page_size / limit", "int 1-100", "Default 20. `limit` is an alias."),
        ],
        request="None.",
        response="`PagedEnvelope<ActivityOut>`, newest first.",
        errors=[],
        rules=[
            "Entries without a project (login, logout, registration) never appear.",
            "A removed member stops seeing the project's activity immediately.",
        ],
    ),
    dict(
        key="GET /api/v1/projects/{project_id}/activity",
        group="Dashboard and activity",
        auth=AUTH_ACCESS,
        authz="Policy `project.view`: current members only.",
        query=[
            ("page", "int 1-100000", "Default 1."),
            ("page_size / limit", "int 1-100", "Default 20. `limit` is an alias."),
        ],
        request="None.",
        response="`PagedEnvelope<ActivityOut>`, newest first.",
        errors=[(404, "NOT_FOUND", "Missing project or not a member.")],
        rules=[],
    ),
]


# --------------------------------------------------------------------------------------------
# Capturing real examples
# --------------------------------------------------------------------------------------------


class Recorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def record(self, template: str, kind: str, method: str, response: Any, **request: Any) -> Any:
        self.calls.append(
            {
                "key": f"{method} {template}",
                "kind": kind,
                "request": request,
                "status": response.status_code,
                "body": response.json() if response.content else None,
                "set_cookie": [_cookie_line(c) for c in response.headers.get_list("set-cookie")],
            }
        )
        return response


def _cookie_line(raw: str) -> str:
    name, rest = raw.split("=", 1)
    attributes = rest.split(";", 1)[1].strip() if ";" in rest else ""
    attributes = re.sub(r"expires=[^;]+;\s*", "", attributes, flags=re.I)
    if "Max-Age=0" in attributes:
        return f"Set-Cookie: {name}=; {attributes}"
    label = {"access_token": "<access-token-jwt>", "refresh_token": "<refresh-token-jwt>"}.get(
        name, "<csrf-token>"
    )
    return f"Set-Cookie: {name}={label}; {attributes}"


def run_scenario() -> list[dict[str, Any]]:
    """Play a realistic session against the real app and return every recorded call."""
    from argon2 import PasswordHasher
    from fastapi.testclient import TestClient

    from app.auth import passwords
    from app.main import create_app

    passwords._hasher = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    app = create_app()
    rec = Recorder()

    def new_client() -> TestClient:
        return TestClient(app, base_url="http://localhost:8000", raise_server_exceptions=False)

    def csrf(c: TestClient) -> dict[str, str]:
        return {"X-CSRF-Token": c.cookies.get("csrf_token") or ""}

    def call(
        c: TestClient,
        template: str,
        method: str,
        path: str,
        *,
        kind: str = "success",
        json_body: Any = None,
        params: dict[str, Any] | None = None,
        use_csrf: bool = True,
        expect: int | None = None,
        anonymous: bool = False,
    ) -> Any:
        # Only a logged-in caller sends the CSRF header (login/register/health do not need it).
        sends_csrf = use_csrf and not anonymous and method in {"POST", "PATCH", "DELETE"}
        headers = csrf(c) if sends_csrf else {}
        response = c.request(method, path, json=json_body, params=params, headers=headers)
        if expect is not None:
            assert response.status_code == expect, (
                method,
                path,
                response.status_code,
                response.text,
            )
        rec.record(
            template,
            kind,
            method,
            response,
            path=path,
            params=params,
            body=json_body,
            authenticated=not anonymous,
            csrf=bool(headers),
        )
        return response

    api = "/api/v1"
    password = "correct-horse-battery"

    def register(email: str, name: str, *, record: bool = False) -> TestClient:
        c = new_client()
        body = {"name": name, "email": email, "password": password}
        if record:
            call(
                c,
                f"{api}/auth/register",
                "POST",
                f"{api}/auth/register",
                json_body=body,
                expect=201,
                anonymous=True,
            )
        else:
            assert c.post(f"{api}/auth/register", json=body).status_code == 201
        return c

    # -- authentication -----------------------------------------------
    ana = register("ana@example.com", "Ana Lopez", record=True)
    call(
        new_client(),
        f"{api}/auth/register",
        "POST",
        f"{api}/auth/register",
        kind="error",
        json_body={"name": "Ana Again", "email": "ana@example.com", "password": password},
        expect=409,
        anonymous=True,
    )
    ben = register("ben@example.com", "Ben Carter")
    cy = register("cy@example.com", "Cy Dunn")
    dan = register("dan@example.com", "Dan Evans")

    login_client = new_client()
    call(
        login_client,
        f"{api}/auth/login",
        "POST",
        f"{api}/auth/login",
        json_body={"email": "ana@example.com", "password": password},
        expect=200,
        anonymous=True,
    )
    call(
        new_client(),
        f"{api}/auth/login",
        "POST",
        f"{api}/auth/login",
        kind="error",
        json_body={"email": "ana@example.com", "password": "wrong-password"},
        expect=401,
        anonymous=True,
    )
    call(ana, f"{api}/auth/me", "GET", f"{api}/auth/me", expect=200)
    call(ana, f"{api}/auth/refresh", "POST", f"{api}/auth/refresh", expect=200)
    call(
        new_client(),
        f"{api}/auth/refresh",
        "POST",
        f"{api}/auth/refresh",
        kind="error",
        expect=401,
        anonymous=True,
        use_csrf=False,
    )

    # -- projects -----------------------------------------------------
    created = call(
        ana,
        f"{api}/projects",
        "POST",
        f"{api}/projects",
        json_body={"name": "Website redesign", "description": "Q4 launch"},
        expect=201,
    )
    pid = created.json()["data"]["id"]
    call(
        ana,
        f"{api}/projects",
        "POST",
        f"{api}/projects",
        kind="error",
        json_body={"name": "   "},
        expect=422,
    )
    ben_id = ben.get(f"{api}/auth/me").json()["data"]["id"]
    cy_id = cy.get(f"{api}/auth/me").json()["data"]["id"]
    dan_id = dan.get(f"{api}/auth/me").json()["data"]["id"]
    ana_id = ana.get(f"{api}/auth/me").json()["data"]["id"]

    members = f"{api}/projects/{pid}/members"
    tpl_members = f"{api}/projects/{{project_id}}/members"
    call(ana, tpl_members, "POST", members, json_body={"email": "ben@example.com"}, expect=201)
    call(
        ana,
        tpl_members,
        "POST",
        members,
        kind="error",
        json_body={"email": "ben@example.com"},
        expect=409,
    )
    assert ana.post(members, json={"user_id": cy_id}, headers=csrf(ana)).status_code == 201

    call(
        ben,
        f"{api}/projects",
        "GET",
        f"{api}/projects",
        params={"q": "web", "page_size": 10},
        expect=200,
    )
    call(ana, f"{api}/projects/{{project_id}}", "GET", f"{api}/projects/{pid}", expect=200)
    call(
        dan,
        f"{api}/projects/{{project_id}}",
        "GET",
        f"{api}/projects/{pid}",
        kind="error",
        expect=404,
    )
    call(ana, f"{api}/projects/{{project_id}}/members", "GET", members, expect=200)
    call(
        ben,
        f"{api}/projects/{{project_id}}",
        "PATCH",
        f"{api}/projects/{pid}",
        kind="error",
        json_body={"name": "Hijacked"},
        expect=403,
    )
    call(
        ana,
        f"{api}/projects/{{project_id}}",
        "PATCH",
        f"{api}/projects/{pid}",
        json_body={"description": "Q4 launch of the new marketing site"},
        expect=200,
    )

    # -- tasks --------------------------------------------------------
    tasks = f"{api}/projects/{pid}/tasks"
    tpl_tasks = f"{api}/projects/{{project_id}}/tasks"
    call(
        ben,
        tpl_tasks,
        "POST",
        tasks,
        kind="error",
        json_body={"title": "Design login page", "assignee_id": dan_id},
        expect=422,
    )
    made = call(
        ben,
        tpl_tasks,
        "POST",
        tasks,
        json_body={
            "title": "Design login page",
            "description": "Wireframes and copy",
            "priority": "high",
            "due_date": "2099-12-31",
            "assignee_id": cy_id,
        },
        expect=201,
    )
    tid = made.json()["data"]["id"]
    overdue = ben.post(
        tasks,
        json={
            "title": "Fix signup bug",
            "priority": "medium",
            "due_date": "2020-01-01",
            "assignee_id": ben_id,
        },
        headers=csrf(ben),
    ).json()["data"]["id"]
    doomed = ben.post(tasks, json={"title": "Throwaway idea"}, headers=csrf(ben)).json()["data"][
        "id"
    ]
    running = ben.post(
        tasks, json={"title": "Build API", "status": "in_progress"}, headers=csrf(ben)
    ).json()["data"]["id"]

    call(
        ben,
        tpl_tasks,
        "GET",
        tasks,
        params={"priority": "high", "sort": "due_date", "limit": 5},
        expect=200,
    )
    call(cy, f"{api}/tasks/{{task_id}}", "GET", f"{api}/tasks/{tid}", expect=200)
    call(dan, f"{api}/tasks/{{task_id}}", "GET", f"{api}/tasks/{tid}", kind="error", expect=404)
    call(
        ana,
        f"{api}/tasks/{{task_id}}",
        "PATCH",
        f"{api}/tasks/{tid}",
        kind="error",
        json_body={"title": "Hijacked"},
        expect=403,
    )
    call(
        ben,
        f"{api}/tasks/{{task_id}}",
        "PATCH",
        f"{api}/tasks/{tid}",
        json_body={"priority": "medium", "due_date": "2099-06-30"},
        expect=200,
    )

    status_tpl = f"{api}/tasks/{{task_id}}/status"
    call(
        ben,
        status_tpl,
        "PATCH",
        f"{api}/tasks/{tid}/status",
        kind="error",
        json_body={"status": "completed"},
        expect=422,
    )
    call(
        ben,
        status_tpl,
        "PATCH",
        f"{api}/tasks/{tid}/status",
        json_body={"status": "in_progress"},
        expect=200,
    )
    assert (
        cy.patch(
            f"{api}/tasks/{tid}/status", json={"status": "completed"}, headers=csrf(cy)
        ).status_code
        == 200
    )

    call(
        ana,
        f"{api}/tasks/{{task_id}}",
        "DELETE",
        f"{api}/tasks/{running}",
        kind="error",
        expect=403,
    )
    call(ana, f"{api}/tasks/{{task_id}}", "DELETE", f"{api}/tasks/{doomed}", expect=204)

    # -- dashboard and activity ---------------------------------------
    call(ana, f"{api}/dashboard/stats", "GET", f"{api}/dashboard/stats", expect=200)
    call(
        ana,
        f"{api}/dashboard/activity",
        "GET",
        f"{api}/dashboard/activity",
        params={"page": 1, "limit": 3},
        expect=200,
    )
    call(
        ana,
        f"{api}/projects/{{project_id}}/activity",
        "GET",
        f"{api}/projects/{pid}/activity",
        params={"limit": 3},
        expect=200,
    )
    call(
        dan,
        f"{api}/projects/{{project_id}}/activity",
        "GET",
        f"{api}/projects/{pid}/activity",
        kind="error",
        expect=404,
    )

    # -- member removal, project deletion, logout ---------------------
    call(
        ana,
        f"{api}/projects/{{project_id}}/members/{{user_id}}",
        "DELETE",
        f"{api}/projects/{pid}/members/{ana_id}",
        kind="error",
        expect=422,
    )
    call(
        ana,
        f"{api}/projects/{{project_id}}/members/{{user_id}}",
        "DELETE",
        f"{api}/projects/{pid}/members/{cy_id}",
        expect=204,
    )
    call(
        ben,
        f"{api}/projects/{{project_id}}",
        "DELETE",
        f"{api}/projects/{pid}",
        kind="error",
        expect=403,
    )
    call(ana, f"{api}/projects/{{project_id}}", "DELETE", f"{api}/projects/{pid}", expect=204)
    call(ana, f"{api}/auth/logout", "POST", f"{api}/auth/logout", expect=204)
    call(new_client(), f"{api}/health", "GET", f"{api}/health", expect=200, anonymous=True)
    assert overdue and ana_id
    return rec.calls


# --------------------------------------------------------------------------------------------
# Normalizing and shaping the captured data
# --------------------------------------------------------------------------------------------


def normalize(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace random UUIDs and real timestamps with stable ones, consistently everywhere."""
    ids: dict[str, str] = {}
    times: dict[str, str] = {}

    def fix_id(match: re.Match[str]) -> str:
        ids.setdefault(match.group(0), f"00000000-0000-4000-8000-{len(ids) + 1:012d}")
        return ids[match.group(0)]

    def fix_time(match: re.Match[str]) -> str:
        if match.group(0) not in times:
            second = len(times)
            times[match.group(0)] = f"2026-11-15T10:{second // 60:02d}:{second % 60:02d}Z"
        return times[match.group(0)]

    def walk(value: Any) -> Any:
        if isinstance(value, str):
            return TIME_RE.sub(fix_time, UUID_RE.sub(fix_id, value))
        if isinstance(value, list):
            return [walk(v) for v in value]
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        return value

    return [walk(call) for call in calls]


def build_examples(calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Group calls by endpoint: the first success and the first error example of each."""
    examples: dict[str, Any] = OrderedDict()
    for call in calls:
        key = call["key"]
        entry = examples.setdefault(key, {})
        if call["kind"] in entry:
            continue
        if "request" not in entry or call["kind"] == "success":
            entry["request"] = {
                "method": key.split(" ", 1)[0],
                "path": call["request"]["path"]
                + (("?" + _query(call["request"]["params"])) if call["request"]["params"] else ""),
                "body": call["request"]["body"],
                "authenticated": call["request"]["authenticated"],
                "csrf": call["request"]["csrf"],
            }
        entry[call["kind"]] = {
            "status": call["status"],
            "body": call["body"],
            "set_cookie": call["set_cookie"],
        }
    # JSON keys must be "METHOD /api/v1/{template}" as in OpenAPI paths
    return {k: examples[k] for k in sorted(examples)}


def _query(params: dict[str, Any]) -> str:
    return "&".join(f"{k}={v}" for k, v in params.items())


# --------------------------------------------------------------------------------------------
# Rendering the endpoint reference
# --------------------------------------------------------------------------------------------

REASONS = {
    200: "OK",
    201: "Created",
    204: "No Content",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    422: "Unprocessable Content",
}


def render_example(key: str, example: dict[str, Any]) -> str:
    request = example["request"]
    lines = [f"{request['method']} {request['path']} HTTP/1.1"]
    if request["body"] is not None:
        lines.append("Content-Type: application/json")
    if request["authenticated"]:
        cookie = "access_token=<access-token-jwt>"
        if key.endswith(("/auth/refresh", "/auth/logout")):
            cookie = "refresh_token=<refresh-token-jwt>"
        if request["csrf"]:
            cookie += "; csrf_token=<csrf-token>"
        lines.append(f"Cookie: {cookie}")
    if request["csrf"]:
        lines.append("X-CSRF-Token: <csrf-token>")
    text = "\n".join(lines)
    if request["body"] is not None:
        text += "\n\n" + json.dumps(request["body"], indent=2)
    return text


def render_response(sample: dict[str, Any]) -> str:
    status = sample["status"]
    lines = [f"HTTP/1.1 {status} {REASONS.get(status, '')}".rstrip()]
    lines += sample.get("set_cookie", [])
    text = "\n".join(lines)
    if sample["body"] is not None:
        text += "\n\n" + json.dumps(sample["body"], indent=2)
    return text


def base_errors(endpoint: dict[str, Any]) -> E:
    method, path = endpoint["key"].split(" ", 1)
    rows: E = []
    protected = not endpoint["auth"].startswith("Public")
    if protected and "refresh" not in endpoint["auth"]:
        rows.append(
            (
                401,
                "UNAUTHENTICATED",
                "Missing, invalid or expired access token, or the user is inactive.",
            )
        )
    if method in {"POST", "PATCH", "DELETE"} and protected:
        rows.append(
            (403, "FORBIDDEN", "Missing or wrong `X-CSRF-Token` header, or a disallowed `Origin`.")
        )
    if endpoint["auth"].startswith("Public") and method == "POST":
        rows.append((403, "FORBIDDEN", "A disallowed `Origin` header."))
    if (
        endpoint["request"] not in (None, "None.", "None (no body).")
        or endpoint["query"]
        or "{" in path
    ):
        rows.append(
            (
                422,
                "VALIDATION_ERROR",
                "Malformed or invalid path id, query or body; unknown body fields are rejected.",
            )
        )
    return rows


def render_endpoint(endpoint: dict[str, Any], example: dict[str, Any], number: str) -> str:
    key = endpoint["key"]
    method, path = key.split(" ", 1)
    out = [
        f"#### {number} {method} {path}",
        "",
        f"**Authentication:** {endpoint['auth']}",
        "",
        f"**Authorization policy:** {endpoint['authz']}",
        "",
    ]

    out.append("**Query parameters**")
    if endpoint["query"]:
        out += ["", "| Name | Type | Description |", "|---|---|---|"]
        out += [f"| `{n}` | {t} | {d} |" for n, t, d in endpoint["query"]]
    else:
        out += ["", "None."]
    out += [
        "",
        f"**Request body:** {endpoint['request'] or 'None.'}",
        "",
        f"**Response:** {endpoint['response']}",
        "",
        "**Error responses**",
        "",
        "| Status | Code | When |",
        "|---|---|---|",
    ]
    seen: set[tuple[int, str, str]] = set()
    for status, code, when in sorted(base_errors(endpoint) + endpoint["errors"]):
        if (status, code, when) not in seen:
            seen.add((status, code, when))
            out.append(f"| {status} | `{code}` | {when} |")
    out += [
        "",
        "**Example request**",
        "",
        "```http",
        render_example(key, example),
        "```",
        "",
        "**Example response**",
        "",
        "```http",
        render_response(example["success"]),
        "```",
    ]
    if "error" in example:
        out += [
            "",
            f"**Example error response** ({example['error']['status']})",
            "",
            "```http",
            render_response(example["error"]),
            "```",
        ]
    if endpoint["rules"]:
        out += ["", "**Rules**", ""] + [f"- {rule}" for rule in endpoint["rules"]]
    return "\n".join(out)


def _short_auth(auth: str) -> str:
    return (
        auth.replace(" (no authentication)", "")
        .replace("Access-token cookie (`access_token`)", "Access token")
        .replace("Access-token cookie + `X-CSRF-Token` header", "Access token + CSRF")
        .replace(
            "Refresh-token cookie (`refresh_token`) + `X-CSRF-Token` header", "Refresh token + CSRF"
        )
    )


def _short_authz(authz: str) -> str:
    """First sentence (a full stop followed by a space or the end), policy names keep their dots."""
    first = re.split(r"\.(?:\s|$)", authz, maxsplit=1)[0]
    return first.rstrip(".")


def render_reference(examples: dict[str, Any]) -> str:
    groups: dict[str, list[dict[str, Any]]] = OrderedDict()
    for endpoint in ENDPOINTS:
        groups.setdefault(endpoint["group"], []).append(endpoint)

    out = [
        "## 3. Endpoint reference",
        "",
        "Every endpoint is documented with the same fields. Placeholders such as "
        "`<access-token-jwt>` stand for real cookie values. Identifiers and timestamps in "
        "the examples are normalized; everything else is real output of the running API "
        "(this section is generated by `backend/scripts/generate_api_docs.py`).",
        "",
        "| # | Method and path | Authentication | Authorization policy |",
        "|---|---|---|---|",
    ]
    for index, endpoint in enumerate(ENDPOINTS, start=1):
        method, path = endpoint["key"].split(" ", 1)
        out.append(
            f"| {index} | `{method} {path}` | {_short_auth(endpoint['auth'])} "
            f"| {_short_authz(endpoint['authz'])} |"
        )
    out.append("")
    for section, (group, endpoints) in enumerate(groups.items(), start=1):
        out += [f"### 3.{section} {group}", ""]
        for number, endpoint in enumerate(endpoints, start=1):
            out += [
                render_endpoint(endpoint, examples[endpoint["key"]], f"3.{section}.{number}"),
                "",
            ]
    return "\n".join(out).rstrip() + "\n\n"


def splice_contract(reference: str) -> str:
    text = CONTRACT_FILE.read_text()
    start = text.index("## 3. ")
    end = text.index("## 4. Status code summary")
    return text[:start] + reference + text[end:]


# --------------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------------


def prepare_environment() -> None:
    from dotenv import dotenv_values

    env = dotenv_values(BACKEND / ".env")
    url = env.get("TEST_DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if not url or not url.rsplit("/", 1)[-1].split("?")[0].endswith("_test"):
        sys.exit("TEST_DATABASE_URL must be set and name a database ending in '_test'.")
    os.environ.update(
        {
            "DATABASE_URL": url,
            "ENVIRONMENT": "test",
            "LOG_LEVEL": "CRITICAL",
            "COOKIE_SECURE": "false",
            "ALLOWED_ORIGINS": "http://localhost:3000",
        }
    )
    if env.get("JWT_SECRET_KEY"):
        os.environ.setdefault("JWT_SECRET_KEY", str(env["JWT_SECRET_KEY"]))


def truncate_everything() -> None:
    from sqlalchemy import text

    from app.database.session import get_engine

    with get_engine().begin() as connection:
        connection.execute(
            text(
                "TRUNCATE activity_logs, refresh_tokens, tasks, project_members, projects, users "
                "RESTART IDENTITY CASCADE"
            )
        )


def main() -> None:
    sys.path.insert(0, str(BACKEND))
    prepare_environment()
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")

    truncate_everything()
    try:
        calls = normalize(run_scenario())
    finally:
        truncate_everything()

    examples = build_examples(calls)
    missing = [
        e["key"]
        for e in ENDPOINTS
        if e["key"] not in examples or "success" not in examples[e["key"]]
    ]
    if missing:
        sys.exit(f"No success example captured for: {missing}")
    EXAMPLES_FILE.write_text(json.dumps(examples, indent=2) + "\n")

    from app.main import create_app  # a fresh app now serves the examples inside OpenAPI

    OPENAPI_FILE.write_text(json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n")
    CONTRACT_FILE.write_text(splice_contract(render_reference(examples)))
    print(
        "wrote "
        + ", ".join(
            str(f.relative_to(BACKEND.parent)) for f in (EXAMPLES_FILE, OPENAPI_FILE, CONTRACT_FILE)
        )
        + f" ({len(examples)} endpoints)"
    )


if __name__ == "__main__":
    main()
