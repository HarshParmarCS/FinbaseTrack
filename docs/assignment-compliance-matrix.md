# Assignment compliance matrix

Source of truth: `req_docs/Full_Stack_Engineer_Assignment.pdf` (10 pages, read in full).

**Snapshot: BASELINE, 16 November 2026, before the final audit fixes.** This version is kept
unchanged on purpose. The status after the fixes is in the "Final status" section that the audit
appends at the end.

Status meanings:
- **PASS:** implemented and verified by executed tests or a live run.
- **PARTIAL:** some of it works and some is missing.
- **FAIL:** missing or not working.
- **NOT VERIFIED:** could not be checked in this environment.

Evidence comes from runs on 16 November 2026:
- Backend: `pytest` gave 970 passed and 99% line coverage; `ruff`, `mypy` and `alembic check`
  were clean.
- Frontend: `pnpm test` gave 367 passed; `pnpm test:live` gave 70 passed against the running
  backend.

## A. Technology stack (PDF pages 1, 2, 7)

| # | Requirement | Status | Evidence | Missing | Correction |
|---|---|---|---|---|---|
| A1 | Backend: FastAPI | PASS | `backend/app/main.py` (`create_app`); 970 API tests | | |
| A2 | Client: Next.js | PASS | `frontend/` (Next.js 16 App Router); `pnpm build` | | |
| A3 | Database: PostgreSQL | PASS | `docker-compose.yml` service `db` (postgres:16); tests run on PostgreSQL (`backend/tests/conftest.py`) | | |
| A4 | Docker (mandatory) | **FAIL** | No `Dockerfile` in `backend/` or `frontend/` | Dockerfiles | Add multi-stage Dockerfiles |
| A5 | Docker Compose (mandatory) | **PARTIAL** | `docker-compose.yml` runs only PostgreSQL | backend and frontend services | Add both services, network, health checks |
| A6 | GitHub Actions CI (bonus) | **FAIL** | No `.github/` directory | Workflow | Optional |

## B. Authentication (page 2)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| B1 | JWT-based authentication | PASS | `backend/app/auth/tokens.py` (HS256, issuer, audience, `jti`) |
| B2 | Registration | PASS | `POST /api/v1/auth/register`; `tests/auth/test_register_login.py`; live `tests/live/auth.live.test.ts` |
| B3 | Login | PASS | `POST /api/v1/auth/login`; same tests; generic 401 on wrong password |
| B4 | Logout | PASS | `POST /api/v1/auth/logout` revokes the refresh token and clears cookies; `test_logout_without_csrf_header_is_forbidden_and_does_not_revoke`, live test "logs out through the real endpoint" |
| B5 | Protected APIs | PASS | `get_current_user` dependency; `tests/audit/test_guards.py::test_every_non_public_route_depends_on_get_current_user`, `test_anonymous_request_never_reaches_a_protected_route` |
| B6 | Secure password hashing | PASS | Argon2id (`app/auth/passwords.py`); `test_password_is_hashed_with_argon2id_and_never_stored_in_plaintext` |
| B7 | Token validation | PASS | `test_invalid_signature_is_rejected`, `test_algorithm_substitution_and_unsigned_tokens_are_rejected`, `test_expired_token_is_rejected` |
| B8 | Refresh tokens (bonus) | PASS | Rotation and reuse detection; live tests "refreshes transparently", "replayed refresh token" |

## C. Project management (page 2)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| C1 | Create projects | PASS | `POST /projects`; `test_create_project_returns_the_project_with_its_owner_and_member`; live projects test |
| C2 | View projects | PASS | `GET /projects`, `GET /projects/{id}`; `test_a_member_sees_the_project_with_owner_and_members` |
| C3 | Update projects | PASS | `PATCH /projects/{id}`; `test_owner_updates_the_name_and_leaves_the_rest_alone` |
| C4 | Delete projects | PASS | `DELETE /projects/{id}`; live test "deletes the project after confirmation" |
| C5 | Add members | PASS | `POST /projects/{id}/members`; `test_owner_adds_a_member_by_email` |
| C6 | Remove members | PASS | `DELETE /projects/{id}/members/{user_id}`; `test_owner_removes_a_member` |

