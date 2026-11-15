# FinTasks frontend API contract (discovered from the running backend)

> Generated on 2026-11-15 by inspecting the existing backend. Nothing was modified in `backend/`.
> Source of truth for the frontend types. It describes what the backend DOES, not what the earlier
> design docs planned. Where this file and `docs/api-contract.md` agree, the latter has more examples.

**Evidence tags** used below: `[live]` = observed on the running server at `http://localhost:8000`
with `curl`; `[openapi]` = operation in `GET /openapi.json` (live document is byte-identical to
`docs/openapi.json`, checked with a JSON comparison); `[code: file]` = read from source;
`[in-process]` = observed by calling the same app with Starlette's `TestClient` against the **test**
database (used for cookie attributes, so the development database was never written to).

## 1. Connectivity

| Item | Finding | Evidence |
|---|---|---|
| Backend origin | `http://localhost:8000` (uvicorn, also reachable as `127.0.0.1:8000`) | [live] `lsof` shows python on 8000; health returned 200 on both hosts |
| API prefix | `/api/v1` | [openapi] all 23 paths; [code: `app/api/router.py`, `app/api/v1/router.py`] |
| Health | `GET /api/v1/health` returns `200 {"data": {"status": "ok"}}`. Liveness only, does not touch the database. | [live]; [openapi] `health_api_v1_health_get`; decision D13 |
| Swagger UI | `GET /docs` returns 200 | [live] |
| OpenAPI | `GET /openapi.json` returns 200, OpenAPI 3.1, 23 operations | [live] |
| Response headers on every API reply | `x-request-id`, `x-content-type-options: nosniff`, `referrer-policy: no-referrer`, `cache-control: no-store` | [live]; [code: `app/core/middleware.py`] |
| Database | PostgreSQL container `fintasks-db` on host port 5433 | [live] `podman ps` |
| Port 3000 | **Already taken by an unrelated container named `resume-matcher`** (a Next.js app). `frontend/` does not exist yet. | [live] `podman ps`, `curl localhost:3000` returned Next.js headers |

## 2. Authentication

**Mechanism: HttpOnly cookies. There are no Bearer tokens and no tokens in response bodies.**
[code: `app/core/cookies.py`, `app/auth/dependencies.py`], [openapi] `components.securitySchemes`:
`accessTokenCookie`, `refreshTokenCookie`, `csrfHeader`.

### 2.1 Cookies set by register, login and refresh
Attributes observed [in-process] with `COOKIE_SECURE=false`, `SameSite=lax`, no domain (test settings; the same
defaults are in `app/core/config.py` lines 57 to 59):

| Cookie | HttpOnly | Max-Age | Path | SameSite | Purpose |
|---|---|---|---|---|---|
| `access_token` | yes | 900 (15 min) | `/` | lax | JWT sent automatically to every API call |
| `refresh_token` | yes | 604800 (7 days) | `/api/v1/auth` | lax | JWT sent only to `/api/v1/auth/*` |
| `csrf_token` | **no** (readable by JavaScript) | 604800 | `/` | lax | Value to echo in `X-CSRF-Token` |

`Secure` is added when `COOKIE_SECURE=true` (required in production; `app/core/config.py` line 121 refuses to start otherwise).
Cookies are host-only (no `Domain`). Cookie values are never shown in this file.
Logout expires all three (`Max-Age=0`) [in-process]. Refresh replaces all three (rotation) [in-process].

### 2.2 CSRF rules [code: `app/core/csrf.py`], [live] error text
1. Safe methods (GET, HEAD, OPTIONS) are never checked.
2. Any other request that carries an `Origin` header must have an origin in `ALLOWED_ORIGINS` (default `http://localhost:3000`) or the API's own origin, otherwise `403 FORBIDDEN "Request origin is not allowed."`
3. Any POST, PATCH, PUT or DELETE that carries `access_token` or `refresh_token` cookies, except `/api/v1/auth/login` and `/api/v1/auth/register`, must send header `X-CSRF-Token` equal to the `csrf_token` cookie. Otherwise `403 FORBIDDEN "CSRF token missing or invalid."`
4. This includes **`POST /auth/refresh` and `POST /auth/logout`** ([openapi] lists `csrfHeader` on both).

Frontend rule: read `document.cookie` for `csrf_token` on each unsafe request and send it as `X-CSRF-Token`. Always send `credentials: "include"` when calling the backend directly from another origin.

