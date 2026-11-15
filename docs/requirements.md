# FinTasks: Requirements

Source: `docs/Full_Stack_Engineer_Assignment.pdf` (Finbase) plus the decisions approved in planning. Product summary: `.kiro/steering/product.md`.

Tier legend: **T1** mandatory in the assignment, **T2** bonus (implemented, cut last to first), **X** out of scope.

## 1. Functional requirements

### Authentication
| ID | Requirement | Tier |
|---|---|---|
| FR-AUTH-1 | A user can register with email, full name and password. Email is unique, case-insensitive. Password minimum 8 characters. | T1 |
| FR-AUTH-2 | A user can log in with email and password. Failure message is generic. | T1 |
| FR-AUTH-3 | A user can log out. Logout clears cookies and revokes the refresh token. | T1 |
| FR-AUTH-4 | Passwords are hashed with Argon2. | T1 |
| FR-AUTH-5 | JWT access tokens (15 min) are validated on every protected request (signature, expiry, type). | T1 |
| FR-AUTH-6 | Tokens are delivered in HttpOnly cookies only. | T1 |
| FR-AUTH-7 | Refresh tokens (7 days) rotate on every use. Reuse of a rotated token is rejected. | T2 |
| FR-AUTH-8 | Reuse of a rotated refresh token revokes the whole token family. | T2 |
| FR-AUTH-10 | State-changing requests that carry auth cookies are CSRF-protected (Origin check and `X-CSRF-Token`). CORS allows only configured origins. | T1 |
| FR-AUTH-9 | `GET /auth/me` returns the current user. | T1 |

### Projects
| ID | Requirement | Tier |
|---|---|---|
| FR-PRJ-1 | Any authenticated user can create a project and becomes its owner and first member. | T1 |
| FR-PRJ-2 | A user can list only projects they are a member of, with search, status filter and pagination. | T1 |
| FR-PRJ-3 | A member can view a project. Non-members get 404. | T1 |
| FR-PRJ-4 | Only the owner can update name, description and status (`active` or `archived`). | T1 |
| FR-PRJ-5 | Only the owner can delete a project. Members and tasks are deleted with it by database cascade, in one transaction. Activity history is kept. | T1 |
| FR-PRJ-6 | Only the owner can add a member by email. The user must be registered. Duplicate gives 409. | T1 |
| FR-PRJ-7 | Only the owner can remove a member. The owner cannot be removed. | T1 |
| FR-PRJ-8 | Removing a member unassigns their tasks in the same transaction and immediately revokes access. | T1 |
| FR-PRJ-9 | Members can list the project's members. | T1 |

### Tasks
| ID | Requirement | Tier |
|---|---|---|
| FR-TSK-1 | A project member can create a task (title required, priority default `medium`, status default `todo`). | T1 |
| FR-TSK-2 | A member can list a project's tasks and view a task. | T1 |
| FR-TSK-3 | A task can be updated by its creator or its assignee (while still a member). | T1 |
| FR-TSK-4 | A task can be deleted only by the project owner and only when its status is `todo`. | T1 |
| FR-TSK-5 | Search by text across title and description. | T1 |
| FR-TSK-6 | Filter by status, priority, assignee and overdue. | T1 |
| FR-TSK-7 | Pagination (`page`, `page_size`) and sorting. | T1 |
| FR-TSK-8 | A task may be assigned only to a project member. | T1 |
| FR-TSK-9 | A task has an optional due date, created and updated timestamps, and a creator (`creator_id`). | T1 |
| FR-TSK-10 | A task can be in status `completed` only if it has an assignee and all required information (title, description, assignee, due date). | T1 |
| FR-TSK-11 | Tasks have a board `position` used for ordering within a status column. | T2 |

### Authorization
| ID | Requirement | Tier |
|---|---|---|
| FR-AZ-1 | All authorization uses a centralized PBAC engine. RBAC is prohibited. | T1 |
| FR-AZ-2 | The engine is default-deny. | T1 |
| FR-AZ-3 | The seven mandatory policies (`project.view`, `project.update`, `project.delete`, `task.create`, `task.update`, `task.delete`, `task.complete`) are implemented. | T1 |
| FR-AZ-4 | Authorization is separated from business logic: decisions are made only by the policy engine, and services enforce them with one `require(...)` call before mutating. | T1 |
| FR-AZ-5 | Policies are defined in a JSON file validated at startup. | T2 |
| FR-AZ-6 | Authorization uses only the user from the verified JWT. | T1 |
| FR-AZ-7 | Responses include `allowed_actions` for projects and tasks so the UI can show or hide controls. | T2 |

### Dashboard and activity
| ID | Requirement | Tier |
|---|---|---|
| FR-DSH-1 | Dashboard shows total, active projects, total, completed, pending, overdue tasks, tasks assigned to me, recent activity. (PDF mandates total projects, active projects, total, completed and pending tasks. Overdue, assigned-to-me and recent activity are extras.) | T1 / T2 |
| FR-ACT-1 | Mutations write activity log entries (`activity_logs`) in the same transaction. Project and member mutations do so from M5; task mutations from M6. | T2 |
| FR-ACT-2 | A project activity timeline and a user-level recent activity feed are available to members. | T2 |

### Frontend
| ID | Requirement | Tier |
|---|---|---|
| FR-UI-1 | Pages: Login, Register, Dashboard, Project Listing, Project Details, Task Details. | T1 |
| FR-UI-2 | Form validation, loading indicators, empty states, error states, clear feedback. | T1 |
| FR-UI-3 | Responsive layout. | T1 |
| FR-UI-4 | Status change via dropdown. | T1 |
| FR-UI-5 | Drag-and-drop Kanban board. | T2 |
| FR-UI-6 | Members management for owners. | T1 |

