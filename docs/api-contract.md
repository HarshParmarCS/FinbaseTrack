# FinTasks: API Contract

Single source of truth for the HTTP API. The backend implements it. The frontend consumes it and must not invent response shapes. Changes go here first (see `.kiro/steering/workflow.md`).

- Base path: `/api/v1`. Health check: `GET /api/v1/health`.
- Format: JSON (`application/json`). Timestamps are UTC ISO 8601 (`2026-11-15T10:30:00Z`). `due_date` is a calendar date (`2026-11-20`). IDs are UUIDs.
- Auth cookies (all `SameSite=Lax`, `Secure` in production):
  - `access_token`: JWT, 15 minutes, `HttpOnly`, path `/`.
  - `refresh_token`: JWT, 7 days, `HttpOnly`, path `/api/v1/auth`.
  - `csrf_token`: random value, 7 days, readable by JavaScript (not `HttpOnly`), path `/`.
  No tokens in bodies. No `Authorization` header.
- CSRF protection for state-changing methods (POST, PUT, PATCH, DELETE), returning 403 `FORBIDDEN`:
  1. If an `Origin` header is present it must be the API's own origin or one of `ALLOWED_ORIGINS`.
  2. If the request carries an `access_token` or `refresh_token` cookie, it must also send the header `X-CSRF-Token` with the same value as the `csrf_token` cookie. Exempt: `POST /auth/login` and `POST /auth/register` (no session exists yet; rule 1 still applies).
- CORS: only `ALLOWED_ORIGINS` are allowed, with credentials. Allowed request headers: `Content-Type`, `X-CSRF-Token`, `X-Request-ID`.
- Client-supplied identity fields (`user_id`, `owner_id`, `creator_id`) are never accepted. Unknown request fields are rejected with 422.

## 1. Envelopes

### Success
```json
{ "data": <object | array | null> }
```
Paginated lists add `meta`:
```json
{
  "data": [ ... ],
  "meta": { "page": 1, "page_size": 20, "total": 57, "total_pages": 3 }
}
```
`204 No Content` responses have no body.

### Error
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "details": [ { "field": "email", "message": "value is not a valid email address" } ],
    "request_id": "b2f3c1d0-..."
  }
}
```
`details` is an array (empty when not applicable). For policy denials, `details` is `[{ "policy_id": "task-delete", "reason": "Task status must be todo." }]`.

### Error codes
| HTTP | `code` | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token; bad login credentials; invalid refresh token |
| 403 | `FORBIDDEN` | Authenticated member denied by a policy; disallowed `Origin`; missing or wrong `X-CSRF-Token` |
| 404 | `NOT_FOUND` | Resource missing, unknown route, or project/task not visible to the user (non-member) |
| 405 | `METHOD_NOT_ALLOWED` | HTTP method not supported on the route |
| 409 | `CONFLICT` | Duplicate email, duplicate member |
| 422 | `VALIDATION_ERROR` | Malformed or invalid input |
| 422 | `BUSINESS_RULE_VIOLATION` | Valid input that breaks a domain rule (assignee not a member, removing the owner) |
| 500 | `INTERNAL_ERROR` | Unexpected error (generic message, request ID included) |

### Pagination parameters (all list endpoints)
`page` (default 1, min 1), `page_size` (default 20, min 1, max 100).

## 2. Shared schemas

```
UserOut        { id, email, name }
MemberOut      { user: UserOut, is_owner: boolean, joined_at }
ProjectOut     { id, name, description: string|null, status: "active"|"archived",
                 owner: UserOut, member_count: int,
                 task_counts: { todo: int, in_progress: int, completed: int },
                 allowed_actions: ProjectAction[], created_at, updated_at }
TaskOut        { id, project_id, title, description: string|null,
                 status: "todo"|"in_progress"|"completed",
                 priority: "low"|"medium"|"high",
                 assignee: UserOut|null, creator: UserOut,
                 due_date: date|null, position: number, completed_at: datetime|null,
                 allowed_actions: TaskAction[], created_at, updated_at }