### 2.3 Flow
1. `POST /auth/register` or `POST /auth/login` returns `{"data": UserOut}` and sets the three cookies. Registration also logs the user in [in-process: 201 and three Set-Cookie headers].
2. Protected calls: browser sends `access_token` automatically. Missing, expired or tampered token returns `401 UNAUTHENTICATED` [live: `GET /auth/me` without cookie].
3. On a 401 (not from login), call `POST /auth/refresh` once with the CSRF header, then retry the original request once. Refresh returns `{"data": UserOut}` and sets rotated cookies. A reused or invalid refresh token returns 401 and revokes the whole token family [code: `app/services/auth_service.py` `refresh`, decision D7].
4. If refresh returns 401, redirect to `/login`.
5. `POST /auth/logout` returns 204 and clears cookies. It also returns 204 with no session (idempotent), so it never reports 401 [openapi: responses 204, 403, 422].
6. `GET /auth/me` returns the current user and is the way to check session state on page load.

### 2.4 Schemas
- `RegisterIn { name: string (1..120), email: email (max 255), password: string (8..128) }`
- `LoginIn { email: email (max 255), password: string (1..128) }`
- `UserOut { id: uuid, email: string, name: string }`
- All three auth success responses use `{ "data": UserOut }`. The CSRF token and JWTs are **not** in the body.
- Failures: login wrong password returns `401 UNAUTHENTICATED "Invalid email or password."` [in-process]. Duplicate email on register returns `409 CONFLICT`. Both documented in [openapi].

Request body (POST /api/v1/auth/register):
```json
{
  "name": "Ana Lopez",
  "email": "ana@example.com",
  "password": "correct-horse-battery"
}
```

Response:
```json
{
  "data": {
    "id": "00000000-0000-4000-8000-000000000001",
    "email": "ana@example.com",
    "name": "Ana Lopez"
  }
}
```

## 3. Endpoint table (all 23, [openapi] unless noted)

Auth column: `none` = public. `access` = needs access cookie. `access+csrf` = also needs `X-CSRF-Token`. `refresh+csrf` = refresh cookie + CSRF.
"PBAC" = who is allowed (enforced in services through `AuthorizationService.require`, `app/authorization/policies.json`).
Listed error statuses are exactly those declared in OpenAPI (plus 401/403 from the middleware described above).

| # | Method and path | operationId | Auth | Request | Success | Errors |
|---|---|---|---|---|---|---|
| 1 | GET `/health` | health_api_v1_health_get | none | | 200 `HealthOut` | |
| 2 | POST `/auth/register` | register_api_v1_auth_register_post | none | `RegisterIn` | 201 `UserOut` | 403 origin, 409, 422 |
| 3 | POST `/auth/login` | login_api_v1_auth_login_post | none | `LoginIn` | 200 `UserOut` | 401, 403 origin, 422 |
| 4 | POST `/auth/refresh` | refresh_api_v1_auth_refresh_post | refresh+csrf | none | 200 `UserOut` | 401, 403 |
| 5 | POST `/auth/logout` | logout_api_v1_auth_logout_post | refresh+csrf | none | 204 | 403 |
| 6 | GET `/auth/me` | me_api_v1_auth_me_get | access | | 200 `UserOut` | 401 |
| 7 | POST `/projects` | create_project_api_v1_projects_post | access+csrf | `ProjectCreate` | 201 `ProjectDetailOut` | 401, 403, 422 |
| 8 | GET `/projects` | list_projects_api_v1_projects_get | access | query: `q`, `status`, `page`, `page_size`, `limit` | 200 paged `ProjectOut` | 401, 422 |
| 9 | GET `/projects/{project_id}` | get_project_api_v1_projects__project_id__get | access | | 200 `ProjectDetailOut` | 401, 404 |
| 10 | PATCH `/projects/{project_id}` | update_project_... | access+csrf | `ProjectUpdate` | 200 `ProjectDetailOut` | 401, 403, 404, 422 |
| 11 | DELETE `/projects/{project_id}` | delete_project_... | access+csrf | | 204 | 401, 403, 404 |
| 12 | GET `/projects/{project_id}/members` | list_members_... | access | | 200 `MemberOut[]` (not paged) | 401, 404 |
| 13 | POST `/projects/{project_id}/members` | add_member_... | access+csrf | `MemberCreate` (`email` or `user_id`) | 201 `MemberOut` | 401, 403, 404, 409, 422 |
| 14 | DELETE `/projects/{project_id}/members/{user_id}` | remove_member_... | access+csrf | | 204 | 401, 403, 404, 422 (owner cannot be removed) |
| 15 | POST `/projects/{project_id}/tasks` | create_task_... | access+csrf | `TaskCreate` | 201 `TaskOut` | 401, 403, 404, 422 |
| 16 | GET `/projects/{project_id}/tasks` | list_tasks_... | access | query: see 5.2 | 200 paged `TaskOut` | 401, 404, 422 |
| 17 | GET `/tasks/{task_id}` | get_task_... | access | | 200 `TaskOut` | 401, 404 |
| 18 | PATCH `/tasks/{task_id}` | update_task_... | access+csrf | `TaskUpdate` | 200 `TaskOut` | 401, 403, 404, 422 |
| 19 | PATCH `/tasks/{task_id}/status` | change_task_status_... | access+csrf | `TaskStatusUpdate` | 200 `TaskOut` | 401, 403, 404, 422 |
| 20 | DELETE `/tasks/{task_id}` | delete_task_... | access+csrf | | 204 | 401, 403, 404 |
| 21 | GET `/dashboard/stats` | dashboard_stats_... | access | | 200 `DashboardStats` | 401 |
| 22 | GET `/dashboard/activity` | dashboard_activity_... | access | `page`, `page_size`, `limit` | 200 paged `ActivityOut` | 401, 422 |
| 23 | GET `/projects/{project_id}/activity` | project_activity_... | access | `page`, `page_size`, `limit` | 200 paged `ActivityOut` | 401, 404, 422 |

