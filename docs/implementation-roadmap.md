# FinTasks: Implementation Roadmap

Milestones are implemented one at a time, in order, following `.kiro/steering/workflow.md`. Each milestone ends with passing tests, a report and user approval.

Time budget: about 2 to 3 days including the first day. Suggested pacing: Day 1 = M0 to M4, Day 2 = M5 to M9, Day 3 = M10 to M14. Tier 1 (mandatory) is finished before Tier 2 (bonus). Cut order when behind: see `.kiro/steering/product.md`.

Status legend: `[x]` done, `[ ]` not started.

## Milestones

### M0: Documentation and project instructions [x]
- Steering files, design documents, README, `.gitignore`, `.env.example`.
- Acceptance: all documents exist, are consistent, and describe an approved design.

### M1: Repository scaffold and backend skeleton [x]
- Create `backend/` (venv + requirements files, Ruff, mypy, pytest). No frontend folder yet. Follow-up added after M1: root `docker-compose.yml` with the PostgreSQL 16 `db` service (Podman or Docker), init script for `fintasks_test`, and root `.env.example`.
- FastAPI app with settings (`pydantic-settings`), JSON logging with request IDs, response envelope helpers, domain exceptions and centralized handlers, `GET /api/v1/health`, Alembic initialized, SQLAlchemy session dependency. The Origin-check middleware moves to M2, where it is needed with cookie authentication.
- Pytest harness against real PostgreSQL with per-test rollback.
- Tests: health endpoint, error envelope for 404 and 422, unhandled exception returns 500 envelope without a stack trace, settings reject the placeholder secret in production.
- Acceptance: with the compose database running, `pytest`, `ruff` and `mypy` pass, `alembic current` connects, and the app serves `/api/v1/health` and `/docs`.
- Commit: `chore: scaffold backend foundation`.

### M1b: Database schema [x]
- Models and the initial Alembic migration for `users`, `projects`, `project_members`, `tasks`, `activity_logs`, `refresh_tokens` (see `database-design.md`), plus model and migration tests. No endpoints.
- Acceptance: migration applies to and reverts from an empty PostgreSQL; models match the migration (no Alembic diff); constraint tests pass.
- Commit: `feat(db): add relational schema models and initial migration`.

### M2: Users and authentication [x]
- Also: CSRF protection (Origin check and double-submit token) and CORS (moved from M1). Auth events are also written to `activity_logs` (M7).
- Argon2 hashing, PyJWT access tokens, cookies, `get_current_user`.
- Endpoints: register, login, logout, me.
- Tests: duplicate email 409, generic login failure, expired and tampered token 401, cookie flags, logout clears cookies, password never returned or logged.
- Acceptance: endpoints 2, 3, 5 (cookie part), 6 in `api-contract.md` work as specified.
- Commit: `feat(auth): implement registration, login, logout and token validation`.

### M3: Refresh token rotation [x] (delivered together with M2)
- Hashed storage (table exists since M1b), rotation, revocation on logout, family revocation on reuse (stretch).
- Endpoint: `POST /auth/refresh`.
- Tests: rotation issues a new pair, old token rejected, expired token rejected, logout revokes, reuse revokes family (if implemented).
- Acceptance: a session survives access-token expiry via refresh.
- Commit: `feat(auth): add refresh token rotation`.

### M4: PBAC engine and policies [x]
- `authorization/` module (PEP, PDP, PAP, PIP), `policies.json` with the seven mandatory policies, startup validation, `AuthorizationService` for services and FastAPI providers. No project or task endpoints yet.
- Tests: the matrix in `authorization-design.md` section 11 (positive, negative, boundary per policy), engine fail-closed behavior, loader rejections, database-backed enforcement (removed member, guessed UUIDs), HTTP 401/403/404, structural checks (no RBAC, no eval).
- Acceptance: every policy has positive, negative and boundary tests; invalid policy configuration aborts startup.
- Commit: `feat(authz): add policy decision engine, registry and policies`.

### M5: Projects and members [x]
- Repositories, services, routers for endpoints 7 to 14. `allowed_actions`, `task_counts` (zero until M6), owner auto-membership.
- Tests: membership scoping of the list, 404 for non-members, owner-only update, delete and member management, duplicate member 409, unknown email 404, owner removal 422, removed member loses access immediately.
- Acceptance: the project policy rows of the matrix pass at API level.
- Commit: `feat(projects): add project and member management APIs`.

### M6: Tasks [x]
- Endpoints 15 to 19: CRUD, search, filters, sorting, pagination, `position`, `completed_at`.
- Assignee must be a member (422). Member removal unassigns tasks (integrates with M5).
- Tests: all task rows of the matrix, completion rules (create and update, clearing a field on a completed task), filters, search, pagination, sorting, assignee validation, unassign on removal, task counts in `ProjectOut`.
- Acceptance: the task policy rows of the matrix pass at API level.
- Commit: `feat(tasks): add task APIs with filters, pagination and completion rules`.

### M7: Audit log, activity and dashboard [x]
- Activity read side: endpoints 20 to 22. Project and member mutations already write activity rows (M5) and task mutations do from M6; this milestone adds the auth events and the dashboard.
- Tests: statistics against known fixtures (including overdue and assigned-to-me), activity scoped by membership, audit rows written for each mutation, no secrets in metadata.
- Acceptance: the dashboard payload matches the contract.
- Commit: `feat(dashboard): add statistics, activity timeline and audit logging`.