## 2. Non-functional requirements

| ID | Requirement | Tier |
|---|---|---|
| NFR-1 | Clean architecture: routers, services, repositories, models separated. | T1 |
| NFR-2 | Centralized exception handling and consistent API envelope. | T1 |
| NFR-3 | Proper HTTP status codes, input validation, pagination, filtering, searching. | T1 |
| NFR-4 | Structured logging with request IDs. | T1 |
| NFR-5 | Environment-based configuration, `.env.example`. | T1 |
| NFR-6 | Alembic migrations. | T1 |
| NFR-7 | Automated tests (unit and API at minimum). Integration tests. | T1 / T2 |
| NFR-8 | Swagger/OpenAPI documentation. | T1 (encouraged in PDF) |
| NFR-9 | Docker, Docker Compose, `docker compose up --build` runs everything. | T1 |
| NFR-10 | GitHub Actions pipeline. | T2 |
| NFR-11 | README with: overview, architecture, technology choices, setup, Docker instructions, environment variables, API documentation, assumptions, trade-offs. | T1 |
| NFR-12 | Meaningful Git history (not a single commit). | T1 |
| NFR-13 | Security: see section 5. | T1 |

## 3. Assumptions

| ID | Assumption |
|---|---|
| A1 | Product name is FinTasks. The assignment does not name the product. |
| A2 | The owner is an automatic member and cannot be removed. Ownership transfer is out of scope. |
| A3 | Only the owner adds or removes members. Members are added by email of an existing user. No invitation flow. |
| A4 | Only members can be assigned tasks. Enforced by service validation AND a composite foreign key. |
| A5 | Membership is read from the database on every request, so removal takes effect immediately. |
| A6 | "Required task information" means non-blank title and description, a priority, a due date and an assignee who is a current project member. The list is configured in `policies.json`. |
| A7 | Task update is allowed for creator OR assignee only. The project owner does not gain update rights from ownership. The owner can still delete `todo` tasks. |
| A8 | "Task Delete: requesting user is the project owner" means the owner of the task's project. |
| A9 | Any write that results in status `completed` is checked against both `task.update` (or `task.create`) and `task.complete`, using the resulting state of the task. |
| A10 | "Active project" means project `status = active`. |
| A11 | "Pending task" means status `todo` or `in_progress`. |
| A12 | "Overdue task" means `due_date` is before today (UTC) and status is not `completed`. |
| A13 | "Assigned to me" counts tasks assigned to the user that are not completed. |
| A14 | Non-members receive 404 for projects and their tasks. Members who are denied by policy receive 403. |
| A15 | Deletes are hard deletes. Activity logs retain history because they have no foreign keys. |
| A16 | Removing a member unassigns their tasks. Tasks they created remain with `creator_id` unchanged. |
| A17 | Emails are normalized to lowercase. |
| A18 | A task's creator who is later removed from the project loses update rights, because update requires current membership. |
| A19 | Creating a project requires only authentication. It is expressed as a `project.create` policy added with the project endpoints (M5), because every action not covered by a policy is denied. |
| A21 | The database enforces that the project owner is a member (deferred composite foreign key), that assignees are members of the task's project (composite foreign key), unique membership, and valid status and priority values. |
| A22 | Task status follows a line: `todo` <-> `in_progress` <-> `completed`. Direct `todo` <-> `completed` moves are invalid. Status changes use a dedicated endpoint so that the completion policy cannot be bypassed. |
| A23 | When a task is already `completed`, editing it must keep it complete (assignee and required fields), because the completion policy is evaluated on the resulting state. |
| A24 | Text fields and search terms reject the NUL character (422), because PostgreSQL cannot store it. `page` is capped at 100000. |
| A25 | Authentication events (register, login, logout, refresh reuse detected) are written to `activity_logs` with no project. They appear only in the acting user's own feed (`GET /dashboard/activity`). |
| A26 | Accepted risks, not mitigated in this version: no login rate limiting, no purge of expired refresh tokens, no request body size limit, access tokens are valid until expiry (15 minutes) after logout, `/docs` stays enabled in production. |
| A20 | Dates: `due_date` is a calendar date (`YYYY-MM-DD`). Timestamps are UTC ISO 8601. |

## 4. Out of scope

Roles or RBAC, WebSockets, email notifications, file attachments, Redis caching, background jobs, ownership transfer, invitations for unregistered users, password reset, email verification, social login, soft delete, multi-tenancy, internationalization.

## 5. Security requirements

- Default-deny authorization, tested per policy.
- Argon2 password hashing. Generic login errors.
- HttpOnly, SameSite=Lax cookies (Secure outside local development). Refresh cookie scoped to `/api/v1/auth`.
- Origin check on mutating requests. Same-origin proxy.
- Refresh tokens stored hashed and rotated.
- Parameterized queries only. Input validated at trust boundaries.
- Secrets only from environment. Production refuses the placeholder secret.
- No secrets, tokens or passwords in logs.
- Non-root containers.

## 6. Deliverables (from the assignment)

GitHub repository, README, Swagger/OpenAPI (Postman collection optional), Docker configuration, `.env.example`, migration files, tests, clean commit history.

## 7. Acceptance checklist for the whole project

- [ ] `docker compose up --build` starts db, backend (migrated) and frontend from a clean clone.
- [ ] A user can register, log in, create a project, add a member, create and assign tasks, move a task through all statuses, and see the statistics.
- [ ] All seven mandatory policies are enforced and tested (allow, deny, default-deny).
- [ ] No RBAC constructs exist anywhere.
- [ ] Every item in section 6 exists.
