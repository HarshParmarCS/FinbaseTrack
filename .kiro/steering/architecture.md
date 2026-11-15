# FinTasks: Architecture

> Approved architecture. Do not change it silently. Any change requires an explicit proposal, user approval and an update to this file and the affected `docs/` files in the same commit.

## Approved technology stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (sync, typed `Mapped[]` style), psycopg 3, Alembic, Pydantic v2 + pydantic-settings, PyJWT, argon2-cffi |
| Database | PostgreSQL 16 (extensions: `pg_trgm`) |
| Backend tooling | venv + `requirements.txt` / `requirements-dev.txt` (`uv` may be used as a faster installer), Ruff (lint + format), mypy, pytest, httpx2 (Starlette's test client dependency) |
| Frontend | Next.js (App Router), React, TypeScript (strict), Tailwind CSS, shadcn/ui, TanStack Query, React Hook Form, Zod, dnd-kit |
| Frontend tooling | `pnpm`, ESLint, Prettier, Vitest + Testing Library, Playwright |
| Infrastructure | Docker, Docker Compose, GitHub Actions |

Decision: SQLAlchemy is used synchronously. FastAPI runs sync route functions in a threadpool. This is simpler to explain and test than async and is sufficient for the expected load.

## Repository layout

```
FinbaseTrack/
├── .kiro/steering/          # persistent agent instructions
├── docs/                    # design documents and the assignment PDF
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/            # config, logging, exceptions, middleware (security added in M2)
│   │   ├── database/        # base (declarative Base), session (engine + get_db)
│   │   ├── api/             # router.py mounts /api; v1/router.py mounts /v1 and the routers
│   │   ├── routers/         # HTTP only, one file per feature (health, auth, projects, tasks, ...)
│   │   ├── schemas/         # Pydantic request/response models, common envelopes
│   │   ├── services/        # business logic and transactions
│   │   ├── repositories/    # database queries only
│   │   ├── models/          # SQLAlchemy models (imported in models/__init__.py for Alembic)
│   │   ├── auth/            # password hashing, tokens (M2)
│   │   └── authorization/   # PBAC: engine, registry, policies, conditions, context, decision, policy_loader, information (PIP), service (PEP), policies.json
│   ├── alembic/  alembic.ini
│   ├── tests/               # test_*.py now; authorization/ and api/ sub-folders as they grow
│   ├── requirements.txt  requirements-dev.txt  pyproject.toml (tool config only)
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/             # routes (App Router)
│   │   ├── components/      # shared UI (ui/ = shadcn)
│   │   ├── features/        # auth, projects, tasks, members, dashboard, activity
│   │   ├── lib/             # api client, query client, utils
│   │   └── types/           # API types matching docs/api-contract.md
│   ├── tests/  e2e/
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## Component responsibilities

| Component | Responsibility | Must NOT |
|---|---|---|
| Router | HTTP only: parse and validate input via schemas, declare the authorization dependency, call one service method, return the envelope | Contain business logic, call repositories directly, make authorization decisions |
| Authorization dependency | Load the resource, build the `AuthorizationContext`, call `PolicyEngine`, map a denial to 403 or 404 | Contain business rules unrelated to access |
| Service | Business logic, transactions, domain validation (for example assignee must be a member), audit writes | Make authorization decisions, know about HTTP, build responses |
| Repository | Database access only: queries, inserts, updates, deletes | Make authorization decisions, contain business rules, commit transactions |
| Policy engine | Decide allow or deny from policies and context | Access HTTP objects or perform writes |
| Condition functions | Pure functions of the context returning bool | Do I/O except reading data already placed on the context |
| Exception handlers | Convert domain exceptions to the error envelope | Leak stack traces or internals |
| Frontend API client | Single place for fetch, cookies, envelope parsing, 401 refresh and retry | Invent response shapes |
| Feature modules (frontend) | Queries, mutations, forms and components for one domain area | Duplicate authorization rules (UI uses server-provided `allowed_actions`) |

## Request lifecycle

1. Browser calls `/api/v1/...` on the Next.js origin. The Next.js rewrite proxies it to the backend, so the browser sees one origin.
2. Middleware: request ID, structured logging, `Origin` check on mutating methods.
3. `get_current_user` verifies the `access_token` cookie (PyJWT: signature, expiry, type) and loads the active user. Failure gives 401.
4. The router validates input and calls ONE service method (no authorization code in routers).
5. The service first calls `AuthorizationService.require(user, action, ...)` (the PEP). It reads current facts from the database (PIP), the `PolicyEngine` (PDP) returns a `Decision`, and a denial raises a domain error: 404 for a missing resource or a non-member, 403 for a member denied by a policy. Only then does the service apply business rules inside a transaction, use repositories, write an activity entry and commit.
6. The router wraps the result in the response envelope. Exceptions are converted by centralized handlers.
7. Every denial and every mutation is logged with request ID, user ID, action and outcome. Secrets and tokens are never logged.

## Backend architecture

- **Layering:** router, service, repository, model. Dependencies point inward only. Services depend on repositories. Routers depend on services and schemas.
- **Layer-based layout:** code is grouped by layer (`routers/`, `schemas/`, `services/`, `repositories/`, `models/`), with one file per feature inside each layer (for example `routers/projects.py`, `services/project_service.py`). Cross-feature calls go through services.
- **Transactions:** one session per request, provided by a dependency. Services own the commit. Repositories never commit.
- **Config:** `pydantic-settings` reads environment variables. Production startup fails if `JWT_SECRET_KEY` is the placeholder.
- **Errors:** domain exceptions (`NotFoundError`, `ConflictError`, `BusinessRuleViolation`, `PermissionDeniedError`, `UnauthenticatedError`) map to HTTP codes in one handler module.
- **Auth:** Argon2 hashing. Access JWT (15 min) in an HttpOnly cookie. Refresh token is a JWT (audience `fintasks:refresh`), stored as a SHA-256 hash, rotated on every use, revoked on logout; reuse of a rotated token revokes its family.
- **Authorization:** the `authorization/` module is the only place that decides access. See `docs/authorization-design.md`.
- **Audit:** services call an audit helper after each mutation. Audit rows are written in the same transaction.

## Frontend architecture

- **Routing:** Next.js App Router. Routes: `/login`, `/register`, `/dashboard`, `/projects`, `/projects/[projectId]` (tabs: Tasks, Board, Members, Activity), `/projects/[projectId]/tasks/[taskId]`.
- **Server state:** TanStack Query. Query keys are defined once per feature. Mutations invalidate affected keys.
- **Forms:** React Hook Form with Zod schemas. Client validation mirrors server rules but the server is the authority.
- **API access:** `lib/api.ts` is the only code that calls `fetch`. It sends cookies, unwraps the envelope, throws a typed `ApiError`, and on a 401 calls `/auth/refresh` once, then retries the request once.
- **Types:** types in `src/types/` match `docs/api-contract.md` exactly. They may be generated from the exported `docs/openapi.json`.
- **Authorization in UI:** the UI shows or hides controls using `allowed_actions` returned by the API. It never re-implements policy logic. The server remains authoritative.
- **Route protection:** Next.js middleware redirects unauthenticated users to `/login`. The API still enforces everything.
- **UX:** every data view has loading (skeleton), empty and error states. Mutations give toast feedback. The layout is responsive (mobile first).

## Database architecture

- PostgreSQL 16, one schema, migrations only through Alembic (no `create_all` outside tests).
- UUID primary keys (`gen_random_uuid()`), `timestamptz` timestamps, status and priority stored as `varchar` with `CHECK` constraints.
- Referential integrity is enforced in the database, including a composite foreign key that guarantees task assignees are project members.
- Full detail: `docs/database-design.md`.

## Integration strategy

1. **Contract first:** `docs/api-contract.md` is the single source of truth. The backend implements it and the frontend consumes it. Any change updates the contract first.
2. **Backend before frontend:** the backend is complete and tested before frontend work starts. There is no mock API layer. The frontend is built directly against the running backend.
3. **Same origin:** Next.js rewrites `/api/*` to the backend (`BACKEND_INTERNAL_URL`). This avoids CORS and keeps cookies first-party.
4. **OpenAPI:** the backend exports `docs/openapi.json` at milestone M8. Frontend types are checked against it.
5. **Compose:** `db`, `backend` (runs `alembic upgrade head` before start) and `frontend`, with healthchecks and `depends_on` conditions. `docker-compose.yml` exists from the start with the `db` service only (PostgreSQL 16, host port 5433). The backend service is added at M8 and the frontend at M13. Until M8 the backend runs locally against that container (see `backend/README.md`).

## Key design decisions (ADR summary)

| # | Decision | Reason |
|---|---|---|
| D1 | Custom PBAC engine with JSON policies, default deny | Required by the assignment; explainable; configurable |
| D2 | Decisions are made only by the PDP in `authorization/`; services ENFORCE them with one `AuthorizationService.require(...)` call before mutating; routers and repositories contain no authorization | Centralized decisions with no scattered conditions (assignment rule), and enforcement that cannot be skipped by a route that forgets a dependency. Replaces the earlier route-dependency design. |
| D3 | 404 for non-members, 403 for members who are denied | Prevents leaking project existence |
| D4 | Sync SQLAlchemy 2.0 | Simpler to reason about and test |
| D5 | Hard delete, audit rows without foreign keys | Simpler queries; history survives deletion |
| D6 | HttpOnly cookie JWTs + same-origin proxy + SameSite=Lax + Origin check + double-submit `X-CSRF-Token` | Mitigates XSS token theft and CSRF; the token is only required when auth cookies are present |
| D7 | Refresh token is a JWT (own audience and `token_type`), only its SHA-256 hash is stored, rotated on every use, reuse revokes the whole family | Revocable, safe if the database leaks, and reuse (theft) is detectable |
| D8 | `varchar` + `CHECK` instead of native enums | Easier migrations |
| D9 | Composite FK `(project_id, assignee_id)` to `project_members` | The database guarantees assignees are members |
| D10 | `position` double precision for Kanban ordering | Cheap reordering without renumbering columns |
| D11 | No frontend mock layer | Backend is finished first; avoids duplicate work |
| D12 | Layer-based backend layout (`routers/`, `services/`, `repositories/`, `models/`, `schemas/`) | Chosen by the project owner at M1; one file per feature inside each layer |
| D13 | Health check at `/api/v1/health`, liveness only (no DB access) | All routes are versioned; the check must work even when the database is down |
| D14 | SQLAlchemy pinned to `>=2.0,<2.1` | Matches the approved stack; 2.1 is a newer, unapproved release line |
| D16 | Policies are a JSON file validated at startup; conditions are a fixed registry of Python functions; the file can select but never define behavior | Configurable PBAC with no code execution from configuration |
| D15 | Podman is the local container runtime; the compose file stays compatible with Docker | The developer has Podman installed; the assignment requires Docker and Docker Compose, so the same `docker-compose.yml` and Dockerfiles must work with `docker compose up --build` |
