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
`details` is an array (empty when not applicable). Each item is `{ "field": string|null, "message": string, "policy_id": string|null }`: validation errors set `field`; policy denials set `policy_id` (for example `task-delete`) and a human-readable `message`. The `request_id` equals the `X-Request-ID` response header.

### Error codes
| HTTP | `code` | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token; bad login credentials; invalid refresh token |
| 403 | `FORBIDDEN` | Authenticated member denied by a policy; disallowed `Origin`; missing or wrong `X-CSRF-Token` |
| 404 | `NOT_FOUND` | Resource missing, unknown route, or project/task not visible to the user (non-member) |
| 405 | `METHOD_NOT_ALLOWED` | HTTP method not supported on the route |
| 409 | `CONFLICT` | Duplicate email, duplicate member |
| 422 | `VALIDATION_ERROR` | Malformed or invalid input, including NUL characters in text and out-of-range pagination |
| 422 | `BUSINESS_RULE_VIOLATION` | Valid input that breaks a domain rule (assignee not a member, removing the owner) |
| 500 | `INTERNAL_ERROR` | Unexpected error (generic message, request ID included) |

### Pagination parameters (all list endpoints)
`page` (default 1, 1 to 100000), `page_size` (default 20, 1 to 100). `limit` is accepted as an alias of `page_size`; if both are sent they must be equal (otherwise 422). Responses always report `page_size`.

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
DashboardStats { total_projects, active_projects, total_tasks, completed_tasks, pending_tasks,
                 overdue_tasks, assigned_to_me, recent_activity: ActivityOut[] (max 10) }
PageMeta       { page, page_size, total, total_pages }
ProjectDetailOut ProjectOut + { members: MemberOut[] }   (returned by POST, GET one and PATCH)
AssignedTaskOut  TaskOut + { project: { id, name, status } }   (returned by GET /me/tasks)
ProjectAction  "update" | "delete" | "manage_members" | "create_task"
TaskAction     "update" | "delete" | "complete"
```
`allowed_actions` is computed server-side by the policy engine (dry run) for the current user. For tasks, `complete` means the user could move the task to `completed` right now: they may update it (creator or assignee) AND it satisfies the completion policy. The UI uses it only to show or hide controls. `task_counts` and `member_count` are computed, not stored.

Validation limits: `email` valid address, max 255. `password` 8 to 128 chars. User `name` 1 to 120. Project `name` 1 to 120. Task `title` 1 to 200 (trimmed, not blank). `description` max 5000.

## 3. Endpoint reference

Every endpoint is documented with the same fields. Placeholders such as `<access-token-jwt>` stand for real cookie values. Identifiers and timestamps in the examples are normalized; everything else is real output of the running API (this section is generated by `backend/scripts/generate_api_docs.py`).

| # | Method and path | Authentication | Authorization policy |
|---|---|---|---|
| 1 | `GET /api/v1/health` | Public | None (liveness only; does not touch the database) |
| 2 | `POST /api/v1/auth/register` | Public | None |
| 3 | `POST /api/v1/auth/login` | Public | None |
| 4 | `POST /api/v1/auth/refresh` | Refresh token + CSRF | None (the refresh token is the credential) |
| 5 | `POST /api/v1/auth/logout` | Refresh token + CSRF | None |
| 6 | `GET /api/v1/auth/me` | Access token | None (returns the caller) |
| 7 | `POST /api/v1/projects` | Access token + CSRF | Policy `project.create`: any authenticated, active user |
| 8 | `GET /api/v1/projects` | Access token | Data scoping: only projects the caller is a CURRENT member of |
| 9 | `GET /api/v1/projects/{project_id}` | Access token | Policy `project.view`: current members only |
| 10 | `PATCH /api/v1/projects/{project_id}` | Access token + CSRF | Policy `project.update`: the project owner only |
| 11 | `DELETE /api/v1/projects/{project_id}` | Access token + CSRF | Policy `project.delete`: the project owner only |
| 12 | `GET /api/v1/projects/{project_id}/members` | Access token | Policy `project.view`: current members only |
| 13 | `POST /api/v1/projects/{project_id}/members` | Access token + CSRF | Policy `project.member.manage`: the project owner only |
| 14 | `DELETE /api/v1/projects/{project_id}/members/{user_id}` | Access token + CSRF | Policy `project.member.manage`: the project owner only |
| 15 | `POST /api/v1/projects/{project_id}/tasks` | Access token + CSRF | Policy `task.create` (members only); plus `task.complete` when the new task is created already `completed` |
| 16 | `GET /api/v1/projects/{project_id}/tasks` | Access token | Policy `project.view`: current members only |
| 17 | `GET /api/v1/tasks/{task_id}` | Access token | Policy `project.view` evaluated on the task's project (the project is read from the database, never from the request) |
| 18 | `PATCH /api/v1/tasks/{task_id}` | Access token + CSRF | Policy `task.update`: the task creator OR assignee, who must still be a project member |
| 19 | `PATCH /api/v1/tasks/{task_id}/status` | Access token + CSRF | Policy `task.update` (creator or assignee); also `task.complete` when the new status is `completed`: an assignee who is a member, a non-blank title and description, a priority and a due date |
| 20 | `DELETE /api/v1/tasks/{task_id}` | Access token + CSRF | Policy `task.delete`: the project owner AND the task status is `todo` |
| 21 | `GET /api/v1/me/tasks` | Access token | Data scoping: tasks assigned to the caller, only in projects the caller is a CURRENT member of |
| 22 | `GET /api/v1/dashboard/stats` | Access token | Data scoping: only projects the caller is a CURRENT member of |
| 23 | `GET /api/v1/dashboard/activity` | Access token | Data scoping: only projects the caller is a CURRENT member of |
| 24 | `GET /api/v1/projects/{project_id}/activity` | Access token | Policy `project.view`: current members only |

### 3.1 Health

#### 3.1.1 GET /api/v1/health

**Authentication:** Public (no authentication)

**Authorization policy:** None (liveness only; does not touch the database).

**Query parameters**

None.

**Request body:** None.

**Response:** `Envelope<{status: "ok"}>`

**Error responses**

| Status | Code | When |
|---|---|---|

**Example request**

```http
GET /api/v1/health HTTP/1.1
```

**Example response**

```http
HTTP/1.1 200 OK

{
  "data": {
    "status": "ok"
  }
}
```

**Rules**

- Intended for container and load-balancer health checks.

### 3.2 Authentication

#### 3.2.1 POST /api/v1/auth/register

**Authentication:** Public (no authentication)

**Authorization policy:** None. The new account is created and logged in.

**Query parameters**

None.

**Request body:** `{ name: string (1-120), email: string, password: string (8-128) }`. Unknown fields give 422. The email is trimmed and lowercased.

**Response:** `Envelope<UserOut>` and three `Set-Cookie` headers (`access_token`, `refresh_token`, `csrf_token`). No token appears in the body.

**Error responses**

| Status | Code | When |
|---|---|---|
| 403 | `FORBIDDEN` | A disallowed `Origin` header. |
| 409 | `CONFLICT` | An account with this email already exists. |
| 422 | `VALIDATION_ERROR` | Malformed or invalid path id, query or body; unknown body fields are rejected. |

**Example request**

```http
POST /api/v1/auth/register HTTP/1.1
Content-Type: application/json

