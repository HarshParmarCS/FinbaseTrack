# Finbase Workdesk

A project and task management app for small teams, built for the Finbase Full Stack Engineer
assignment (`req_docs/Full_Stack_Engineer_Assignment.pdf`). Teams create projects, add members,
plan tasks, move them from To do to Completed, and follow everything that happens in an activity
timeline.

The product name in the UI is **Finbase Workdesk**. The code started as "FinTasks", and the
backend, database and tokens still use that name internally (`fintasks` database, JWT issuer
`fintasks-api`). Renaming those would log every user out and break existing local databases, so
they were left alone on purpose.

Access is decided by a **policy-based (PBAC) engine** with rules in a JSON file. There are no
roles anywhere in the code or the database.

## Status

What works today, checked on 16 November 2026:

| Area | State |
|---|---|
| Backend API (23 endpoints) | Done. 970 tests pass, 99% line coverage, ruff and mypy clean |
| Database schema and migration | Done. One Alembic migration, `alembic check` reports no drift |
| Authentication (cookies, refresh rotation, CSRF) | Done, tested against the real API |
| Authorization (PBAC, 9 policies) | Done |
| Frontend: sign-in, register, dashboard, projects, members, tasks, activity, settings | Done. 367 unit tests and 70 end-to-end tests against the running backend |
| Visual design (Finbase-style theme, central color tokens) | Done |
| OpenAPI export and Swagger UI | Done (`docs/openapi.json`, `/docs`) |
| Kanban board with drag and drop | **Not built.** Status is changed with a dropdown |
| "My Tasks" page with a combined list | **Not built.** The backend has no cross-project task list (see Limitations) |
| Dockerfiles for backend and frontend | **Not built.** `docker-compose.yml` only runs PostgreSQL |
| `docker compose up --build` for the whole stack | **Not possible yet** (depends on the line above) |
| GitHub Actions CI | **Not built** |
| Playwright browser tests | **Not built.** End-to-end checks use Vitest + jsdom against the live API instead |

## What a user can do

**Accounts**
- Register with name, email and password (8 to 128 characters). Registering also signs you in.
- Sign in and sign out. Sign-out is at the bottom of the sidebar.
- Sessions survive a page reload. An expired 15-minute access token is refreshed silently. When the
  session really ends (refresh token expired, revoked, or reused), you are sent to the sign-in
  page with a message.

**Projects**
- Create, rename, describe, archive and delete projects.
- See only the projects you belong to. Search by name, filter by status, page through results.
- The creator is the owner and is always a member. The owner adds members by the email of an
  already registered user, and can remove them. Removing a member cuts their access at once and
  unassigns their tasks in that project.

**Tasks**
- Create tasks with title, description, priority (low, medium, high), due date and assignee.
  Assignees can only be project members.
- Change status along `To do <-> In progress <-> Completed` (no jumping from To do to Completed).
- Search title and description. Filter by status and priority (several at once), assignee or
  "unassigned", due date range and "overdue". Sort by created, updated, due date, priority or
  board position. 20 per page in the UI (the API allows up to 100).

**Dashboard**
- Totals: projects, active projects, tasks, completed, pending, overdue, assigned to me, and a
  completion percentage worked out from those numbers.
- Your open assigned tasks, upcoming due dates, a project overview with progress bars, a task
  status breakdown and the latest activity.
- Quick "New project" and "New task" actions.

**Activity**
- A day-grouped timeline of everything in your projects (`/activity`), and one per project on the
  project page. Each entry says who did what, to which task or project, and when.

## Permission rules

All decisions are made by `backend/app/authorization/`. Services call it before every change. The
rules are in `backend/app/authorization/policies.json` and are checked at startup.

| Action | Who may do it |
|---|---|
| Create a project | Any signed-in user |
| View a project, its tasks, members and activity | Current members only. Everyone else gets **404**, so a project's existence is not revealed |
| Update or delete a project | The owner |
| Add or remove members | The owner (the owner cannot be removed) |
| Create a task | Any current member |
| Update a task or change its status | Its creator or its assignee, while still a member. Being the owner does not add update rights |
| Delete a task | The owner, and only while the task is To do |
| Complete a task | Only when it has an assignee, title, description, priority and due date |

Members who are refused get **403** with the name of the policy that refused them. The frontend
only shows buttons the backend lists in `allowed_actions`, but the backend checks every request
anyway, so hiding a button is never the security boundary.

## How it is built

```
Browser ──> Next.js (port 3000) ── /api/* rewrite ──> FastAPI (port 8000) ──> PostgreSQL 16
```

**Backend** (`backend/`): Python 3.12, FastAPI, SQLAlchemy 2.0 (sync), Alembic, Pydantic v2,
PyJWT, argon2-cffi.
- Layers: routers (HTTP only), services (business rules and transactions), repositories
  (queries only), models.
- Errors use one envelope: `{"error": {"code", "message", "details", "request_id"}}`.
- Every change writes an audit row in the same transaction.
- Passwords are hashed with Argon2.
- Tokens are JWTs in HttpOnly cookies: a 15-minute access token, and a 7-day refresh token that is
  stored only as a SHA-256 hash and rotated on every use. Reusing an old refresh token revokes the
  whole token family.
- Changes need a matching `X-CSRF-Token` header and an allowed `Origin`.