## D. Task management (page 3)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| D1 | Create tasks | PASS | `POST /projects/{id}/tasks`; `tests/tasks/test_task_create_and_read.py` |
| D2 | View tasks | PASS | `GET /projects/{id}/tasks`, `GET /tasks/{id}` |
| D3 | Update tasks | PASS | `PATCH /tasks/{id}`, `PATCH /tasks/{id}/status`; `tests/tasks/test_task_update.py` |
| D4 | Delete tasks | PASS | `DELETE /tasks/{id}`; `tests/tasks/test_task_delete.py` |
| D5 | Search tasks | PASS | `q` parameter (title or description); `tests/tasks/test_task_list.py`; live "searches by text" |
| D6 | Filter by status | PASS | repeatable `status`; live "filters by status and priority" |
| D7 | Filter by priority | PASS | repeatable `priority`; same |
| D8 | Paginate task listings | PASS | `page`, `page_size` (max 100), `meta`; live "paginates with the backend's meta" |
| D9 | Attributes: title, description, assignee, priority, status, due date, timestamps | PASS | `backend/app/models/task.py` (also `creator_id`, `position`, `completed_at`) |
| D10 | Statuses Todo / In Progress / Completed | PASS | `TaskStatus` with a `CHECK` constraint |
| D11 | Priorities Low / Medium / High | PASS | `TaskPriority` with a `CHECK` constraint |

## E. PBAC (pages 3 and 4)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| E1 | No RBAC | PASS | No role columns or role checks. Grep for `role` finds only ARIA attributes in the frontend. `.kiro/steering/workflow.md` rule 4 |
| E2 | Centralized PBAC layer, separated from business logic | PASS | `backend/app/authorization/` (engine, registry, conditions, PIP, PEP); `tests/authorization/test_structure.py` |
| E3 | Not scattered through controllers or services | PASS | Services only call `AuthorizationService.require`; `test_guards.py::test_service_method_asks_the_policy_engine_before_touching_data` |
| E4 | Project visibility (members only) | PASS | policy `project-view`; `test_a_non_member_gets_404_not_403`; live outsider tests |
| E5 | Project update (owner only) | PASS | policy `project-update`; `test_a_member_who_is_not_the_owner_cannot_update` |
| E6 | Project delete (owner only) | PASS | policy `project-delete`; live "is denied by the backend (403 with a policy)" |
| E7 | Task creation (members only) | PASS | policy `task-create`; `test_a_non_member_cannot_create_a_task` |
| E8 | Task update (creator or assignee) | PASS | policy `task-update`; `test_the_creator_can_update_their_task`, `test_the_assignee_can_update_a_task_they_did_not_create`, `test_a_member_who_is_neither_creator_nor_assignee_cannot_update` |
| E9 | Task delete (Todo and project owner) | PASS | policy `task-delete`; `test_the_project_owner_cannot_delete_an_in_progress_task`, `test_the_creator_cannot_delete_even_their_own_todo_task` |
| E10 | Task completion (assignee and required fields) | PASS | policy `task-complete`; `test_a_task_without_an_assignee_cannot_be_completed`, `test_a_task_missing_required_information_cannot_be_completed` |
| E11 | Default deny / unknown actions denied | PASS | `test_unknown_actions_are_denied`, `test_an_unknown_action_is_denied_for_a_member` |
| E12 | Configurable policies, JSON (bonus) | PASS | `app/authorization/policies.json`, validated at startup; `tests/audit/test_policy_configurability.py`, `test_the_application_refuses_to_start_with_an_invalid_policy_file` |

## F. Database design (page 5)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| F1 | Relational schema, normalized | PASS | Six tables: users, projects, project_members, tasks, refresh_tokens, activity_logs (`docs/database-design.md`) |
| F2 | Meaningful relationships (foreign keys) | PASS | Including a composite FK `(project_id, assignee_id)` to `project_members`; `tests/models/` |
| F3 | Constraints | PASS | `CHECK`, `UNIQUE`, `NOT NULL`; `test_membership_must_be_unique_per_project_and_user`, `test_email_uniqueness_cannot_be_bypassed_with_different_case` |
| F4 | Scalability considerations | PASS | Indexes, including `pg_trgm` for search; `EXPLAIN` checked on 60k tasks during the backend audit |
| F5 | Migration files | PASS | `backend/alembic/versions/20261115_0206_4138ca71fcc2_initial_schema.py`; `tests/test_alembic.py`; `alembic check` clean |