{
  "name": "Ana Lopez",
  "email": "ana@example.com",
  "password": "correct-horse-battery"
}
```

**Example response**

```http
HTTP/1.1 201 Created
Set-Cookie: access_token=<access-token-jwt>; HttpOnly; Max-Age=900; Path=/; SameSite=lax
Set-Cookie: refresh_token=<refresh-token-jwt>; HttpOnly; Max-Age=604800; Path=/api/v1/auth; SameSite=lax
Set-Cookie: csrf_token=<csrf-token>; Max-Age=604800; Path=/; SameSite=lax

{
  "data": {
    "id": "00000000-0000-4000-8000-000000000001",
    "email": "ana@example.com",
    "name": "Ana Lopez"
  }
}
```

**Example error response** (409)

```http
HTTP/1.1 409 Conflict

{
  "error": {
    "code": "CONFLICT",
    "message": "An account with this email already exists.",
    "details": [],
    "request_id": "00000000-0000-4000-8000-000000000002"
  }
}
```

**Rules**

- The password is stored only as an Argon2id hash.
- Identity fields (`id`, `is_active`, ...) cannot be supplied: they give 422.
- Writes a `user.registered` activity entry.

#### 3.2.2 POST /api/v1/auth/login

**Authentication:** Public (no authentication)

**Authorization policy:** None. Inactive accounts cannot log in.

**Query parameters**

None.

**Request body:** `{ email: string, password: string }`

**Response:** `Envelope<UserOut>` and three `Set-Cookie` headers (see register).

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Wrong email or password, or inactive account. The message is always "Invalid email or password." |
| 403 | `FORBIDDEN` | A disallowed `Origin` header. |
| 422 | `VALIDATION_ERROR` | Malformed or invalid path id, query or body; unknown body fields are rejected. |

**Example request**

```http
POST /api/v1/auth/login HTTP/1.1
Content-Type: application/json

{
  "email": "ana@example.com",
  "password": "correct-horse-battery"
}
```

**Example response**

```http
HTTP/1.1 200 OK
Set-Cookie: access_token=<access-token-jwt>; HttpOnly; Max-Age=900; Path=/; SameSite=lax
Set-Cookie: refresh_token=<refresh-token-jwt>; HttpOnly; Max-Age=604800; Path=/api/v1/auth; SameSite=lax
Set-Cookie: csrf_token=<csrf-token>; Max-Age=604800; Path=/; SameSite=lax

{
  "data": {
    "id": "00000000-0000-4000-8000-000000000001",
    "email": "ana@example.com",
    "name": "Ana Lopez"
  }
}
```

**Example error response** (401)

```http
HTTP/1.1 401 Unauthorized

{
  "error": {
    "code": "UNAUTHENTICATED",
    "message": "Invalid email or password.",
    "details": [],
    "request_id": "00000000-0000-4000-8000-000000000003"
  }
}
```

**Rules**

- Each login starts a new refresh-token family (one per device).
- A request whose `Origin` header is not allowed gets 403, even without cookies.
- Writes an `auth.login` activity entry.

#### 3.2.3 POST /api/v1/auth/refresh

**Authentication:** Refresh-token cookie (`refresh_token`) + `X-CSRF-Token` header

**Authorization policy:** None (the refresh token is the credential).

**Query parameters**

None.

**Request body:** None (no body).

**Response:** `Envelope<UserOut>` and three new `Set-Cookie` headers.

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid, expired, revoked or reused refresh token. The auth cookies are cleared in the response. |
| 403 | `FORBIDDEN` | Missing or wrong `X-CSRF-Token` header, or a disallowed `Origin`. |

**Example request**

```http
POST /api/v1/auth/refresh HTTP/1.1
Cookie: refresh_token=<refresh-token-jwt>; csrf_token=<csrf-token>
X-CSRF-Token: <csrf-token>
```

**Example response**

```http
HTTP/1.1 200 OK
Set-Cookie: access_token=<access-token-jwt>; HttpOnly; Max-Age=900; Path=/; SameSite=lax
Set-Cookie: refresh_token=<refresh-token-jwt>; HttpOnly; Max-Age=604800; Path=/api/v1/auth; SameSite=lax
Set-Cookie: csrf_token=<csrf-token>; Max-Age=604800; Path=/; SameSite=lax

{
  "data": {
    "id": "00000000-0000-4000-8000-000000000001",
    "email": "ana@example.com",
    "name": "Ana Lopez"
  }
}
```

**Example error response** (401)

```http
HTTP/1.1 401 Unauthorized
Set-Cookie: access_token=; HttpOnly; Max-Age=0; Path=/; SameSite=lax
Set-Cookie: refresh_token=; HttpOnly; Max-Age=0; Path=/api/v1/auth; SameSite=lax
Set-Cookie: csrf_token=; Max-Age=0; Path=/; SameSite=lax

{
  "error": {
    "code": "UNAUTHENTICATED",
    "message": "Your session is no longer valid. Please log in again.",
    "details": [],
    "request_id": "00000000-0000-4000-8000-000000000004"
  }
}
```

**Rules**

- Rotation: the presented token is revoked and replaced in the same family.
- Presenting an already-rotated token is treated as theft: the whole family is revoked and an `auth.refresh_reuse_detected` activity entry is written.
- An access token is never accepted here (different audience and type).

#### 3.2.4 POST /api/v1/auth/logout

**Authentication:** Refresh-token cookie (`refresh_token`) + `X-CSRF-Token` header

**Authorization policy:** None.

**Query parameters**

None.

**Request body:** None (no body).

**Response:** `204 No Content` with `Set-Cookie` headers that clear all three cookies.

**Error responses**

| Status | Code | When |
|---|---|---|
| 403 | `FORBIDDEN` | Missing or wrong `X-CSRF-Token` header, or a disallowed `Origin`. |

**Example request**

```http
POST /api/v1/auth/logout HTTP/1.1
Cookie: refresh_token=<refresh-token-jwt>; csrf_token=<csrf-token>
X-CSRF-Token: <csrf-token>
```

**Example response**

```http
HTTP/1.1 204 No Content
Set-Cookie: access_token=; HttpOnly; Max-Age=0; Path=/; SameSite=lax
Set-Cookie: refresh_token=; HttpOnly; Max-Age=0; Path=/api/v1/auth; SameSite=lax
Set-Cookie: csrf_token=; Max-Age=0; Path=/; SameSite=lax
```

**Rules**

- Always 204, also when not logged in or when the token is invalid (idempotent).
- Revokes the presented token's whole family. Writes `auth.logout` when it is known.
- A copied access token stays valid until its 15-minute expiry (stateless token).

#### 3.2.5 GET /api/v1/auth/me

**Authentication:** Access-token cookie (`access_token`)

**Authorization policy:** None (returns the caller).

**Query parameters**

None.

**Request body:** None.

**Response:** `Envelope<UserOut>`

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token, or the user is inactive. |

**Example request**

```http
GET /api/v1/auth/me HTTP/1.1
Cookie: access_token=<access-token-jwt>
```

**Example response**

```http
HTTP/1.1 200 OK

