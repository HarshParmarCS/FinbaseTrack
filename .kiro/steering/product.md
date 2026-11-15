# FinTasks: Product Definition

> Source of truth for WHAT we build. Detailed requirement IDs live in `docs/requirements.md`.
> The product name is **FinTasks** (the repository folder is `FinbaseTrack`).

## Purpose

FinTasks is a lightweight project management platform inspired by Jira, Linear and Trello. It is the deliverable for the Finbase Full Stack Engineer assignment (`docs/Full_Stack_Engineer_Assignment.pdf`). The goal is a production-oriented, well-architected application whose design decisions the author can fully explain in a review.

## Target users

- **Small teams** that need to organize work into projects and tasks.
- **Project owners** who create a project, invite registered users as members and control its settings.
- **Project members** who create, update and complete tasks inside projects they belong to.
- **Reviewers** at Finbase, who run `docker compose up --build`, exercise the app and read the code.

There are NO roles. Every capability is decided by policies evaluated against the authenticated user, the action and the resource (see `docs/authorization-design.md`). "Owner" is a relationship between a user and a project, not a role.

## Functional requirements (summary)

### Authentication
- Register, log in, log out.
- JWT access tokens (15 minutes) and rotating refresh tokens (7 days), both in HttpOnly cookies.
- All APIs except register, login, refresh and health are protected.
- Passwords hashed with Argon2.

### Projects
- Create, view, update, delete projects.
- Project fields: name, description, status (`active` or `archived`).
- Add and remove members (owner only, by email of an already registered user).
- Projects are visible only to their members.

### Tasks
- Create, view, update, delete tasks inside a project.
- Task fields: title, description, status, priority, assignee, due date, created by, created and updated timestamps, board position.
- Statuses: `todo`, `in_progress`, `completed`. Priorities: `low`, `medium`, `high`.
- Search by text. Filter by status, priority, assignee, overdue. Paginate and sort.
- Assign tasks to project members only.

### Dashboard
Total projects, active projects, total tasks, completed tasks, pending tasks, overdue tasks, tasks assigned to me, recent activity.

### Additional features
- Activity timeline per project and per user, backed by the `activity_logs` table (audit trail).
- Drag-and-drop Kanban board (status dropdown is the fallback and must always work).
- Refresh token rotation.
- Configurable JSON policy definitions.
- Responsive UI with loading, empty and error states and clear user feedback.

## Business rules

| # | Rule |
|---|---|
| BR-1 | Only project members can view a project. Non-members receive 404, never 403, so project existence is not leaked. |
| BR-2 | Only the project owner can update or delete a project. |
| BR-3 | The owner is automatically a member and can never be removed or replaced. Ownership transfer is out of scope. |
| BR-4 | Only the owner can add or remove members. Members are added by email and the user must already be registered. |
| BR-5 | Only project members can create tasks. Task operations verify CURRENT membership on every request. |
| BR-6 | A task can be updated by its creator OR its assignee, and only while that user is still a project member. The owner does not gain update rights by being the owner. |
| BR-7 | A task can be deleted only if its status is `todo` AND the requester is the project owner. |
| BR-8 | A task can be in status `completed` only if it has an assignee AND all required information is present (title, description, priority, due date and an assignee who is a current member). The required field list is configured in the policy file. |
| BR-9 | Any write that results in status `completed` (create or update) must satisfy BR-8, evaluated against the resulting state of the task. |
| BR-10 | Only project members can be assigned tasks. |
| BR-11 | Removing a member revokes access immediately and unassigns that member's tasks in the same transaction. |
| BR-12 | Authorization decisions use only the user identified by the verified JWT. User IDs sent by the client are never used to decide access. |
| BR-13 | Deleting a project hard-deletes its members and tasks. Audit entries are kept. |

## Dashboard definitions

All statistics are scoped to projects where the current user is a member.

- **Total projects**: projects the user is a member of.
- **Active projects**: those with `status = active`.
- **Total tasks**: tasks in those projects.
- **Completed tasks**: `status = completed`.
- **Pending tasks**: `status` in (`todo`, `in_progress`).
- **Overdue tasks**: `due_date` before today (UTC) and `status != completed`.
- **Assigned to me**: tasks assigned to the user with `status != completed`.
- **Recent activity**: the 10 most recent audit entries in the user's projects.

## Scope

### In scope (Tier 1: mandatory, ships first)
Everything the assignment marks mandatory: auth, projects, tasks, PBAC with the seven required policies, normalized schema, required frontend pages (Login, Register, Dashboard, Project Listing, Project Details, Task Details), validation, loading/empty/error states, Docker and Docker Compose, tests, README, `.env.example`, migrations, Swagger/OpenAPI, clean Git history.

### In scope (Tier 2: bonus, cut last to first if time runs out)
Configurable JSON PBAC, audit log and activity timeline, refresh token rotation, GitHub Actions CI, drag-and-drop board, integration tests, overdue and assigned-to-me statistics.

### Cut order if time runs short
1. Playwright smoke test.
2. Drag-and-drop (keep the status dropdown).
3. Refresh token reuse detection (keep rotation).
4. Activity timeline UI (keep the API).

### Out of scope (Tier 3)
Roles or RBAC of any kind, WebSockets, email notifications, file attachments, Redis, background jobs, ownership transfer, invitations to unregistered users, password reset, social login, soft delete.

## Quality bar

- Clean layered architecture. Authorization separated from business logic.
- Consistent API envelope and proper HTTP status codes.
- Every PBAC policy has allow, deny and default-deny tests.
- The app runs with one command: `docker compose up --build`.
- The author can explain every part of the code.