All paths are prefixed with `/api/v1`. Path ids are UUIDs; a malformed UUID returns 422.

## 4. Response envelopes [code: `app/schemas/common.py`], [openapi]
- Single or list: `{ "data": ... }`
- Paged: `{ "data": [...], "meta": { "page", "page_size", "total", "total_pages" } }`
- 204 responses have no body.
- Member list is a plain `{ "data": MemberOut[] }` with no `meta`.

## 5. Behavior the UI depends on

### 5.1 Projects
- Visible only to members. A non-member gets **404, never 403**, including for the project's tasks, members and activity.
- The creator is the owner and an automatic member. The client never sends an owner. `owner_id` is not accepted.
- Owner-only: update, delete, add or remove members. Owner cannot be removed (422 `BUSINESS_RULE_VIOLATION`).
- `ProjectCreate { name (1..120), description? (max 5000), status? }`, `ProjectUpdate` has the same optional fields, `status` is `active` or `archived`.
- `MemberCreate { email? , user_id? }`: the user must already be registered. Adding the same user again returns 409.
- `ProjectOut` fields: `id, name, description, status, owner, member_count, task_counts {todo,in_progress,completed}, allowed_actions, created_at, updated_at`. `ProjectDetailOut` adds `members: MemberOut[]`.
- `allowed_actions` on projects: any of `update`, `delete`, `manage_members`, `create_task`. **The UI must use this list to show or hide controls.**
- Query for the list: `q` (max 100, name contains), `status` (`active` or `archived`, single value), `page` (1..100000, default 1), `page_size` or `limit` (1..100, default 20; if both are sent they must be equal).

Request body (POST /api/v1/projects):
```json
{
  "name": "Website redesign",
  "description": "Q4 launch"
}
```

Response:
```json
{
  "data": {
    "id": "00000000-0000-4000-8000-000000000005",
    "name": "Website redesign",
    "description": "Q4 launch",
    "status": "active",
    "owner": {
      "id": "00000000-0000-4000-8000-000000000001",
      "email": "ana@example.com",
      "name": "Ana Lopez"
    },
    "member_count": 1,
    "task_counts": {
      "todo": 0,
      "in_progress": 0,
      "completed": 0
    },
    "allowed_actions": [
      "update",
      "delete",
      "manage_members",
      "create_task"
    ],
    "created_at": "2026-11-15T10:00:00Z",
    "updated_at": "2026-11-15T10:00:00Z",
    "members": [
      {
        "user": {
          "id": "00000000-0000-4000-8000-000000000001",
          "email": "ana@example.com",
          "name": "Ana Lopez"
        },
        "is_owner": true,
        "joined_at": "2026-11-15T10:00:00Z"
      }
    ]
  }
}
```