{
  "data": {
    "id": "00000000-0000-4000-8000-000000000001",
    "email": "ana@example.com",
    "name": "Ana Lopez"
  }
}
```

**Rules**

- The identity comes only from the verified token, never from the request.

### 3.3 Projects

#### 3.3.1 POST /api/v1/projects

**Authentication:** Access-token cookie + `X-CSRF-Token` header

**Authorization policy:** Policy `project.create`: any authenticated, active user.

**Query parameters**

None.

**Request body:** `{ name: string (1-120), description?: string|null (max 5000), status?: "active"|"archived" }` (default status `active`). `owner_id` and other unknown fields give 422.

**Response:** `Envelope<ProjectDetailOut>` (201). The caller is owner and first member.

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token, or the user is inactive. |
| 403 | `FORBIDDEN` | Missing or wrong `X-CSRF-Token` header, or a disallowed `Origin`. |
| 422 | `VALIDATION_ERROR` | Malformed or invalid path id, query or body; unknown body fields are rejected. |

**Example request**

```http
POST /api/v1/projects HTTP/1.1
Content-Type: application/json
Cookie: access_token=<access-token-jwt>; csrf_token=<csrf-token>
X-CSRF-Token: <csrf-token>

{
  "name": "Website redesign",
  "description": "Q4 launch"
}
```

**Example response**

```http
HTTP/1.1 201 Created

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

**Example error response** (422)

```http
HTTP/1.1 422 Unprocessable Content

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

**Rules**

- The project and the owner's membership are written in ONE transaction.
- Writes a `project.created` activity entry.

#### 3.3.2 GET /api/v1/projects

**Authentication:** Access-token cookie (`access_token`)

**Authorization policy:** Data scoping: only projects the caller is a CURRENT member of.

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `q` | string (max 100) | Name contains, case-insensitive. `%` and `_` are literal. |
| `status` | `active`|`archived` | Filter by status. |
| `page` | int 1-100000 | Default 1. |
| `page_size / limit` | int 1-100 | Default 20. `limit` is an alias. |

**Request body:** None.

**Response:** `PagedEnvelope<ProjectOut>` ordered by most recently updated. Each item has `member_count`, `task_counts` and `allowed_actions`, computed in one query.

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token, or the user is inactive. |
| 422 | `VALIDATION_ERROR` | Malformed or invalid path id, query or body; unknown body fields are rejected. |

**Example request**

```http
GET /api/v1/projects?q=web&page_size=10 HTTP/1.1
Cookie: access_token=<access-token-jwt>
```

**Example response**

```http
HTTP/1.1 200 OK

{
  "data": [
    {
      "id": "00000000-0000-4000-8000-000000000005",
      "name": "Website redesign",
      "description": "Q4 launch",
      "status": "active",
      "owner": {
        "id": "00000000-0000-4000-8000-000000000001",
        "email": "ana@example.com",
        "name": "Ana Lopez"
      },
      "member_count": 3,
      "task_counts": {
        "todo": 0,
        "in_progress": 0,
        "completed": 0
      },
      "allowed_actions": [
        "create_task"
      ],
      "created_at": "2026-11-15T10:00:00Z",
      "updated_at": "2026-11-15T10:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 10,
    "total": 1,
    "total_pages": 1
  }
}
```

**Rules**

- Never lists a project the caller does not belong to.

#### 3.3.3 GET /api/v1/projects/{project_id}

**Authentication:** Access-token cookie (`access_token`)

**Authorization policy:** Policy `project.view`: current members only.

**Query parameters**

None.

**Request body:** None.

**Response:** `Envelope<ProjectDetailOut>`: project, owner, members (owner first), counts, `allowed_actions`.

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token, or the user is inactive. |
| 404 | `NOT_FOUND` | The project does not exist, or the caller is not a member (the two cases are indistinguishable). |
| 422 | `VALIDATION_ERROR` | Malformed or invalid path id, query or body; unknown body fields are rejected. |

**Example request**

```http
GET /api/v1/projects/00000000-0000-4000-8000-000000000005 HTTP/1.1
Cookie: access_token=<access-token-jwt>
```

**Example response**

```http
HTTP/1.1 200 OK

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
    "member_count": 3,
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
      },
      {
        "user": {
          "id": "00000000-0000-4000-8000-000000000007",
          "email": "ben@example.com",
          "name": "Ben Carter"
        },
        "is_owner": false,
        "joined_at": "2026-11-15T10:00:01Z"
      },
      {
        "user": {
          "id": "00000000-0000-4000-8000-000000000009",
          "email": "cy@example.com",
          "name": "Cy Dunn"
        },
        "is_owner": false,
        "joined_at": "2026-11-15T10:00:02Z"
      }
    ]
  }
}
```

**Example error response** (404)

```http
HTTP/1.1 404 Not Found

{
  "error": {
    "code": "NOT_FOUND",
    "message": "Resource not found.",
    "details": [],
    "request_id": "00000000-0000-4000-8000-000000000010"
  }
}
```

#### 3.3.4 PATCH /api/v1/projects/{project_id}

**Authentication:** Access-token cookie + `X-CSRF-Token` header

**Authorization policy:** Policy `project.update`: the project owner only.

**Query parameters**

None.

**Request body:** Any of `{ name, description, status }`; at least one. Omitted fields are unchanged, `description: null` clears it, `name` and `status` cannot be null.

**Response:** `Envelope<ProjectDetailOut>`

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token, or the user is inactive. |
| 403 | `FORBIDDEN` | A member who is not the owner (policy `project-update`). |
| 403 | `FORBIDDEN` | Missing or wrong `X-CSRF-Token` header, or a disallowed `Origin`. |
| 404 | `NOT_FOUND` | Missing project or not a member. |
| 422 | `VALIDATION_ERROR` | Malformed or invalid path id, query or body; unknown body fields are rejected. |

**Example request**

```http
PATCH /api/v1/projects/00000000-0000-4000-8000-000000000005 HTTP/1.1
Content-Type: application/json
Cookie: access_token=<access-token-jwt>; csrf_token=<csrf-token>
X-CSRF-Token: <csrf-token>

