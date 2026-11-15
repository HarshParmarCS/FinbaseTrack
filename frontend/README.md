# FinTasks frontend

Next.js (App Router) interface for the FinTasks API. Current state: **application shell and API
integration foundation and authentication** (login, register, sign out, session state, protected
routes, refresh handling). The data screens are not built yet. No data is mocked. The backend contract this app will follow is
[`docs/frontend-api-contract.md`](../docs/frontend-api-contract.md).

## Stack

Next.js 16 (App Router, TypeScript strict), Tailwind CSS 4, shadcn/ui (Radix, neutral theme),
TanStack Query, React Hook Form, Zod, Lucide icons, Vitest + Testing Library.

## Prerequisites

- Node.js 20 or newer (developed on 24)
- pnpm (`npm install -g pnpm`)
- The backend running on `http://localhost:8000` (see `../backend/README.md`) for the `/api` proxy

## Setup and run

```bash
cd frontend
pnpm install
cp .env.example .env.local     # optional: the defaults already match a local backend
pnpm dev                       # http://localhost:3000
```

**Port 3000 is required.** The backend only accepts browser requests from `http://localhost:3000`
(`ALLOWED_ORIGINS`), including through the proxy. If another program already uses port 3000, the dev command fails instead of
silently choosing another port.

## Scripts

| Command                             | Purpose                                   |
| ----------------------------------- | ----------------------------------------- |
| `pnpm dev`                          | Development server on port 3000           |
| `pnpm build` / `pnpm start`         | Production build and server               |
| `pnpm lint`                         | ESLint                                    |
| `pnpm typecheck`                    | `tsc --noEmit` (strict)                   |
| `pnpm test`                         | Vitest, single run                        |
| `pnpm format` / `pnpm format:check` | Prettier (with the Tailwind class sorter) |

## Configuration

Browser settings are in `src/config/env.ts`, the server-only one in `src/config/server-env.ts`
(both validated with Zod).

| Variable                   | Scope       | Default                 | Meaning                                                                |
| -------------------------- | ----------- | ----------------------- | ---------------------------------------------------------------------- |
| `BACKEND_INTERNAL_URL`     | server only | `http://localhost:8000` | Target of the `/api/*` rewrite in `next.config.ts` (no trailing slash) |
| `NEXT_PUBLIC_APP_NAME`     | browser     | `FinTasks`              | Product name in the UI                                                 |
| `NEXT_PUBLIC_API_BASE_URL` | browser     | empty (same origin)     | Base URL for API calls; see below                                      |

**Same origin (default, recommended):** leave `NEXT_PUBLIC_API_BASE_URL` empty. The browser calls
`/api/v1/...` on the frontend origin and Next.js forwards the request to `BACKEND_INTERNAL_URL`, so
cookies stay first-party and CORS is not involved.

**Direct:** set `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` to call the backend from the browser.
This needs the CORS setup the backend already has for `http://localhost:3000`. Use `localhost` on both
sides (not `127.0.0.1`), because cookies are per host. Restart the dev server after changing it.

## API layer