**Frontend** (`frontend/`): Next.js 16 (App Router), React 19, TypeScript (strict), Tailwind CSS 4,
shadcn/ui (Radix), TanStack Query, React Hook Form, Zod, sonner for toasts, Lucide icons.
- One API client (`src/lib/api/client.ts`) handles cookies, CSRF, errors, and one shared
  refresh-and-retry on a 401.
- Forms validate with the same limits as the backend and show server errors on the right field.
- Every list and card has loading, empty and error states.
- All colors are tokens in `src/app/globals.css`, and a test fails the build if a component uses a
  raw color.

**Database**: UUID keys, `timestamptz`, status and priority as `varchar` with `CHECK` constraints,
and a composite foreign key that makes it impossible to assign a task to a non-member. Project
deletes are hard deletes. Activity rows have no foreign keys, so history survives deletion.

## Running it locally

You need Python 3.12, Node.js 20 or newer, pnpm, and Podman or Docker for PostgreSQL.

```bash
# 1. Database (from the repository root)
cp .env.example .env                 # set POSTGRES_PASSWORD
podman compose up -d db              # or: docker compose up -d db  (PostgreSQL on 127.0.0.1:5433)

# 2. Backend (from backend/)
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -r requirements-dev.txt
cp .env.example .env                 # set DATABASE_URL, TEST_DATABASE_URL and JWT_SECRET_KEY
alembic upgrade head
uvicorn app.main:app --reload        # http://localhost:8000, Swagger at /docs

# 3. Frontend (from frontend/)
pnpm install
pnpm dev                             # http://localhost:3000
```

The frontend must run on port **3000** (the dev script pins it), so make sure nothing else is
using that port. The backend only accepts browser requests from `http://localhost:3000`
(`ALLOWED_ORIGINS`). Use `localhost`, not `127.0.0.1`, because cookies are per host. Step-by-step details are in
`backend/README.md` and `frontend/README.md`.

## Tests

```bash
cd backend && pytest                 # 970 tests on a real PostgreSQL test database (needs TEST_DATABASE_URL)
cd backend && ruff check . && mypy && alembic check

cd frontend && pnpm test             # 367 unit and component tests, no network
cd frontend && pnpm test:live        # 70 end-to-end tests against the running backend on :8000
cd frontend && pnpm lint && pnpm typecheck && pnpm build
```

- **What the backend tests cover:** every policy has allow, deny and default-deny tests. They also
  cover token expiry and tampering, refresh reuse, CSRF, removed members losing access, and audit
  rows for each change. Structural tests check that every non-public route requires
  authentication, that every service asks the policy engine before touching data, and that
  `docs/api-contract.md` and `docs/openapi.json` match the code.
- **What the live frontend tests do:** they register real throwaway users
  (`authlive-…@example.com`, `projlive-…`, `tasklive-…`, `actlive-…`) and drive the real pages
  against the real API. They delete the projects they create, but the users and their audit rows
  stay in your development database.
- **The other suites:** both test suites run fully in-process. The browser itself was not used for
  automated testing.

## API documentation

- Swagger UI: `http://localhost:8000/docs`, raw schema at `/openapi.json`.
- `docs/api-contract.md`: every endpoint with auth, policy, parameters, schemas, errors and real
  examples. Section 3 is generated from the running app by `python -m scripts.generate_api_docs`
  (from `backend/`).
- `docs/frontend-api-contract.md`: what the frontend relies on, plus the backend gaps found while
  building it.
- `docs/postman/fintasks.postman_collection.json`: 62 requests that walk through the main flows
  (it adds the CSRF header for you).

## Limitations and known gaps

These are real and not hidden in the UI:

- **No combined task list:** there is no endpoint that lists tasks across projects. The dashboard
  asks each project with open work, up to 10 projects, and says when its list is partial. The
  "My Tasks" page explains this instead of showing data.
- **Activity has some gaps:**
  - There is no feed of only your own actions.
  - Sign-in events are recorded but no endpoint returns them.
  - Entries written in the same transaction share a timestamp, so their order within that group
    is not defined.
  - Entries carry ids rather than names, so a name that no other response mentions shows as
    "a task" or "a member".
- **Accepted security trade-offs:**
  - No login rate limiting.
  - No cleanup job for expired refresh tokens.
  - No request body size limit.
  - An access token stays valid until it expires (up to 15 minutes) after logout.
  - Swagger stays enabled.
- **Missing features:** no password reset, email, file attachments, invitations for unregistered
  users, ownership transfer or dark mode.
- **Colors:** the theme follows Finbase reference screenshots in `frontend/reference/`. The colors
  were estimated from those images, not taken from an official brand guide, and the mark is
  original artwork, not the Finbase logo.

## Documentation

| File | Contents |
|---|---|
| `docs/requirements.md` | Requirements, assumptions and accepted risks |
| `docs/database-design.md` | Tables, constraints and indexes |
| `docs/authorization-design.md` | How the PBAC engine and policies work |
| `docs/api-contract.md` | Full REST contract |
| `docs/frontend-api-contract.md` | Frontend view of the API and the gaps (G1 to G15) |
| `docs/implementation-roadmap.md` | Milestones and what each one delivered |
| `backend/README.md`, `frontend/README.md` | Setup, commands and design notes per app |
| `.kiro/steering/*.md` | Product rules, architecture, coding standards and workflow |

## How this was made

The project was built milestone by milestone with the Kiro AI coding assistant, guided by the
steering files in `.kiro/steering/` (product rules, architecture, coding standards, workflow).
Each milestone was planned, reviewed and accepted before the next one started, and was checked
by the test suites above.