{
  "description": "Q4 launch of the new marketing site"
}
```

**Example response**

```http
HTTP/1.1 200 OK

{
  "data": {
    "id": "00000000-0000-4000-8000-000000000005",
    "name": "Website redesign",
    "description": "Q4 launch of the new marketing site",
    "status": "active",
    "owner": {
      "id": "00000000-0000-4000-8000-000000000001",
      "email": "ana@example.com",
      "name": "Ana Lopez"
    },
    "member_count": 3,
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
    "updated_at": "2026-11-15T10:00:03Z",
    "members": [
      {
        "user": {
          "id": "00000000-0000-4000-8000-000000000001",
          "email": "ana@example.com",
          "name": "Ana Lopez"
        },
        "is_owner": true,
        "joined_at": "2026-11-15T10:00:00Z"
      },
      {
        "user": {
          "id": "00000000-0000-4000-8000-000000000007",
          "email": "ben@example.com",
          "name": "Ben Carter"
        },
        "is_owner": false,
        "joined_at": "2026-11-15T10:00:01Z"
      },
      {
        "user": {
          "id": "00000000-0000-4000-8000-000000000009",
          "email": "cy@example.com",
          "name": "Cy Dunn"
        },
        "is_owner": false,
        "joined_at": "2026-11-15T10:00:02Z"
      }
    ]
  }
}
```

**Example error response** (403)

```http
HTTP/1.1 403 Forbidden

{
  "error": {
    "code": "FORBIDDEN",
    "message": "Only the project owner can update a project.",
    "details": [
      {
        "field": null,
        "message": "Only the project owner can update a project.",
        "policy_id": "project-update"
      }
    ],
    "request_id": "00000000-0000-4000-8000-000000000011"
  }
}
```

**Rules**

- A request that changes nothing succeeds and writes no activity entry.
- Writes `project.updated` with the old and new values.

#### 3.3.5 DELETE /api/v1/projects/{project_id}

**Authentication:** Access-token cookie + `X-CSRF-Token` header

**Authorization policy:** Policy `project.delete`: the project owner only.

**Query parameters**

None.

**Request body:** None.

**Response:** `204 No Content`

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token, or the user is inactive. |
| 403 | `FORBIDDEN` | A member who is not the owner (policy `project-delete`). |
| 403 | `FORBIDDEN` | Missing or wrong `X-CSRF-Token` header, or a disallowed `Origin`. |
| 404 | `NOT_FOUND` | Missing project or not a member. |
| 422 | `VALIDATION_ERROR` | Malformed or invalid path id, query or body; unknown body fields are rejected. |

**Example request**

```http
DELETE /api/v1/projects/00000000-0000-4000-8000-000000000005 HTTP/1.1
Cookie: access_token=<access-token-jwt>; csrf_token=<csrf-token>
X-CSRF-Token: <csrf-token>
```

**Example response**

```http
HTTP/1.1 204 No Content
```

**Example error response** (403)

```http
HTTP/1.1 403 Forbidden

{
  "error": {
    "code": "FORBIDDEN",
    "message": "Only the project owner can delete a project.",
    "details": [
      {
        "field": null,
        "message": "Only the project owner can delete a project.",
        "policy_id": "project-delete"
      }
    ],
    "request_id": "00000000-0000-4000-8000-000000000035"
  }
}
```

**Rules**

- One transaction; the database cascades the project's members and tasks.
- Activity history is kept (no foreign keys) and a `project.deleted` entry is written.

### 3.4 Project members

#### 3.4.1 GET /api/v1/projects/{project_id}/members

**Authentication:** Access-token cookie (`access_token`)

**Authorization policy:** Policy `project.view`: current members only.

**Query parameters**

None.

**Request body:** None.

**Response:** `Envelope<MemberOut[]>` (not paginated): the owner first, then by join time.

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token, or the user is inactive. |
| 404 | `NOT_FOUND` | Missing project or not a member. |
| 422 | `VALIDATION_ERROR` | Malformed or invalid path id, query or body; unknown body fields are rejected. |

**Example request**

```http
GET /api/v1/projects/00000000-0000-4000-8000-000000000005/members HTTP/1.1
Cookie: access_token=<access-token-jwt>
```

**Example response**

```http
HTTP/1.1 200 OK

{
  "data": [
    {
      "user": {
        "id": "00000000-0000-4000-8000-000000000001",
        "email": "ana@example.com",
        "name": "Ana Lopez"
      },
      "is_owner": true,
      "joined_at": "2026-11-15T10:00:00Z"
    },
    {
      "user": {
        "id": "00000000-0000-4000-8000-000000000007",
        "email": "ben@example.com",
        "name": "Ben Carter"
      },
      "is_owner": false,
      "joined_at": "2026-11-15T10:00:01Z"
    },
    {
      "user": {
        "id": "00000000-0000-4000-8000-000000000009",
        "email": "cy@example.com",
        "name": "Cy Dunn"
      },
      "is_owner": false,
      "joined_at": "2026-11-15T10:00:02Z"
    }
  ]
}
```

#### 3.4.2 POST /api/v1/projects/{project_id}/members

**Authentication:** Access-token cookie + `X-CSRF-Token` header

**Authorization policy:** Policy `project.member.manage`: the project owner only.

**Query parameters**

None.

**Request body:** Exactly one of `{ email: string }` or `{ user_id: uuid }` (the person being added, never the caller). Both or neither gives 422.

**Response:** `Envelope<MemberOut>` (201)

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token, or the user is inactive. |
| 403 | `FORBIDDEN` | A member who is not the owner (policy `project-member-manage`). |
| 403 | `FORBIDDEN` | Missing or wrong `X-CSRF-Token` header, or a disallowed `Origin`. |
| 404 | `NOT_FOUND` | Missing project or not a member, or no active user matches (message "User not found."). |
| 409 | `CONFLICT` | The user is already a member (including the owner). |
| 422 | `VALIDATION_ERROR` | Malformed or invalid path id, query or body; unknown body fields are rejected. |

**Example request**

```http
POST /api/v1/projects/00000000-0000-4000-8000-000000000005/members HTTP/1.1
Content-Type: application/json
Cookie: access_token=<access-token-jwt>; csrf_token=<csrf-token>
X-CSRF-Token: <csrf-token>

{
  "email": "ben@example.com"
}
```

**Example response**

```http
HTTP/1.1 201 Created

{
  "data": {
    "user": {
      "id": "00000000-0000-4000-8000-000000000007",
      "email": "ben@example.com",
      "name": "Ben Carter"
    },
    "is_owner": false,
    "joined_at": "2026-11-15T10:00:01Z"
  }
}
```

**Example error response** (409)

```http
HTTP/1.1 409 Conflict

