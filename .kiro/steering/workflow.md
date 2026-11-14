# FinTasks: Development Workflow

We build milestone by milestone, in the order defined in `docs/implementation-roadmap.md`. This file defines how.

## Non-negotiable rules

1. Implement ONE milestone at a time. Do not start the next until the current one is reported complete and approved.
2. NEVER skip tests. Every milestone includes tests and they must pass.
3. NEVER silently change the approved architecture. Propose the change, get approval, then update the docs.
4. NEVER introduce RBAC: no roles, no role columns, no role checks, no permission tables tied to roles.
5. NEVER bypass PBAC. Every protected action goes through the authorization module.
6. NEVER put business logic inside routers.
7. NEVER put authorization decisions inside repositories (or services).
8. NEVER hardcode secrets. Configuration comes from environment variables. `.env.example` contains placeholders only.
9. NEVER invent frontend API response structures independently of the approved API contract (`docs/api-contract.md`).
10. NEVER modify unrelated working code.
11. Before major changes, explain the intended changes and wait for approval when the change affects architecture, contracts, schema or policies.
12. After implementation, run the relevant tests and report the results (command, counts, failures).
13. Identify unfinished requirements explicitly in every report. Never imply completion that has not been verified.

## Milestone loop

For each milestone:

1. **Read.** Re-read the milestone in `docs/implementation-roadmap.md` and the relevant docs (`api-contract.md`, `database-design.md`, `authorization-design.md`).
2. **Plan.** Post a short plan: files to create or change, migrations, endpoints, tests. Flag anything that conflicts with the docs. Wait for approval if it is a major change (rule 11).
3. **Tests first where practical.** Write or outline the tests that prove the milestone's acceptance criteria. Policy and API behavior must be test-driven.
4. **Implement** the smallest change that satisfies the milestone. No extras.
5. **Verify.** Run the milestone's tests, then the full suite for the affected project (backend or frontend), plus lint and type checks.
6. **Document.** Update affected docs, tick the roadmap, record new assumptions.
7. **Commit.** One or more Conventional Commits. The working tree must be clean afterward.
8. **Report** using the format below, then wait for approval.

## Report format (end of every milestone)

- **Milestone:** ID and name.
- **Changes:** files and behavior added or changed.
- **Tests:** exact commands run and results (passed, failed, skipped counts). Lint and type check results.
- **Acceptance criteria:** each criterion marked verified or not verified, with how it was verified.
- **Unfinished or deviating items:** every requirement not yet done, and any deviation from the docs.
- **Next milestone** and anything needed from the user.

## Definition of done

A milestone is done only when all of these hold:

- Acceptance criteria in the roadmap are met and verified.
- Tests for the new behavior exist and the full suite passes.
- Ruff, mypy (backend) or ESLint, `tsc` (frontend) pass.
- Docs match the code. Migrations apply cleanly on an empty database and are reversible where practical.
- No secrets, no unrelated changes, clean Git status after commit.

## Handling changes to the design

- If the implementation reveals a flaw or gap in a document, STOP and report it. Propose the doc change, wait for approval, update the document first, then the code.
- Record every new assumption in `docs/requirements.md` (Assumptions section).
- Contract changes follow the order: `docs/api-contract.md`, then backend, then frontend.
- Policy changes follow the order: `docs/authorization-design.md`, then `policies.json`, then tests.
- Schema changes follow the order: `docs/database-design.md`, then migration, then models.

## Git conventions

- Branch: work on `main` unless the user asks for branches. Commit after each verified milestone (more often for large ones).
- Commit messages follow Conventional Commits (see `coding-standards.md`). Examples:
  - `chore: initialize project structure and documentation`
  - `feat(auth): implement registration, login and logout`
  - `feat(authz): add policy decision engine and registry`
  - `feat(projects): add project and member management APIs`
  - `feat(tasks): add task APIs with filters and completion rules`
  - `test: add policy and API tests`
  - `build: add Dockerfiles and compose configuration`
  - `docs: update README and API documentation`
- Never use `--force`, `reset --hard` or `--no-verify` unless the user explicitly asks.
- Stage specific files by name, not `git add -A`.

## Time and priority management

- Overall time budget: about 2 to 3 days including the first day. Tier 1 (mandatory) is completed before any Tier 2 (bonus) work.
- If behind schedule, use the cut order in `.kiro/steering/product.md`. Tell the user before cutting anything.
- Keep the app runnable at the end of every milestone from M8 on.

## Environment and commands (target state, created during M1 and later)

- Backend (from `backend/`, venv active, see `backend/README.md`): `pip install -r requirements-dev.txt` (or `uv pip install -r requirements-dev.txt`), `pytest`, `ruff check .`, `ruff format --check .`, `mypy`, `alembic upgrade head`, `uvicorn app.main:app --reload`. Tests need `TEST_DATABASE_URL`.
- Frontend: `pnpm install`, `pnpm test`, `pnpm lint`, `pnpm typecheck`, `pnpm dev`, `pnpm build`.
- Stack: `docker compose up --build`.