### 5.2 Tasks
- `TaskCreate { title (1..200), description?, priority? (default `medium`), status? (default `todo`), assignee_id?, due_date? (YYYY-MM-DD) }`. The creator comes from the cookie.
- `TaskUpdate { title?, description?, priority?, assignee_id?, due_date? }`. **`status` and `position` are not accepted here.** Sending status returns 422.
- **Status change is a separate endpoint:** `PATCH /tasks/{id}/status` with `TaskStatusUpdate { status, position? }`. `position` (number) is the only way to set board order and is what drag and drop will send.
- Status values: `todo`, `in_progress`, `completed`. Priority values: `low`, `medium`, `high`.
- Transitions only along the line `todo <-> in_progress <-> completed`. `todo -> completed` returns 422. [code: `app/services/task_service.py`; requirement A22]
- Completing requires an assignee, title, description, priority and due date (policy `task-complete`), otherwise 422/403 with a `details[].policy_id`.
- Assignee must be a current project member (422 `BUSINESS_RULE_VIOLATION` otherwise).
- Update allowed for the task's creator or assignee only. Delete allowed only for the project owner and only when status is `todo` (403 otherwise).
- `TaskOut`: `id, project_id, title, description, status, priority, assignee (UserOut|null), creator, due_date, position, completed_at, allowed_actions (update|delete|complete), created_at, updated_at`.
- List query: `q` (title or description contains), `status` (**repeatable**, e.g. `?status=todo&status=in_progress`), `priority` (repeatable), `assignee_id` (a UUID or the literal `unassigned`), `due_after`, `due_before` (dates, inclusive), `overdue` (boolean), `sort` (one of `created_at`, `-created_at` (default), `updated_at`, `-updated_at`, `due_date`, `-due_date`, `priority`, `-priority`, `position`), `page`, `page_size`/`limit`.

Request body (POST /api/v1/projects/{project_id}/tasks):
```json
{
  "title": "Design login page",
  "description": "Wireframes and copy",
  "priority": "high",
  "due_date": "2099-12-31",
  "assignee_id": "00000000-0000-4000-8000-000000000009"
}
```

Response:
```json
{
  "data": {
    "id": "00000000-0000-4000-8000-000000000014",
    "project_id": "00000000-0000-4000-8000-000000000005",
    "title": "Design login page",
    "description": "Wireframes and copy",
    "status": "todo",
    "priority": "high",
    "assignee": {
      "id": "00000000-0000-4000-8000-000000000009",
      "email": "cy@example.com",
      "name": "Cy Dunn"
    },
    "creator": {
      "id": "00000000-0000-4000-8000-000000000007",
      "email": "ben@example.com",
      "name": "Ben Carter"
    },
    "due_date": "2099-12-31",
    "position": 1024.0,
    "completed_at": null,
    "allowed_actions": [
      "update",
      "complete"
    ],
    "created_at": "2026-11-15T10:00:04Z",
    "updated_at": "2026-11-15T10:00:04Z"
  }
}
```

Status change response:
```json
{
  "data": {
    "id": "00000000-0000-4000-8000-000000000014",
    "project_id": "00000000-0000-4000-8000-000000000005",
    "title": "Design login page",
    "description": "Wireframes and copy",
    "status": "in_progress",
    "priority": "medium",
    "assignee": {
      "id": "00000000-0000-4000-8000-000000000009",
      "email": "cy@example.com",
      "name": "Cy Dunn"
    },
    "creator": {
      "id": "00000000-0000-4000-8000-000000000007",
      "email": "ben@example.com",
      "name": "Ben Carter"
    },
    "due_date": "2099-06-30",
    "position": 2048.0,
    "completed_at": null,
    "allowed_actions": [
      "update",
      "complete"
    ],
    "created_at": "2026-11-15T10:00:04Z",
    "updated_at": "2026-11-15T10:00:06Z"
  }
}
```