{
  "error": {
    "code": "CONFLICT",
    "message": "This user is already a member of the project.",
    "details": [],
    "request_id": "00000000-0000-4000-8000-000000000008"
  }
}
```

**Rules**

- The new member has access immediately.
- Writes a `member.added` entry.

#### 3.4.3 DELETE /api/v1/projects/{project_id}/members/{user_id}

**Authentication:** Access-token cookie + `X-CSRF-Token` header

**Authorization policy:** Policy `project.member.manage`: the project owner only.

**Query parameters**

None.

**Request body:** None.

**Response:** `204 No Content`

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token, or the user is inactive. |
| 403 | `FORBIDDEN` | A member who is not the owner (policy `project-member-manage`). |
| 403 | `FORBIDDEN` | Missing or wrong `X-CSRF-Token` header, or a disallowed `Origin`. |
| 404 | `NOT_FOUND` | Missing project or not a member, or the target is not a member (message "Member not found."). |
| 422 | `BUSINESS_RULE_VIOLATION` | The target is the project owner. |
| 422 | `VALIDATION_ERROR` | Malformed or invalid path id, query or body; unknown body fields are rejected. |

**Example request**

```http
DELETE /api/v1/projects/00000000-0000-4000-8000-000000000005/members/00000000-0000-4000-8000-000000000009 HTTP/1.1
Cookie: access_token=<access-token-jwt>; csrf_token=<csrf-token>
X-CSRF-Token: <csrf-token>
```

**Example response**

```http
HTTP/1.1 204 No Content
```

**Example error response** (422)

```http
HTTP/1.1 422 Unprocessable Content

{
  "error": {
    "code": "BUSINESS_RULE_VIOLATION",
    "message": "The project owner cannot be removed from the project.",
    "details": [],
    "request_id": "00000000-0000-4000-8000-000000000034"
  }
}
```

**Rules**

- One transaction: the member's task assignments in this project are cleared (all statuses), then the membership is deleted. Tasks they created stay.
- Access is revoked immediately: the removed user's next request gets 404.
- Writes `member.removed` and one `task.unassigned` entry per cleared task.

### 3.5 Tasks

#### 3.5.1 POST /api/v1/projects/{project_id}/tasks

**Authentication:** Access-token cookie + `X-CSRF-Token` header

**Authorization policy:** Policy `task.create` (members only); plus `task.complete` when the new task is created already `completed`.

**Query parameters**

None.

**Request body:** `{ title: string (1-200), description?: string|null (max 5000), priority?: low|medium|high, status?: todo|in_progress|completed, assignee_id?: uuid|null, due_date?: date|null }`. Defaults: priority `medium`, status `todo`. `creator_id`, `project_id`, `position` and unknown fields give 422.

**Response:** `Envelope<TaskOut>` (201). The creator is the caller; `position` is the end of the status column.

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token, or the user is inactive. |
| 403 | `FORBIDDEN` | Created as `completed` without an assignee or required information (policy `task-complete`). |
| 403 | `FORBIDDEN` | Missing or wrong `X-CSRF-Token` header, or a disallowed `Origin`. |
| 404 | `NOT_FOUND` | Missing project or not a member. |
| 422 | `BUSINESS_RULE_VIOLATION` | The assignee is not a project member. |
| 422 | `VALIDATION_ERROR` | Malformed or invalid path id, query or body; unknown body fields are rejected. |

**Example request**

```http
POST /api/v1/projects/00000000-0000-4000-8000-000000000005/tasks HTTP/1.1
Content-Type: application/json
Cookie: access_token=<access-token-jwt>; csrf_token=<csrf-token>
X-CSRF-Token: <csrf-token>

{
  "title": "Design login page",
  "description": "Wireframes and copy",
  "priority": "high",
  "due_date": "2099-12-31",
  "assignee_id": "00000000-0000-4000-8000-000000000009"
}
```

**Example response**

```http
HTTP/1.1 201 Created

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

**Example error response** (422)

```http
HTTP/1.1 422 Unprocessable Content

{
  "error": {
    "code": "BUSINESS_RULE_VIOLATION",
    "message": "The assignee must be a member of the project.",
    "details": [],
    "request_id": "00000000-0000-4000-8000-000000000013"
  }
}
```

**Rules**

- Writes a `task.created` entry.

#### 3.5.2 GET /api/v1/projects/{project_id}/tasks

**Authentication:** Access-token cookie (`access_token`)

**Authorization policy:** Policy `project.view`: current members only.

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `q` | string (max 100) | Title or description contains, case-insensitive. |
| `status` | `todo`|`in_progress`|`completed` | May be repeated. |
| `priority` | `low`|`medium`|`high` | May be repeated. |
| `assignee_id` | uuid or `unassigned` | Anything else gives 422. |
| `due_after` | date | Due on or after (tasks without a due date are excluded). |
| `due_before` | date | Due on or before (tasks without a due date are excluded). |
| `overdue` | boolean | `true`: due before today (UTC) and not completed. `false`: the complement. |
| `sort` | enum | `created_at`, `-created_at` (default), `updated_at`, `-updated_at`, `due_date`, `-due_date`, `priority`, `-priority`, `position`. Anything else gives 422. Ties are broken by `id`. |
| `page` | int 1-100000 | Default 1. |
| `page_size / limit` | int 1-100 | Default 20. `limit` is an alias. |

**Request body:** None.

**Response:** `PagedEnvelope<TaskOut>`

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token, or the user is inactive. |
| 404 | `NOT_FOUND` | Missing project or not a member. |
| 422 | `VALIDATION_ERROR` | Malformed or invalid path id, query or body; unknown body fields are rejected. |

**Example request**

```http
GET /api/v1/projects/00000000-0000-4000-8000-000000000005/tasks?priority=high&sort=due_date&limit=5 HTTP/1.1
Cookie: access_token=<access-token-jwt>
```

**Example response**

```http
HTTP/1.1 200 OK

{
  "data": [
    {
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
  ],
  "meta": {
    "page": 1,
    "page_size": 5,
    "total": 1,
    "total_pages": 1
  }
}
```

**Rules**

- Creators and assignees come from joins: two queries per page, whatever its size.

#### 3.5.3 GET /api/v1/tasks/{task_id}

**Authentication:** Access-token cookie (`access_token`)

**Authorization policy:** Policy `project.view` evaluated on the task's project (the project is read from the database, never from the request).

**Query parameters**

None.

**Request body:** None.

**Response:** `Envelope<TaskOut>` with `creator` and `assignee` objects.

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token, or the user is inactive. |
| 404 | `NOT_FOUND` | The task does not exist, or the caller is not a member of its project (indistinguishable). |
| 422 | `VALIDATION_ERROR` | Malformed or invalid path id, query or body; unknown body fields are rejected. |

**Example request**

