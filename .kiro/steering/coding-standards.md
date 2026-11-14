# FinTasks: Coding Standards

These standards apply to all code. Follow existing conventions in the repo. Where this file and the code disagree, raise it instead of silently picking one.

## General

- Keep code simple and explainable. The author must be able to justify every part.
- Small functions with one purpose. Prefer clear names over comments. Comments explain WHY, not WHAT.
- No dead code, no commented-out code, no unused dependencies, no speculative features (YAGNI).
- Do not modify unrelated working code.
- No secrets, tokens or passwords in code, tests (beyond obvious fixtures), logs or Git history.

## Python and FastAPI

### Naming and style
- Python 3.12. Format and lint with Ruff. Line length 100.
- `snake_case` for functions, variables and modules. `PascalCase` for classes. `UPPER_SNAKE_CASE` for constants.
- Schemas end with `In`, `Out` or `Update` (`ProjectIn`, `ProjectOut`, `TaskUpdate`). Models are singular (`Project`, `Task`). Services are `XService`, repositories `XRepository`.
- Layout: one file per feature inside each layer: `routers/<feature>.py`, `schemas/<feature>.py`, `services/<feature>_service.py`, `repositories/<feature>_repository.py`, `models/<feature>.py`.

### Type safety
- Full type hints on every function. Run mypy on `app/`. No `Any` without a comment explaining why.
- SQLAlchemy 2.0 typed style (`Mapped[...]`, `mapped_column`, `select()`). No legacy `Query` API.
- Pydantic v2 models for all request and response bodies. Use `Literal` or `StrEnum` for status and priority.

### Layering rules
- Routers: parse input, declare the authorization dependency, call exactly one service method, return the envelope. NO business logic in routers.
- Services: business rules and transactions. No HTTP types, no authorization decisions.
- Repositories: queries only. No business rules, NO authorization decisions, no commits.
- Authorization lives only in `app/authorization/`. Every protected route declares its action through the `authorize(...)` dependency. Never check ownership, membership or roles ad hoc elsewhere.
- Data scoping for list queries (only the user's projects) is done in the repository by a membership filter that the service passes in. It is not a policy decision. It is documented in `docs/authorization-design.md`.

### FastAPI
- Routes under `/api/v1`, plural nouns, correct verbs and status codes (200, 201, 204, 401, 403, 404, 409, 422).
- Every route has `response_model`, a summary, and declared error responses so Swagger is accurate.
- All responses use the envelope in `docs/api-contract.md`. Use the shared response helpers.
- Use dependency injection for the DB session, current user and authorization.
- Never accept `user_id`, `owner_id` or `created_by` from the client. Take them from the verified JWT user.

### Error handling
- Raise domain exceptions from services. Never raise `HTTPException` inside services or repositories.
- Centralized handlers convert exceptions to the error envelope. Unexpected errors return 500 with a generic message and a request ID. Stack traces go to logs only.
- Validation errors return 422 with field-level `details`.

### Logging
- Use the standard `logging` module with structured (JSON) output in non-development environments.
- Every request log carries a request ID. Log authorization denials (user ID, action, policy ID) and mutations at INFO. Log unexpected errors at ERROR with traceback.
- Never log passwords, tokens, cookies, password hashes or full request bodies.

### Database
- Schema changes only through Alembic migrations, one logical change per migration, reversible where practical.
- Constraints belong in the database (NOT NULL, unique, foreign keys, CHECK) as well as in validation.
- Use parameterized SQLAlchemy constructs only. No string-built SQL.
- Avoid N+1 queries. Use `selectinload` or joins where needed.

### Security (backend)
- Argon2 for passwords (argon2-cffi defaults or stronger). Generic login failure messages.
- JWT: verify signature, expiry and token type. Fixed algorithm (HS256), secret from environment.
- Cookies: HttpOnly, SameSite=Lax, Secure outside local development, refresh cookie path `/api/v1/auth`.
- Reject mutating requests whose `Origin` header is present and not in `ALLOWED_ORIGINS`.
- Validate all input with Pydantic. Enforce length limits.

## TypeScript and React

### Naming and style
- TypeScript `strict: true`. No `any` (use `unknown` and narrow). No `@ts-ignore` without a comment.
- `PascalCase` for components and types, `camelCase` for functions and variables, `kebab-case` for file names, `UPPER_SNAKE_CASE` for constants.
- Components are function components with explicit prop types. One exported component per file.
- ESLint and Prettier must pass.

### Structure and modularity
- Organize by feature under `src/features/<name>/` (components, hooks, schemas, api functions). Shared UI under `src/components/`.
- Pages in `src/app/` stay thin: compose feature components.
- All network calls go through `lib/api.ts`. No `fetch` inside components.
- Query keys come from a per-feature key factory.

### API contract
- Types in `src/types/` mirror `docs/api-contract.md`. NEVER invent response structures. If a needed field is missing, propose a contract change first.
- Zod schemas for forms match backend validation rules in the contract.

### State and forms
- Server state in TanStack Query. Local UI state in React state. Avoid global stores unless clearly needed.
- Forms use React Hook Form + Zod, show inline field errors, disable submit while pending, and show server errors.
- Optimistic updates (Kanban) must roll back on failure and show a message.

### Error handling and UX
- Every data view has loading, empty and error states.
- Convert `ApiError` into readable messages. Show toasts for mutation results.
- Use `allowed_actions` from the API to show or hide controls. Never replicate policy logic in the UI.

### Accessibility and responsiveness
- Semantic HTML, labeled inputs, keyboard-reachable controls, visible focus. The drag-and-drop board must have a non-drag alternative (status select).
- Mobile first. Verify layouts at phone, tablet and desktop widths.

### Security (frontend)
- No tokens in JavaScript-accessible storage. Auth uses HttpOnly cookies only.
- Never render untrusted HTML (`dangerouslySetInnerHTML` is forbidden).
- Environment variables exposed to the browser (`NEXT_PUBLIC_*`) must never hold secrets.

## Testing standards

- Never skip tests. Every milestone ships with tests, and they must pass before the milestone is reported complete.
- Backend: pytest. Tests run against a real PostgreSQL (not SQLite) with per-test transaction rollback.
- Test names describe behavior: `test_non_member_gets_404_for_project`.
- Authorization: every policy has at least one allow test, one deny test and one default-deny test (`tests/authorization/`).
- API tests assert status codes, envelope shape and side effects (including audit rows).
- Security-relevant behavior (token expiry, tampering, rotation, revoked membership) has explicit tests.
- Frontend: Vitest + Testing Library for forms, schemas, the API client (refresh and retry) and key components. Playwright covers one smoke path if time allows.
- Tests are deterministic: fixed clocks where time matters, no reliance on test order, no network access.
- A bug fix includes a regression test.

## Git

- Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`, `ci:`, `build:`. Imperative subject under 72 characters.
- One logical change per commit. Never commit secrets, `.env`, build output or `node_modules`.