### 5.3 Dashboard and activity
- `GET /dashboard/stats` returns `DashboardStats { total_projects, active_projects, total_tasks, completed_tasks, pending_tasks, overdue_tasks, assigned_to_me, recent_activity: ActivityOut[] }` (counts only the user's projects; definitions in `docs/requirements.md`).
- `ActivityOut { id, user: UserOut, project_id|null, task_id|null, action, metadata (free-form object), created_at }`.
- `GET /dashboard/activity` is the activity of **every project the caller currently belongs to, by any member**, newest first. It is not limited to the caller's own actions, and it never contains authentication events (they have no project) [code: `app/repositories/activity_repository.py` `ActivityQueries.for_member`; verified live on 2026-11-16]. `GET /projects/{id}/activity` is one project's timeline (members only, 404 otherwise). Both order by `created_at` descending, then `id` descending.
- **Correction:** an earlier version of this file said `/dashboard/activity` was "the caller's own feed (includes auth events)". That was wrong.
- `action` values: `user.registered, auth.login, auth.logout, auth.refresh_reuse_detected, project.created, project.updated, project.deleted, member.added, member.removed, task.created, task.updated, task.status_changed, task.assigned, task.unassigned, task.deleted` [code: `app/models/enums.py` `ActivityAction`]. The `action` field is typed as plain `string` in OpenAPI, so the union must be kept in the frontend by hand.
- `metadata` keys vary by action. Treat it as `Record<string, unknown>`. Keys written by the backend services:

| action | metadata |
|---|---|
| `project.created` | `name` |
| `project.updated` | `changes: { field: [old, new] }` (name, description, status) |
| `project.deleted` | `name`, `member_count`, `task_count` |
| `member.added` | `member_user_id` |
| `member.removed` | `member_user_id`, `unassigned_task_count` |
| `task.created` | `title`, `status`, `priority`, `assignee_id` |
| `task.updated` | `changes: { field: [old, new] }` (title, description, priority, due_date) |
| `task.status_changed` | `from`, `to`, `position` (no title) |
| `task.assigned` | `assignee_id`, `previous_assignee_id` |
| `task.unassigned` | `previous_assignee_id`, or `reason: "member_removed"` and `former_assignee_id` |
| `task.deleted` | `title`, `status` |

Stats example (truncated):
```json
{
  "data": {
    "total_projects": 1,
    "active_projects": 1,
    "total_tasks": 3,
    "completed_tasks": 1,
    "pending_tasks": 2,
    "overdue_tasks": 1,
    "assigned_to_me": 0,
    "recent_activity": [
      {
        "id": "00000000-0000-4000-8000-000000000021",
        "user": {
          "id": "00000000-0000-4000-8000-000000000001",
          "email": "ana@example.com",
          "name": "Ana Lopez"
        },
        "project_id": "00000000-0000-4000-8000-000000000005",
        "task_id": "00000000-0000-4000-8000-000000000020",
        "action": "task.deleted",
        "metadata": {
          "title": "Throwaway idea",
          "status": "todo"
        },
        "created_at": "2026-11-15T10:00:07Z"
      },
      {
        "id": "00000000-0000-4000-8000-000000000022",
        "user": {
          "id": "00000000-0000-4000-8000-000000000009",
          "email": "cy@example.c
```

## 6. Error format [code: `app/core/exceptions.py`], [live] 401 body
```json
{ "error": { "code": "UNAUTHENTICATED", "message": "Authentication is missing, invalid or expired.", "details": [], "request_id": "..." } }
```
`details` items: `{ field: string|null, message: string, policy_id: string|null }`. `request_id` equals the `X-Request-ID` response header (exposed to browsers by CORS).

| HTTP | `code` | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | no, expired or invalid token; wrong login |
| 403 | `FORBIDDEN` | policy denial (`details[0].policy_id` is set), CSRF failure, disallowed origin |
| 404 | `NOT_FOUND` | missing resource or a project the user is not a member of |
| 409 | `CONFLICT` | duplicate email, duplicate member |
| 422 | `VALIDATION_ERROR` | schema validation, `details[].field` is the field name |
| 422 | `BUSINESS_RULE_VIOLATION` | assignee not a member, invalid status jump, owner removal |
| 405 | `METHOD_NOT_ALLOWED` | wrong method |
| 500 | `INTERNAL_ERROR` | unexpected; generic message plus `request_id` |

CSRF failures and 401s share the same envelope but CSRF returns 403 with message `CSRF token missing or invalid.`; the UI should special-case that message by refetching or re-logging in.

Example 422:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "details": [
      {
        "field": "name",
        "message": "String should have at least 1 character",
        "policy_id": null
      }
    ],
    "request_id": "00000000-0000-4000-8000-000000000006"
  }
}
```

## 7. CORS [code: `app/core/middleware.py` `register_middleware`], [live] preflights
- `allow_origins` = `ALLOWED_ORIGINS` (default and current behavior: `http://localhost:3000`), explicit list, never `*`.
- `allow_credentials=true`; methods GET, POST, PUT, PATCH, DELETE, OPTIONS; request headers `Content-Type`, `X-CSRF-Token`, `X-Request-ID`; exposed header `X-Request-ID`; preflight cache 600 s.
- [live] Preflight `OPTIONS /api/v1/projects` from `Origin: http://localhost:3000` with `Access-Control-Request-Headers: content-type,x-csrf-token` returned **200** with `access-control-allow-origin: http://localhost:3000`, `access-control-allow-credentials: true` and the allowed headers.
- [live] The same preflight from `http://evil.example` returned **400** with no `allow-origin` header.
- [live] A GET with `Origin: http://localhost:3000` returns `access-control-allow-origin: http://localhost:3000`.
- Conclusion: **a frontend at `http://localhost:3000` can call `http://localhost:8000` directly** with `credentials: "include"`. `http://127.0.0.1:3000` would NOT be allowed. Mixing `localhost` and `127.0.0.1` also breaks cookies.
- Not verified: behavior in a real browser (no browser available here). Standard cookie rules (RFC 6265) do not isolate cookies by port, so `localhost:3000` JavaScript should be able to read the `csrf_token` cookie set by `localhost:8000`. Confirm this in the first frontend smoke test.
- Architecture file preference: a Next.js rewrite proxy (`/api/*` to the backend) so the browser sees one origin. That avoids CORS and the cookie-port question altogether. It does not exist yet (no `frontend/`).