```http
GET /api/v1/tasks/00000000-0000-4000-8000-000000000014 HTTP/1.1
Cookie: access_token=<access-token-jwt>
```

**Example response**

```http
HTTP/1.1 200 OK

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

**Example error response** (404)

```http
HTTP/1.1 404 Not Found

{
  "error": {
    "code": "NOT_FOUND",
    "message": "Resource not found.",
    "details": [],
    "request_id": "00000000-0000-4000-8000-000000000015"
  }
}
```

#### 3.5.4 PATCH /api/v1/tasks/{task_id}

**Authentication:** Access-token cookie + `X-CSRF-Token` header

**Authorization policy:** Policy `task.update`: the task creator OR assignee, who must still be a project member. A task that is completed must stay complete (policy `task.complete`).

**Query parameters**

None.

**Request body:** Any of `{ title, description, priority, due_date, assignee_id }`; at least one. `null` clears description, due_date and assignee. `status`, `position`, `creator_id`, `project_id` and timestamps are rejected (422): status changes use the status endpoint.

**Response:** `Envelope<TaskOut>`

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token, or the user is inactive. |
| 403 | `FORBIDDEN` | Missing or wrong `X-CSRF-Token` header, or a disallowed `Origin`. |
| 403 | `FORBIDDEN` | Not the creator or assignee (`task-update`), or the edit would make a completed task incomplete (`task-complete`). |
| 404 | `NOT_FOUND` | Missing task or not a member of its project. |
| 422 | `BUSINESS_RULE_VIOLATION` | The assignee is not a project member. |
| 422 | `VALIDATION_ERROR` | Malformed or invalid path id, query or body; unknown body fields are rejected. |

**Example request**

```http
PATCH /api/v1/tasks/00000000-0000-4000-8000-000000000014 HTTP/1.1
Content-Type: application/json
Cookie: access_token=<access-token-jwt>; csrf_token=<csrf-token>
X-CSRF-Token: <csrf-token>

{
  "priority": "medium",
  "due_date": "2099-06-30"
}
```

**Example response**

```http
HTTP/1.1 200 OK

{
  "data": {
    "id": "00000000-0000-4000-8000-000000000014",
    "project_id": "00000000-0000-4000-8000-000000000005",
    "title": "Design login page",
    "description": "Wireframes and copy",
    "status": "todo",
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
    "position": 1024.0,
    "completed_at": null,
    "allowed_actions": [
      "update",
      "complete"
    ],
    "created_at": "2026-11-15T10:00:04Z",
    "updated_at": "2026-11-15T10:00:05Z"
  }
}
```

**Example error response** (403)

```http
HTTP/1.1 403 Forbidden

{
  "error": {
    "code": "FORBIDDEN",
    "message": "Only the task creator or the task assignee can update a task.",
    "details": [
      {
        "field": null,
        "message": "Only the task creator or the task assignee can update a task.",
        "policy_id": "task-update"
      }
    ],
    "request_id": "00000000-0000-4000-8000-000000000016"
  }
}
```

**Rules**

- Writes `task.updated` (old and new values) and `task.assigned` or `task.unassigned` when the assignee changes. A no-op writes nothing.

#### 3.5.5 PATCH /api/v1/tasks/{task_id}/status

**Authentication:** Access-token cookie + `X-CSRF-Token` header

**Authorization policy:** Policy `task.update` (creator or assignee); also `task.complete` when the new status is `completed`: an assignee who is a member, a non-blank title and description, a priority and a due date.

**Query parameters**

None.

**Request body:** `{ status: todo|in_progress|completed, position?: number }`. `position` places the task on the board (default: end of the new column). Numbers only, finite, within +-1e12.

**Response:** `Envelope<TaskOut>`

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token, or the user is inactive. |
| 403 | `FORBIDDEN` | Missing or wrong `X-CSRF-Token` header, or a disallowed `Origin`. |
| 403 | `FORBIDDEN` | Not the creator or assignee (`task-update`), or the completion information is missing (`task-complete`). |
| 404 | `NOT_FOUND` | Missing task or not a member of its project. |
| 422 | `BUSINESS_RULE_VIOLATION` | Invalid transition, or the task is already in that status and no `position` was given. |
| 422 | `VALIDATION_ERROR` | Malformed or invalid path id, query or body; unknown body fields are rejected. |

**Example request**

```http
PATCH /api/v1/tasks/00000000-0000-4000-8000-000000000014/status HTTP/1.1
Content-Type: application/json
Cookie: access_token=<access-token-jwt>; csrf_token=<csrf-token>
X-CSRF-Token: <csrf-token>

{
  "status": "in_progress"
}
```

**Example response**

```http
HTTP/1.1 200 OK

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

**Example error response** (422)

```http
HTTP/1.1 422 Unprocessable Content

{
  "error": {
    "code": "BUSINESS_RULE_VIOLATION",
    "message": "A task cannot move from todo to completed. Allowed from todo: in_progress.",
    "details": [],
    "request_id": "00000000-0000-4000-8000-000000000017"
  }
}
```

**Rules**

- Transitions form a line: `todo` <-> `in_progress` <-> `completed`. Direct `todo` <-> `completed` is rejected.
- `completed_at` is set when entering `completed` and cleared when leaving it.
- An invalid transition is reported (422) before the completion policy (403).
- Writes a `task.status_changed` entry.

#### 3.5.6 DELETE /api/v1/tasks/{task_id}

**Authentication:** Access-token cookie + `X-CSRF-Token` header

**Authorization policy:** Policy `task.delete`: the project owner AND the task status is `todo`.

**Query parameters**

None.

**Request body:** None.

**Response:** `204 No Content`

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token, or the user is inactive. |
| 403 | `FORBIDDEN` | Missing or wrong `X-CSRF-Token` header, or a disallowed `Origin`. |
| 403 | `FORBIDDEN` | Not the owner, or the task is not `todo` (policy `task-delete`). The task creator cannot delete either. |
| 404 | `NOT_FOUND` | Missing task or not a member of its project. |
| 422 | `VALIDATION_ERROR` | Malformed or invalid path id, query or body; unknown body fields are rejected. |

**Example request**

```http
DELETE /api/v1/tasks/00000000-0000-4000-8000-000000000020 HTTP/1.1
Cookie: access_token=<access-token-jwt>; csrf_token=<csrf-token>
X-CSRF-Token: <csrf-token>
```

**Example response**

```http
HTTP/1.1 204 No Content
```

**Example error response** (403)

```http
HTTP/1.1 403 Forbidden

{
  "error": {
    "code": "FORBIDDEN",
    "message": "Only the project owner can delete a task, and only while its status is todo.",
    "details": [
      {
        "field": null,
        "message": "Only the project owner can delete a task, and only while its status is todo.",
        "policy_id": "task-delete"
      }
    ],
    "request_id": "00000000-0000-4000-8000-000000000019"
  }
}
```