## G. Frontend (pages 5 and 6)

| # | Requirement | Status | Evidence | Missing |
|---|---|---|---|---|
| G1 | Login | PASS | `src/app/(auth)/login`; `tests/auth/forms.test.tsx`; live auth test | |
| G2 | Registration | PASS | `src/app/(auth)/register`; same | |
| G3 | Dashboard | PASS | `src/features/dashboard/`; `tests/dashboard/dashboard.test.tsx`; live dashboard test | |
| G4 | Project listing | PASS | `/projects`; `tests/projects/projects-view.test.tsx`; live | |
| G5 | Project details | PASS | `/projects/[projectId]`; `tests/projects/project-detail.test.tsx`; live | |
| G6 | Task details | PASS | `/projects/[projectId]/tasks/[taskId]`; `tests/tasks/task-detail.test.tsx`; live | |
| G7 | Statistics: total projects, active projects, total, completed, pending tasks | PASS | `GET /dashboard/stats`; live "returns the statistics the cards display" | |
| G8 | Responsive UI | **NOT VERIFIED** | Responsive classes and a mobile navigation sheet exist; the sheet is tested in jsdom | Not viewed in a real browser at phone widths |
| G9 | Form validation | PASS | Zod and React Hook Form, server 422 mapped to fields; form tests | |
| G10 | Loading indicators | PASS | Skeletons and a global bar; component tests | |
| G11 | Empty states | PASS | `EmptyState` in every list; tests | |
| G12 | Error states | PASS | `InlineError`, error boundaries; tests | |
| G13 | Clear user feedback | PASS | Toasts and inline errors; `tests/experience.test.tsx` | |
| G14 | Status update via dropdown | PASS | `TaskStatusSelect`; live "Ben completes Ana's complete task" | |
| G15 | Drag and drop (bonus) | FAIL | Not built | Kanban board |
| G16 | Talks to the real backend | PASS (direct) / **NOT VERIFIED** (via proxy) | Live tests call `http://localhost:8000` directly. The Next.js `/api` rewrite path has not been exercised end to end | Run through the proxy |

## H. API design (page 6)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| H1 | RESTful endpoints and methods | PASS | 23 operations, `docs/api-contract.md` |
| H2 | Proper status codes | PASS | 200/201/204/401/403/404/409/422 asserted in tests; `test_openapi.py` |
| H3 | Input validation | PASS | Pydantic, strict models (`extra="forbid"`), NUL rejection; `tests/audit/test_hardening.py` |
| H4 | Consistent response structures | PASS | `{data}`, `{data, meta}`, `{error}` envelopes; `test_contract_examples_validate_against_the_response_models` |
| H5 | Error handling | PASS | `app/core/exceptions.py` handlers |
| H6 | Pagination, filtering, searching | PASS | see D5 to D8 |
| H7 | Swagger / OpenAPI | PASS | `/docs`, `docs/openapi.json`; `tests/audit/test_openapi.py` |

## I. Backend engineering (pages 6 and 7)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| I1 | Clean architecture, modular structure | PASS | routers / services / repositories / models / authorization |
| I2 | Separation of concerns | PASS | Routers call one service method, enforced by guard tests |
| I3 | Reusable services | PASS | `app/services/*` |
| I4 | Centralized exception handling | PASS | `app/core/exceptions.py`; `tests/test_exceptions.py` |
| I5 | Logging | PASS | `app/core/logging.py`, request id middleware; `tests/test_logging.py` |
| I6 | Environment-based configuration | PASS | `app/core/config.py` (pydantic-settings); `tests/test_config.py` |
| I7 | Maintainable code | PASS | ruff and mypy (strict) clean |

## J. Testing (page 7)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| J1 | Unit or API tests | PASS | 970 backend (unit and API), 367 frontend |
| J2 | Integration tests (bonus) | PASS | Backend tests on real PostgreSQL; 70 frontend live tests on the real API |