## 8. Data models and enums
| Name | Values |
|---|---|
| `ProjectStatus` | `active`, `archived` |
| `TaskStatus` | `todo`, `in_progress`, `completed` |
| `TaskPriority` | `low`, `medium`, `high` |
| `TaskSort` | `created_at`, `-created_at`, `updated_at`, `-updated_at`, `due_date`, `-due_date`, `priority`, `-priority`, `position` |
| project `allowed_actions` | `update`, `delete`, `manage_members`, `create_task` |
| task `allowed_actions` | `update`, `delete`, `complete` |

Other models are listed in sections 2.4, 5.1, 5.2 and 5.3. Full field-by-field JSON Schemas: `docs/openapi.json` `components.schemas` (this is what frontend types should be generated or checked against).
Timestamps are UTC ISO 8601 with `Z`; `due_date` is a plain `YYYY-MM-DD`; `position` is a float.

## 9. Missing, awkward or risky items
| # | Item | Impact | Proposed action |
|---|---|---|---|
| G1 | **Port 3000 is occupied** by the `resume-matcher` container. The assigned origin in `ALLOWED_ORIGINS` is `http://localhost:3000`. | `pnpm dev` will fail or pick another port, which CORS would then reject. | Stop that container, or approve a backend `ALLOWED_ORIGINS` change. Not changed. |
| G2 | No endpoint lists a user's assigned tasks across projects. The dashboard only returns the count `assigned_to_me`. | The dashboard cannot show an "assigned to me" list. | Either show the count only, or approve a contract change (for example `GET /tasks?assignee=me`). |
| G3 | No user search or list endpoint. | Adding a member needs the exact email (`MemberCreate.email`). Assignee choices come from the project's member list. | Acceptable; matches the product scope. |
| G4 | Board order is changed through `PATCH /tasks/{id}/status` (status is required, `position` optional). | Reordering inside one column sends the unchanged status plus a new `position`. Backend test `test_a_task_can_be_reordered_inside_its_column` covers it. | None. Not a gap. |
| G5 | `ActivityOut.action` and `metadata` are untyped in OpenAPI. | Frontend must keep the action union by hand (section 5.3). | Optional later: make `action` an enum in the schema. |
| G6 | The task list `status` and `priority` filters are repeatable query params. | The API client must serialize arrays as repeated keys, not comma lists. | Note for `lib/api.ts`. |
| G7 | Cookie `Secure` and the real `ALLOWED_ORIGINS` value in `backend/.env` were not read (environment files can hold secrets). Cookie attributes were observed on the test configuration. | None expected for local HTTP. | Confirm in the first browser login. |
| G8 | Direct cross-origin calls from `localhost:3000` rely on cookies shared across ports (section 7). | A failure would show as 401 after login. | Prefer the Next.js rewrite proxy as the architecture states. |