**Rules**

- Writes a `task.deleted` entry; the history outlives the task.

#### 3.5.7 GET /api/v1/me/tasks

**Authentication:** Access-token cookie (`access_token`)

**Authorization policy:** Data scoping: tasks assigned to the caller, only in projects the caller is a CURRENT member of. `allowed_actions` still come from the policy engine.

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `q` | string (max 100) | Title or description contains, case-insensitive. |
| `status` | `todo`|`in_progress`|`completed` | May be repeated. Default: all. |
| `priority` | `low`|`medium`|`high` | May be repeated. |
| `project_id` | uuid | Only this project. A project the caller is not in gives an empty list. |
| `due_after` | date | Due on or after (tasks without a due date are excluded). |
| `due_before` | date | Due on or before (tasks without a due date are excluded). |
| `overdue` | boolean | `true`: due before today (UTC) and not completed. `false`: the complement. |
| `sort` | enum | Same values and default as the project task list. |
| `page` | int 1-100000 | Default 1. |
| `page_size / limit` | int 1-100 | Default 20. `limit` is an alias. |

**Request body:** None.

**Response:** `PagedEnvelope<AssignedTaskOut>`: every `TaskOut` field plus `project: {id, name, status}`.

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token, or the user is inactive. |
| 422 | `VALIDATION_ERROR` | Malformed or invalid path id, query or body; unknown body fields are rejected. |

**Example request**

```http
GET /api/v1/me/tasks?sort=due_date HTTP/1.1
Cookie: access_token=<access-token-jwt>
```

**Example response**

```http
HTTP/1.1 200 OK

{
  "data": [
    {
      "id": "00000000-0000-4000-8000-000000000014",
      "project_id": "00000000-0000-4000-8000-000000000005",
      "title": "Design login page",
      "description": "Wireframes and copy",
      "status": "completed",
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
      "position": 1024.0,
      "completed_at": "2026-11-15T10:00:07Z",
      "allowed_actions": [
        "update",
        "complete"
      ],
      "created_at": "2026-11-15T10:00:04Z",
      "updated_at": "2026-11-15T10:00:08Z",
      "project": {
        "id": "00000000-0000-4000-8000-000000000005",
        "name": "Website redesign",
        "status": "active"
      }
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 1,
    "total_pages": 1
  }
}
```

**Example error response** (422)

```http
HTTP/1.1 422 Unprocessable Content

{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "details": [
      {
        "field": "status.0",
        "message": "Input should be 'todo', 'in_progress' or 'completed'",
        "policy_id": null
      }
    ],
    "request_id": "00000000-0000-4000-8000-000000000021"
  }
}
```

**Rules**

- Completed tasks are included unless `status` filters them out.
- A member who is removed from a project stops seeing its tasks immediately (their assignments there are also cleared).
- Projects, creators and assignees come from joins: two queries per page.

### 3.6 Dashboard and activity

#### 3.6.1 GET /api/v1/dashboard/stats

**Authentication:** Access-token cookie (`access_token`)

**Authorization policy:** Data scoping: only projects the caller is a CURRENT member of.

**Query parameters**

None.

**Request body:** None.

**Response:** `Envelope<DashboardStats>`. `pending` = todo + in_progress. `overdue` = due before today (UTC) and not completed. `assigned_to_me` = assigned to the caller and not completed. `recent_activity` = the 10 newest entries.

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token, or the user is inactive. |

**Example request**

```http
GET /api/v1/dashboard/stats HTTP/1.1
Cookie: access_token=<access-token-jwt>
```

**Example response**

```http
HTTP/1.1 200 OK

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
        "id": "00000000-0000-4000-8000-000000000022",
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
        "created_at": "2026-11-15T10:00:09Z"
      },
      {
        "id": "00000000-0000-4000-8000-000000000023",
        "user": {
          "id": "00000000-0000-4000-8000-000000000009",
          "email": "cy@example.com",
          "name": "Cy Dunn"
        },
        "project_id": "00000000-0000-4000-8000-000000000005",
        "task_id": "00000000-0000-4000-8000-000000000014",
        "action": "task.status_changed",
        "metadata": {
          "to": "completed",
          "from": "in_progress",
          "position": 1024.0
        },
        "created_at": "2026-11-15T10:00:08Z"
      },
      {
        "id": "00000000-0000-4000-8000-000000000024",
        "user": {
          "id": "00000000-0000-4000-8000-000000000007",
          "email": "ben@example.com",
          "name": "Ben Carter"
        },
        "project_id": "00000000-0000-4000-8000-000000000005",
        "task_id": "00000000-0000-4000-8000-000000000014",
        "action": "task.status_changed",
        "metadata": {
          "to": "in_progress",
          "from": "todo",
          "position": 2048.0
        },
        "created_at": "2026-11-15T10:00:06Z"
      },
      {
        "id": "00000000-0000-4000-8000-000000000025",
        "user": {
          "id": "00000000-0000-4000-8000-000000000007",
          "email": "ben@example.com",
          "name": "Ben Carter"
        },
        "project_id": "00000000-0000-4000-8000-000000000005",
        "task_id": "00000000-0000-4000-8000-000000000014",
        "action": "task.updated",
        "metadata": {
          "changes": {
            "due_date": [
              "2099-12-31",
              "2099-06-30"
            ],
            "priority": [
              "high",
              "medium"
            ]
          }
        },
        "created_at": "2026-11-15T10:00:05Z"
      },
      {
        "id": "00000000-0000-4000-8000-000000000026",
        "user": {
          "id": "00000000-0000-4000-8000-000000000007",
          "email": "ben@example.com",
          "name": "Ben Carter"
        },
        "project_id": "00000000-0000-4000-8000-000000000005",
        "task_id": "00000000-0000-4000-8000-000000000018",
        "action": "task.created",
        "metadata": {
          "title": "Build API",
          "status": "in_progress",
          "priority": "medium",
          "assignee_id": null
        },
        "created_at": "2026-11-15T10:00:10Z"
      },
      {
        "id": "00000000-0000-4000-8000-000000000027",
        "user": {
          "id": "00000000-0000-4000-8000-000000000007",
          "email": "ben@example.com",
          "name": "Ben Carter"
        },
        "project_id": "00000000-0000-4000-8000-000000000005",
        "task_id": "00000000-0000-4000-8000-000000000020",
        "action": "task.created",
        "metadata": {
          "title": "Throwaway idea",
          "status": "todo",
          "priority": "medium",
          "assignee_id": null
        },
        "created_at": "2026-11-15T10:00:11Z"
      },
      {
        "id": "00000000-0000-4000-8000-000000000028",
        "user": {
          "id": "00000000-0000-4000-8000-000000000007",
          "email": "ben@example.com",
          "name": "Ben Carter"
        },
        "project_id": "00000000-0000-4000-8000-000000000005",
        "task_id": "00000000-0000-4000-8000-000000000029",
        "action": "task.created",
        "metadata": {
          "title": "Fix signup bug",
          "status": "todo",
          "priority": "medium",
          "assignee_id": "00000000-0000-4000-8000-000000000007"
        },
        "created_at": "2026-11-15T10:00:12Z"
      },
      {
        "id": "00000000-0000-4000-8000-000000000030",
        "user": {
          "id": "00000000-0000-4000-8000-000000000007",
          "email": "ben@example.com",
          "name": "Ben Carter"
        },
        "project_id": "00000000-0000-4000-8000-000000000005",
        "task_id": "00000000-0000-4000-8000-000000000014",
        "action": "task.created",
        "metadata": {
          "title": "Design login page",
          "status": "todo",
          "priority": "high",
          "assignee_id": "00000000-0000-4000-8000-000000000009"
        },
        "created_at": "2026-11-15T10:00:04Z"
      },
      {
        "id": "00000000-0000-4000-8000-000000000031",
        "user": {
          "id": "00000000-0000-4000-8000-000000000001",
          "email": "ana@example.com",
          "name": "Ana Lopez"
        },
        "project_id": "00000000-0000-4000-8000-000000000005",
        "task_id": null,
        "action": "project.updated",
        "metadata": {
          "changes": {
            "description": [
              "Q4 launch",
              "Q4 launch of the new marketing site"
            ]
          }
        },
        "created_at": "2026-11-15T10:00:03Z"
      },
      {
        "id": "00000000-0000-4000-8000-000000000032",
        "user": {
          "id": "00000000-0000-4000-8000-000000000001",
          "email": "ana@example.com",
          "name": "Ana Lopez"
        },
        "project_id": "00000000-0000-4000-8000-000000000005",
        "task_id": null,
        "action": "member.added",
        "metadata": {
          "member_user_id": "00000000-0000-4000-8000-000000000009"
        },
        "created_at": "2026-11-15T10:00:02Z"
      }
    ]
  }
}
```