### M8: Backend containerization and API docs [x]
- Status (2026-11-16): `docs/openapi.json` exported and reconciled with `api-contract.md`. Backend `Dockerfile` (multi-stage, non-root), entrypoint with migrations under an advisory lock (`scripts/migrate.py`), and the `backend` compose service. Built and run with Podman.
- Backend `Dockerfile` (multi-stage, non-root), entrypoint runs `alembic upgrade head`, compose gets the `backend` service (the `db` service already exists). Optional seed script for demo data.
- Export `docs/openapi.json`, reconcile with `api-contract.md`.
- Tests: full backend suite; container smoke test (`/health`, register, login).
- Acceptance: `docker compose up --build` serves the API and Swagger; the backend is runnable from a clean clone.
- Commit: `build(backend): add Dockerfile, compose service and OpenAPI export`.
- **Backend complete. Frontend work starts after approval.**

### M9: Frontend foundation and authentication [x]
- Next.js app (TypeScript strict, Tailwind, shadcn/ui, TanStack Query, RHF, Zod, ESLint, Prettier, Vitest). `/api` rewrite to the backend. `lib/api.ts` with envelope parsing, `ApiError` and 401 refresh and retry. Types from the contract. App shell, route protection, toasts.
- Pages: Login, Register.
- Tests: Zod schemas, API client (envelope, errors, refresh and retry once, no retry loop), login form states.
- Acceptance: register, log in, log out against the running backend.
- Commit: `feat(web): add app foundation and authentication pages`.

### M10: Dashboard and project listing [x]
- Dashboard (stat cards, recent activity, assigned-to-me). Projects list with search, status filter, pagination, create, edit and delete dialogs. Loading, empty and error states.
- Tests: component tests for loading, empty and error states and for the project form.
- Acceptance: a user manages projects and sees correct statistics.
- Commit: `feat(web): add dashboard and project management UI`.

### M11: Project details, tasks and members [x]
- Project details with Tasks tab (filters, search, pagination, status dropdown), Members tab (owner management), task create and edit forms, Task Details page. Controls driven by `allowed_actions`. Server policy errors shown clearly (for example the completion rule reasons).
- Tests: filters, task form, permission-driven controls.
- Acceptance: the whole task workflow works in the browser.
- Commit: `feat(web): add project details, task management and members UI`.

### M12: Kanban board and activity tab (Tier 2) [partial]
- Status (2026-11-16): the activity timeline (per project and across projects) is done. Not done: the Kanban board and drag and drop; status changes use a dropdown.
- dnd-kit board with optimistic updates and rollback, status select fallback, activity tab.
- Tests: move handler and rollback on 403 and 422.
- Acceptance: dragging changes status; an illegal completion rolls back with a message.
- Commit: `feat(web): add Kanban board and activity timeline`.

### M13: Full-stack Docker Compose [x]
- Status (2026-11-16): `postgres`, `backend` and `frontend` services with health checks and a private network. Verified with `podman compose up --build`: all healthy, smoke test 38/38, live suite 70/70 through the proxy, browser check 24/24.
- Frontend `Dockerfile` (Next.js standalone, non-root), compose with `db`, `backend`, `frontend`, healthchecks, ordering, env wiring.
- Optional: Playwright smoke test (register, create project, create task, move task).
- Acceptance: from a clean clone, `docker compose up --build` runs the whole app and the full user flow works.
- Commit: `build: containerize frontend and finalize compose stack`.

### M14: CI/CD, README and final verification [partial]
- Status (2026-11-16): README, `docs/ASSIGNMENT_SUBMISSION.md` and `docs/assignment-compliance-matrix.md` written; final verification done. `.github/workflows/ci.yml` added and its commands run locally; it has not run on GitHub yet.
- GitHub Actions: backend (Ruff, mypy, pytest with Postgres service), frontend (lint, typecheck, test, build), Docker image builds.
- README completed (all sections the assignment requires). Optional Postman collection generated from OpenAPI.
- Final review: acceptance checklist in `requirements.md` section 7, Git history review, security checklist, requirements traceability, unfinished items list.
- Commit: `ci: add GitHub Actions pipeline` and `docs: finalize README and documentation`.

## Requirement coverage map

| Requirement group | Milestones |
|---|---|
| Authentication | M2, M3, M9 |
| PBAC | M4 (engine), M5, M6 (enforcement) |
| Projects and members | M5, M10, M11 |
| Tasks | M6, M11, M12 |
| Dashboard, activity, audit | M7, M10, M12 |
| Docker | M1 follow-up (db), M8 (backend), M13 (full) |
| CI/CD | M14 |
| Documentation | M0, M8, M14 |

## Risk register

| Risk | Mitigation |
|---|---|
| Time overrun | Tier order, cut order, one milestone at a time, backend first |
| PBAC complexity | Small engine, pure conditions, test matrix before routes |
| Contract drift between backend and frontend | Contract-first, OpenAPI export at M8, types checked against it |
| Cookie and proxy issues in Docker | Same-origin proxy tested in M13, `COOKIE_SECURE` configurable |
| Race conditions on member removal | Single transaction, composite FK RESTRICT as safety net |
| Drag-and-drop instability | Status select always available; M12 is Tier 2 |