## K. Containerization (page 7)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| K1 | Dockerfile(s) | **FAIL** | none |
| K2 | docker-compose.yml | **PARTIAL** | database only |
| K3 | Runnable with `docker compose up --build` | **FAIL** | backend and frontend not containerized |

## L. CI/CD (bonus, pages 7 and 8)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| L1 | Basic pipeline | FAIL | not implemented |

## M. Documentation (page 8)

| # | Requirement | Status | Evidence | Missing |
|---|---|---|---|---|
| M1 | Overview, architecture, technology choices | PASS | `README.md` | |
| M2 | Setup instructions | PASS | `README.md`, `backend/README.md`, `frontend/README.md` | |
| M3 | Docker instructions | **FAIL** | Only database instructions exist | Full stack |
| M4 | Environment variables | **PARTIAL** | Three `.env.example` files; root one lacks the backend and frontend variables for Compose | |
| M5 | API documentation | PASS | Swagger, `docs/api-contract.md`, Postman collection | |
| M6 | Assumptions and trade-offs | PASS | `README.md`, `docs/requirements.md` | |

## N. Git (pages 8 and 9)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| N1 | Not a single commit | PASS | 8 commits (14 to 16 November) |
| N2 | Clean, meaningful history | **PARTIAL** | Commits are split by feature, but the messages are short ("Added api logic", "Updated frontend components") and do not follow the suggested progression precisely. History is not rewritten |
| N3 | No secrets committed | PASS | Only `.env.example` files are tracked. A history scan found only placeholders and test fixtures |

## O. Submission items (page 9)

| # | Item | Status |
|---|---|---|
| O1 | GitHub repository | NOT VERIFIED (no remote checked) |
| O2 | README | PASS |
| O3 | Postman collection or Swagger | PASS (`docs/postman/fintasks.postman_collection.json`, `docs/openapi.json`) |
| O4 | Docker configuration | **FAIL** |
| O5 | `.env.example` | PARTIAL (see M4) |
| O6 | Database migration files | PASS |

## Baseline summary

Counted over the 93 mandatory rows. Bonus rows (A6, B8, E12, G15, J2, L1) are listed but not
counted. G16 is counted as NOT VERIFIED, because the proxy path was not exercised.

| Status | Rows | Which |
|---|---|---|
| PASS | 80 | |
| PARTIAL | 5 | A5, K2, M4, N2, O5 |
| FAIL | 5 | A4, K1, K3, M3, O4 |
| NOT VERIFIED | 3 | G8, G16, O1 |

Baseline compliance over verified rows: 80 of 90 = **88.9%**.

Every FAIL row is the same gap: the application is not containerized, so the mandatory
`docker compose up --build` does not work.

---

# Final status (after the audit fixes, 16 November 2026)

## Rows that changed