| File                          | Role                                                                                                                                                                                                                                                                                                        |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/lib/api/client.ts`       | The only code that calls `fetch`. Sends cookies (`credentials: "include"`), adds `X-CSRF-Token` from the `csrf_token` cookie on POST/PATCH/DELETE, handles JSON, 204 and non-JSON bodies, timeouts, and on a 401 refreshes the session once (shared between concurrent calls) and repeats the request once. |
| `src/lib/api/errors.ts`       | `ApiError` (`status`, `code`, `message`, `details`, `requestId`, `retryAfterSeconds`), plus `getErrorMessage` and `getFieldErrors` for forms. Non-envelope errors (HTML from a proxy, plain-text 429) become readable `ApiError`s too.                                                                      |
| `src/lib/api/endpoints.ts`    | Every backend path.                                                                                                                                                                                                                                                                                         |
| `src/lib/api/query-client.ts` | TanStack Query defaults: 30 s stale time, no retry on 4xx, two retries for network and 5xx errors, no mutation retries.                                                                                                                                                                                     |
| `src/types/api.ts`            | Types and enums mirroring `docs/frontend-api-contract.md`.                                                                                                                                                                                                                                                  |
| `src/features/<name>/`        | `api.ts` (typed calls), `keys.ts` (query key factory), `hooks.ts` (queries and mutations) for health, auth, projects (with members), tasks, dashboard and activity. Mutations invalidate the related keys.                                                                                                  |

The client returns the body exactly as the backend sends it (single `{ data }`, paged `{ data, meta }`
or nothing for 204). The feature `api.ts` functions unwrap it per endpoint.

## Authentication

The backend authenticates with HttpOnly cookies (`access_token` 15 min, `refresh_token` 7 days scoped
to `/api/v1/auth`, readable `csrf_token`). The app never reads or stores tokens.

| Piece                             | Role                                                                                                                           |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `features/auth/auth-provider.tsx` | Session state (`loading`, `authenticated`, `unauthenticated`, `error`), `useAuth()`, `signOut()` (calls `POST /auth/logout`)   |
| `features/auth/session.ts`        | `fetchSession()`: asks `GET /auth/me`, but only if the readable `csrf_token` cookie exists (the hint that a session may exist) |
| `features/auth/auth-gate.tsx`     | Protected pages: loading, then content, or redirect to `/login?next=...`; a retryable error if the backend cannot be reached   |
| `features/auth/guest-gate.tsx`    | Login and register pages: a signed-in user moves on to a safe `next` page or the dashboard                                     |
| `src/proxy.ts`                    | Redirects to `/login` when the `csrf_token` cookie is missing. A convenience only                                              |
| `lib/api/client.ts`               | Refresh and retry once on 401, one shared refresh for concurrent requests, tells the provider when the session is over         |

Behavior:

- **Register** signs the user in (the backend sets the cookies), then the app goes to the dashboard.
- **Session persistence:** a page reload keeps the cookies; the app asks `/auth/me` again.
- **Expiry:** an expired access cookie is refreshed silently. If the refresh fails (refresh token
  expired, revoked, or replayed after rotation), the session state is cleared and the user is sent to
  `/login?reason=expired&next=...` with an explanation. There is no retry loop.
- **Sign out** calls the backend, clears state and goes to a clean `/login`. If the call fails the user
  stays signed in and sees an error.
- **Security:** the route protection (`proxy.ts` and `AuthGate`) only decides what to show. The backend
  rejects every unauthenticated or unauthorized API call. `next` is accepted only as a same-site path.

### Live test

With the backend running, `pnpm test:live` runs `tests/live/auth.live.test.ts`: register, reload,
protected call, CSRF and origin rejection, wrong password, logout, login, access-cookie expiry,
concurrent refresh, replayed refresh token and missing refresh cookie, all against the real API using
the same client code and a cookie jar standing in for the browser. It creates one user per run
(`authlive-<timestamp>@example.com`) in the backend's database. Override the target with `LIVE_API_URL`.

## Dashboard

`/dashboard` (`src/features/dashboard/`) uses only real endpoints: `GET /dashboard/stats` (counts and
recent activity), `GET /projects` (overview and status breakdown) and `GET /projects/{id}/tasks`
(assigned and upcoming tasks). Each card loads independently with its own skeleton, empty state and
retry. Creating a project or task from the **New** menu invalidates the project, task, dashboard and
activity queries, so the numbers refresh.

The backend has no cross-project task list, so "My assigned tasks" and "Upcoming due dates" query each
project with open work (at most 10) and say when a list is partial. The status chart appears only when
all projects fit in one page. These limits are listed in `docs/frontend-api-contract.md` (G9 to G12).

## Check the connection

With the backend running, open `/diagnostics` (public, not in the sidebar). It calls the health endpoint and
`GET /auth/me` and reports status, timing, request id and whether the CSRF cookie exists. A 401 on
`/auth/me` counts as a pass when you are not signed in. It shows no cookie values.

## Structure

```
src/
  app/                  routes; (app)/ is the route group that uses the application shell
  components/
    layout/             app shell, sidebar, mobile navigation, top bar, account menu
    providers/          TanStack Query provider
    shared/             page header, empty state, stat card
    ui/                 shadcn/ui primitives (generated; add more with `pnpm dlx shadcn@latest add <name>`)
  config/               env.ts, server-env.ts (environment), navigation.ts (sidebar items)
  features/             health, auth, projects, tasks, dashboard, activity, diagnostics
  lib/api/              client, errors, endpoints, query client
  lib/                  `cn` helper
  types/                API types
tests/                  Vitest tests (tests/api for the API layer)
```

## Notes for the next milestones

- `/my-tasks`, `/activity`, `/settings` and `/diagnostics` are not in the original architecture route list. There is
  no backend endpoint that lists a user's assigned tasks (contract item G2), so My Tasks cannot
  show a list yet.
- State-changing requests must send `X-CSRF-Token` (the value of the `csrf_token` cookie). See the
  contract, section 2.