ActivityOut    { id, user: UserOut, project_id: uuid|null, task_id: uuid|null,
                 action: string, metadata: object, created_at }
ProjectDetailOut ProjectOut + { members: MemberOut[] }   (returned by POST, GET one and PATCH)
ProjectAction  "update" | "delete" | "manage_members" | "create_task"
TaskAction     "update" | "delete" | "complete"
```
`allowed_actions` is computed server-side by the policy engine (dry run) for the current user. The UI uses it only to show or hide controls. `task_counts` and `member_count` are computed, not stored.

Validation limits: `email` valid address, max 255. `password` 8 to 128 chars. User `name` 1 to 120. Project `name` 1 to 120. Task `title` 1 to 200 (trimmed, not blank). `description` max 5000.

## 3. Endpoints

Legend: Auth column "Pub" means no authentication. "Policy action" is evaluated by the authorization module (`authorization-design.md`). For project and task resources the non-member check always runs first and gives 404; the listed action (for example `project.update`) is then evaluated and gives 403 on denial. The `project.view` / `task.view` entries below in combination rows describe that first membership check.

| # | Method and path | Auth | Policy action | Success |
|---|---|---|---|---|
| 1 | `GET /api/v1/health` | Pub | none | 200 |
| 2 | `POST /auth/register` | Pub | none | 201 |
| 3 | `POST /auth/login` | Pub | none | 200 |
| 4 | `POST /auth/refresh` | Cookie | none | 200 |
| 5 | `POST /auth/logout` | Cookie | none | 204 |
| 6 | `GET /auth/me` | Yes | none | 200 |
| 7 | `GET /projects` | Yes | scoped to membership | 200 |
| 8 | `POST /projects` | Yes | `project.create` | 201 |
| 9 | `GET /projects/{project_id}` | Yes | `project.view` | 200 |
| 10 | `PATCH /projects/{project_id}` | Yes | `project.view` + `project.update` | 200 |
| 11 | `DELETE /projects/{project_id}` | Yes | `project.view` + `project.delete` | 204 |
| 12 | `GET /projects/{project_id}/members` | Yes | `project.view` | 200 |
| 13 | `POST /projects/{project_id}/members` | Yes | `project.view` + `project.member:manage` | 201 |
| 14 | `DELETE /projects/{project_id}/members/{user_id}` | Yes | `project.view` + `project.member:manage` | 204 |
| 15 | `GET /projects/{project_id}/tasks` | Yes | `project.view` | 200 |
| 16 | `POST /projects/{project_id}/tasks` | Yes | `task.create` (+ `task.complete` if resulting status is completed) | 201 |
| 17 | `GET /tasks/{task_id}` | Yes | `task.view` | 200 |
| 18 | `PATCH /tasks/{task_id}` | Yes | `task.view` + `task.update` (+ `task.complete` if resulting status is completed) | 200 |
| 19 | `DELETE /tasks/{task_id}` | Yes | `task.view` + `task.delete` | 204 |
| 20 | `GET /dashboard/stats` | Yes | scoped to membership | 200 |
| 21 | `GET /dashboard/activity` | Yes | scoped to membership | 200 |
| 22 | `GET /projects/{project_id}/activity` | Yes | `project.view` | 200 |

Every authenticated endpoint can also return 401. Endpoints with a path ID can return 404. Endpoints with a body can return 422.

### 3.1 Health
`GET /api/v1/health` returns 200 (liveness only; it does not query the database) `{ "data": { "status": "ok" } }`.

### 3.2 Auth

**Common to register, login and refresh:** on success the response sets `access_token`, `refresh_token` and `csrf_token` cookies. The body never contains a token.

**POST /auth/register**
Request: `{ "email": "ana@example.com", "name": "Ana Lopez", "password": "s3cretpass" }`
201: `{ "data": UserOut }` and sets both cookies (the user is logged in).
Errors: 409 `CONFLICT` (email exists), 422.

**POST /auth/login**
Request: `{ "email": "...", "password": "..." }`
200: `{ "data": UserOut }` and sets both cookies.
Errors: 401 `UNAUTHENTICATED` with message "Invalid email or password." for unknown email, wrong password or inactive user. 422.

**POST /auth/refresh**
No body. Reads the `refresh_token` cookie (requires the `X-CSRF-Token` header). Rotates: the old token is revoked and replaced, in the same token family, and a new access token is issued. Presenting a token that was already rotated or revoked is treated as theft: the whole family is revoked and the response is 401. An access token is never accepted here.
200: `{ "data": UserOut }`.
Errors: 401 (missing, unknown, expired, revoked or reused token; cookies are cleared).

**POST /auth/logout**
No body. Revokes the presented refresh token's family (if any) and clears all three cookies. Always 204, even when not logged in or when the token is invalid. Requires the `X-CSRF-Token` header when auth cookies are present.

**GET /auth/me**
200: `{ "data": UserOut }`.

### 3.3 Projects

**GET /projects**
Query: `q` (matches name, case-insensitive), `status` (`active`|`archived`), `page`, `page_size`.
Returns only projects the user is a member of, ordered by `updated_at` descending.
200: `{ "data": ProjectOut[], "meta": {...} }`.

**POST /projects**
Request: `{ "name": "Website redesign", "description": "optional", "status": "active" }` (`description` and `status` optional; `status` defaults to `active`).
201: `{ "data": ProjectDetailOut }`. The authenticated user becomes owner and first member. The project and the membership are written in one transaction. Owner and `created_by` are never read from the body.

**GET /projects/{project_id}**
200: `{ "data": ProjectDetailOut }` (project, owner, member list, counts). 404 for non-members.

**PATCH /projects/{project_id}**
Request: any of `{ "name", "description", "status" }`. At least one field. Omitted fields are unchanged; `"description": null` clears the description; `name` and `status` cannot be null.
200: `{ "data": ProjectDetailOut }`. 403 for members who are not the owner. 404 for non-members.

**DELETE /projects/{project_id}**
204. 403 for non-owner members. 404 for non-members. One transaction: the database cascades the project's members and tasks. `activity_logs` rows are kept (they have no foreign keys) and a `project.deleted` entry is written first.

**GET /projects** also returns, per project, `member_count`, `task_counts` and `allowed_actions`, computed in one query (no per-project queries). `q` matches the name case-insensitively; `%` and `_` are matched literally.

### 3.4 Members

**GET /projects/{project_id}/members**
200: `{ "data": MemberOut[] }` (owner first, then by `joined_at`). Not paginated.

**POST /projects/{project_id}/members**
Request: exactly one of `{ "email": "bob@example.com" }` or `{ "user_id": "<uuid>" }`. Both or neither gives 422. (`user_id` names the person being added, never the caller.)
201: `{ "data": MemberOut }`.
Errors: 403 (not owner), 404 (project not visible, or no active registered user matches: code `NOT_FOUND`, message "User not found."), 409 (already a member, including the owner).

**DELETE /projects/{project_id}/members/{user_id}**
204. In one transaction the member's task assignments in this project are cleared (all statuses, so no task points at a non-member) and the membership is deleted. Access is revoked immediately: the user's next request gets 404. The member's own tasks (as creator) are untouched.
Errors: 403 (not owner), 404 (project not visible, or user is not a member), 422 `BUSINESS_RULE_VIOLATION` (target is the owner).

### 3.5 Tasks

**GET /projects/{project_id}/tasks**
Query:
| Param | Type | Notes |
|---|---|---|
| `q` | string | Case-insensitive match on title or description |
| `status` | `todo`\|`in_progress`\|`completed` | May be repeated to match several |
| `priority` | `low`\|`medium`\|`high` | May be repeated |
| `assignee_id` | uuid or `unassigned` | |
| `overdue` | boolean | `true` returns tasks with `due_date` before today (UTC) and status not completed |
| `sort` | string | One of `created_at`, `-created_at` (default), `updated_at`, `-updated_at`, `due_date`, `-due_date`, `priority`, `-priority`, `position`. `due_date` sorts nulls last. `priority` order is low, medium, high. |
| `page`, `page_size` | int | |

200: `{ "data": TaskOut[], "meta": {...} }`. A non-uuid `assignee_id` (other than `unassigned`) gives 422.

**POST /projects/{project_id}/tasks**
Request:
```json
{
  "title": "Design login page",
  "description": "optional",
  "priority": "medium",
  "status": "todo",
  "assignee_id": "uuid | null",
  "due_date": "2026-11-20 | null"
}
```
Only `title` is required. `priority` defaults to `medium`, `status` to `todo`. `creator_id` is set from the JWT user. `position` is assigned by the server (end of the status column).
201: `{ "data": TaskOut }`.
Errors: 403 (completion rule failure when the requested status is `completed`), 404 (project missing or user is not a member), 422 `BUSINESS_RULE_VIOLATION` (assignee not a member).

**GET /tasks/{task_id}**
200: `{ "data": TaskOut }`. 404 if the task does not exist or the user is not a member of its project.

**PATCH /tasks/{task_id}**
Partial update. Any of `title`, `description`, `priority`, `status`, `assignee_id` (null unassigns), `due_date` (null clears), `position`. At least one field. `project_id` cannot be changed.
200: `{ "data": TaskOut }`.
Rules:
- Allowed for the task creator or assignee who is a current member (otherwise 403).
- If the resulting status is `completed`, the completion policy is also evaluated against the resulting task state. A denial gives 403 with `details[0].policy_id = "task-complete"` and a reason such as "Task must have an assignee." or "Missing required fields: due_date."
- `status` changes and Kanban moves both use this endpoint (`status` plus `position`).
- Setting `status` to something other than `completed` clears `completed_at`.
Errors: 403, 404, 422 (assignee not a member is `BUSINESS_RULE_VIOLATION`).

**DELETE /tasks/{task_id}**
204 only if the user is the project owner and the task status is `todo`. 403 otherwise for members. 404 for non-members.

### 3.6 Dashboard and activity

**GET /dashboard/stats**
200:
```json
{
  "data": {
    "total_projects": 4,
    "active_projects": 3,
    "total_tasks": 42,
    "completed_tasks": 18,
    "pending_tasks": 24,
    "overdue_tasks": 5,
    "assigned_to_me": 7,
    "recent_activity": [ ActivityOut, ... up to 10 ]
  }
}
```
Definitions are in `.kiro/steering/product.md` (Dashboard definitions).

**GET /dashboard/activity**
Query: `page`, `page_size` (default 20). Activity across the user's projects, newest first.
200: `{ "data": ActivityOut[], "meta": {...} }`.

**GET /projects/{project_id}/activity**
Query: `page`, `page_size`. Newest first.
200: `{ "data": ActivityOut[], "meta": {...} }`.

## 4. Status code summary

| Situation | Code |
|---|---|
| Created | 201 |
| Deleted or logged out | 204 |
| Not authenticated | 401 |
| Member denied by policy, bad origin | 403 |
| Not found or not visible | 404 |
| Duplicate | 409 |
| Invalid input or domain rule violated | 422 |
| Unexpected failure | 500 |

## 5. OpenAPI

FastAPI serves Swagger UI at `/docs` and the schema at `/openapi.json`. At milestone M8 the schema is exported to `docs/openapi.json`. If the exported schema and this document differ, this document is corrected first (or the code is fixed), then both are re-aligned.