| # | Requirement | Baseline | Final | Evidence |
|---|---|---|---|---|
| A4 / K1 / O4 | Dockerfile(s) | FAIL | **PASS** | `backend/Dockerfile` (multi-stage, `python:3.12-slim`, non-root `app`), `frontend/Dockerfile` (multi-stage, `node:24-alpine`, pnpm from `packageManager`, frozen lockfile, standalone output, non-root `node`). Both built successfully |
| A5 / K2 | docker-compose.yml with all services | PARTIAL | **PASS** | `postgres`, `backend`, `frontend` on network `workdesk`, named volume `fintasks_pgdata`, health checks, `depends_on: service_healthy`. `podman compose config` is valid. All three containers reached *healthy* |
| K3 | Runnable with one command | FAIL | **PASS** (with Podman) | `podman compose up --build -d` started all three containers from nothing, with the migration applied automatically. See K4 for Docker Engine |
| K4 (new) | Verified with Docker Engine itself | | **NOT VERIFIED** | Docker is not installed on the development machine, so Podman 6.1.4 with podman-compose 1.6.0 was used. The compose file uses only standard Compose features |
| G8 | Responsive UI | NOT VERIFIED | **PASS** (Chrome) | `scripts/browser-check.mjs` in headless Chrome: 8 pages (sign-in plus 7 app pages) at 1440px and 390px; no horizontal page scroll on phones; desktop sidebar hidden and phone menu working; screenshots reviewed. Not checked in Safari or Firefox |
| G16 | Frontend talks to the real backend through the proxy | NOT VERIFIED | **PASS** | All 70 live tests passed against the Docker stack through `http://<frontend>/api/v1` (`LIVE_API_URL`). The browser check registered through the real form and created data through the proxy, with cookies and CSRF |
| M3 | Docker instructions | FAIL | **PASS** | `README.md` ("Run everything with one command"), `docs/ASSIGNMENT_SUBMISSION.md` section 9 |
| M4 / O5 | Environment variables, `.env.example` | PARTIAL | **PASS** | Root `.env.example` lists every variable `docker-compose.yml` reads, with placeholders only; table in the README |
| O1 | GitHub repository | NOT VERIFIED | **PASS** | Remote `git@github.com:HarshParmarCS/FinbaseTrack.git`. Local `main` equals `origin/main` as of the last fetch (not re-fetched during the audit) |
| A6 / L1 | CI pipeline (bonus) | FAIL | **NOT VERIFIED** | `.github/workflows/ci.yml` (backend, frontend and Docker build jobs). Each command was run locally and passes. The workflow has not run on GitHub |
| N2 | Meaningful Git history | PARTIAL | **PARTIAL** (unchanged) | 8 feature-sized commits with short messages. History is not rewritten. The audit work is left uncommitted, with suggested messages |
| G15 | Drag and drop (bonus) | FAIL | FAIL (unchanged) | Not built; the dropdown is the supported method |

Every other row keeps its baseline status (PASS). Each was re-verified in this audit:
- **Backend:** 970 tests passed, also from a fresh virtual environment.
- **Frontend:** 367 unit tests passed.
- **End to end:** 70 live tests passed against the containers.
- **Smoke test:** `scripts/smoke_test.py` passed 38 of 38 against the containers. It covers all
  seven PBAC rules with three users, through the frontend origin.

## Issues found and fixed during the audit

| Issue | Effect | Fix | Verified by |
|---|---|---|---|
| No Dockerfiles; compose ran only the database | Mandatory `docker compose up --build` impossible | Two Dockerfiles, `.dockerignore` files, a full compose file, a root `.env.example` | Build, healthy start, the checks above |
| `backend/requirements-dev.txt` contained `pytest-cov==` with no version | `pip install -r requirements-dev.txt` failed on a fresh machine (verified: exit 2) | Pinned `pytest-cov==7.1.0` | Fresh `uv venv`: install succeeded, then 970 tests passed |
| Next.js built-in type check ran out of memory inside the image build (exit 137 in a 2 GB VM) | Frontend image build failed | `SKIP_BUILD_TYPECHECK=true` in the Dockerfile only; `pnpm typecheck` stays the gate, locally and in CI | Image built; `pnpm typecheck` clean; local `pnpm build` still type-checks |
| Migrations had no container-safe runner | Two backends could race on startup | `backend/scripts/migrate.py`: waits for the database, then runs `alembic upgrade head` under a PostgreSQL advisory lock | Two concurrent runs serialized; a fresh volume was migrated once; a restart was a no-op |
| Migration log line lost after Alembic reconfigured logging | Cosmetic | Logger keeps its own level | "Database schema is up to date" appears in the logs |

No authorization or business-logic defects were found. RBAC is absent, and PBAC stays in
`backend/app/authorization/`.

## Final summary

There are 94 mandatory rows: the 93 baseline rows plus the new K4. Bonus rows are not counted.

| Status | Rows | Which |
|---|---|---|
| PASS | 92 | everything not listed below |
| PARTIAL | 1 | N2 (short commit messages; history not rewritten) |
| FAIL | 0 | |
| NOT VERIFIED | 1 | K4 (Docker Engine; Podman used) |

**Compliance over verified rows: 92 of 93 = 98.9%.** It was 88.9% at the baseline.

Bonus items:
- **PASS:** refresh tokens, configurable JSON PBAC, integration tests, audit logging and activity
  timeline.
- **NOT VERIFIED:** CI on GitHub.
- **FAIL:** drag and drop.