**Rules**

- Three queries in total, however much data exists.

#### 3.6.2 GET /api/v1/dashboard/activity

**Authentication:** Access-token cookie (`access_token`)

**Authorization policy:** Data scoping: only projects the caller is a CURRENT member of.

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `page` | int 1-100000 | Default 1. |
| `page_size / limit` | int 1-100 | Default 20. `limit` is an alias. |

**Request body:** None.

**Response:** `PagedEnvelope<ActivityOut>`, newest first.

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token, or the user is inactive. |
| 422 | `VALIDATION_ERROR` | Malformed or invalid path id, query or body; unknown body fields are rejected. |

**Example request**

```http
GET /api/v1/dashboard/activity?page=1&limit=3 HTTP/1.1
Cookie: access_token=<access-token-jwt>
```

**Example response**

```http
HTTP/1.1 200 OK

{
  "data": [
    {
      "id": "00000000-0000-4000-8000-000000000022",
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
      "created_at": "2026-11-15T10:00:09Z"
    },
    {
      "id": "00000000-0000-4000-8000-000000000023",
      "user": {
        "id": "00000000-0000-4000-8000-000000000009",
        "email": "cy@example.com",
        "name": "Cy Dunn"
      },
      "project_id": "00000000-0000-4000-8000-000000000005",
      "task_id": "00000000-0000-4000-8000-000000000014",
      "action": "task.status_changed",
      "metadata": {
        "to": "completed",
        "from": "in_progress",
        "position": 1024.0
      },
      "created_at": "2026-11-15T10:00:08Z"
    },
    {
      "id": "00000000-0000-4000-8000-000000000024",
      "user": {
        "id": "00000000-0000-4000-8000-000000000007",
        "email": "ben@example.com",
        "name": "Ben Carter"
      },
      "project_id": "00000000-0000-4000-8000-000000000005",
      "task_id": "00000000-0000-4000-8000-000000000014",
      "action": "task.status_changed",
      "metadata": {
        "to": "in_progress",
        "from": "todo",
        "position": 2048.0
      },
      "created_at": "2026-11-15T10:00:06Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 3,
    "total": 12,
    "total_pages": 4
  }
}
```

**Rules**

- Entries without a project (login, logout, registration) never appear.
- A removed member stops seeing the project's activity immediately.

#### 3.6.3 GET /api/v1/projects/{project_id}/activity

**Authentication:** Access-token cookie (`access_token`)

**Authorization policy:** Policy `project.view`: current members only.

**Query parameters**

| Name | Type | Description |
|---|---|---|
| `page` | int 1-100000 | Default 1. |
| `page_size / limit` | int 1-100 | Default 20. `limit` is an alias. |

**Request body:** None.

**Response:** `PagedEnvelope<ActivityOut>`, newest first.

**Error responses**

| Status | Code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired access token, or the user is inactive. |
| 404 | `NOT_FOUND` | Missing project or not a member. |
| 422 | `VALIDATION_ERROR` | Malformed or invalid path id, query or body; unknown body fields are rejected. |

**Example request**

```http
GET /api/v1/projects/00000000-0000-4000-8000-000000000005/activity?limit=3 HTTP/1.1
Cookie: access_token=<access-token-jwt>
```

**Example response**

```http
HTTP/1.1 200 OK

{
  "data": [
    {
      "id": "00000000-0000-4000-8000-000000000022",
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
      "created_at": "2026-11-15T10:00:09Z"
    },
    {
      "id": "00000000-0000-4000-8000-000000000023",
      "user": {
        "id": "00000000-0000-4000-8000-000000000009",
        "email": "cy@example.com",
        "name": "Cy Dunn"
      },
      "project_id": "00000000-0000-4000-8000-000000000005",
      "task_id": "00000000-0000-4000-8000-000000000014",
      "action": "task.status_changed",
      "metadata": {
        "to": "completed",
        "from": "in_progress",
        "position": 1024.0
      },
      "created_at": "2026-11-15T10:00:08Z"
    },
    {
      "id": "00000000-0000-4000-8000-000000000024",
      "user": {
        "id": "00000000-0000-4000-8000-000000000007",
        "email": "ben@example.com",
        "name": "Ben Carter"
      },
      "project_id": "00000000-0000-4000-8000-000000000005",
      "task_id": "00000000-0000-4000-8000-000000000014",
      "action": "task.status_changed",
      "metadata": {
        "to": "in_progress",
        "from": "todo",
        "position": 2048.0
      },
      "created_at": "2026-11-15T10:00:06Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 3,
    "total": 12,
    "total_pages": 4
  }
}
```

**Example error response** (404)

```http
HTTP/1.1 404 Not Found

{
  "error": {
    "code": "NOT_FOUND",
    "message": "Resource not found.",
    "details": [],
    "request_id": "00000000-0000-4000-8000-000000000033"
  }
}
```

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