### Dashboard-specific gaps (found while building the dashboard)
| # | Missing from the backend | What the dashboard does instead | Limit |
|---|---|---|---|
| G9 | No endpoint lists tasks across projects (this extends G2). Needed for "My assigned tasks" and "Upcoming due dates". | Asks `GET /projects/{id}/tasks` for each project that still has open tasks (`task_counts.todo + in_progress > 0`), at most 10 projects, with server-side filters: `assignee_id=<me>&status=todo&status=in_progress&sort=due_date&page_size=10` and `status=todo&status=in_progress&due_after=<UTC today>&sort=due_date&page_size=5`. Results are merged and sorted by due date in the browser. | With more than 10 projects that have open work, or more matching tasks than one page in a project, the lists are partial. The card says so. The exact count of assigned tasks comes from `assigned_to_me` in the statistics. Up to about 21 requests per dashboard load. |
| G10 | `GET /dashboard/stats` gives `completed_tasks` and `pending_tasks` but not the to do / in progress split. | The status chart sums `task_counts` from `GET /projects?page_size=100`. | Shown only when every project fits in that one page (`meta.total` equals the number returned). Otherwise the card says the breakdown is not available. Never a partial total. |
| G11 | No "due soon" or date-window parameters beyond `due_after` and `due_before`. | Uses `due_after=<today>` and the ascending `due_date` sort (the backend puts tasks without a date last). | Overdue tasks are counted in the statistics but not listed (a list would need `overdue=true` per project, the same fan-out). |
| G12 | `ActivityOut.metadata` keys are not in the schema. | Uses only keys the backend writes: `title` (tasks), `name` (projects), `from` and `to` (status changes). Anything else shows no object name. | Verified against the real backend for task created and status changed events. |

Task completion percentage is computed in the browser as `completed_tasks / total_tasks` from the statistics, rounded to a whole percent, and is shown as a dash when there are no tasks.

A proposed backend addition that would remove G9 and G11 (not implemented, needs approval): `GET /tasks?assignee_id=me&status=...&due_after=...&sort=due_date` returning the same paged `TaskOut` envelope, limited to the caller's projects.

### Activity-specific gaps (found while building the Activity module)
| # | Missing from the backend | What the frontend does instead |
|---|---|---|
| G13 | No feed of the caller's OWN actions, and authentication events (`user.registered`, `auth.*`) are written but no endpoint returns them. | `/activity` shows "activity in your projects" and marks the caller's own entries "You". It does not filter by actor in the browser, because a filtered page of 20 would be incomplete. |
| G14 | Activity rows get `created_at = now()` in PostgreSQL, which is the transaction start time. Events written in one transaction (member removed plus the tasks it unassigned; a task edit plus its reassignment) share a timestamp, and the backend breaks the tie by a random UUID. | The order inside such a group is shown as the backend returns it; the frontend cannot recover the real order. A sequence column or a per-row timestamp would fix it. |
| G15 | Entries carry ids, not names: no project name (except `project.*` metadata), no task title on most task events, no member names. | Names come only from other real responses: the user's project list, the project's member list, the actors of the loaded entries, and titles that newer entries in the same feed reveal. Otherwise the text says "a task", "a member" or "a project". "A project you can no longer open" is used only when the complete project list is loaded. |

No endpoint was found broken. All 23 operations in the live OpenAPI exist, and the live document matches `docs/openapi.json`. The whole backend suite passed (970 tests) at the last run.

## 10. Frontend integration readiness
| Area | Status |
|---|---|
| Backend reachable, health, Swagger, OpenAPI | Ready (live) |
| Auth (cookie flow, CSRF, refresh, logout, `me`) | Ready. Needs the `X-CSRF-Token` rule in `lib/api.ts` |
| Projects and members | Ready |
| Tasks, filters, sort, pagination, status endpoint | Ready |
| Dashboard and activity | Ready, with G2 |
| CORS for `http://localhost:3000` | Ready for direct calls; port 3000 is currently used by another app (G1) |
| Error format | Ready, uniform envelope |
| Blocking items before coding | G1 only. G2 needs a decision when those screens are built |

Unfinished in this task: no frontend code exists (as requested). Nothing here has been tested in a browser.
