# Finbase Workdesk frontend

Next.js (App Router) interface for the Finbase Workdesk API (the backend still calls itself FinTasks). Current state: **application shell and API
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
| `NEXT_PUBLIC_APP_NAME`     | browser     | `Finbase Workdesk`      | Product name in the UI                                                 |
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

## Projects

`/projects` (list) and `/projects/[projectId]` (details and members) in `src/features/projects/`.

- **List:** cards with name, description, status, owner, member count, task counts and creation date.
  Search (`q`), status filter and page live in the URL. Create, edit and delete from the cards.
- **Details:** overview, task progress, edit, delete, and the member list with add (by email of a
  registered user) and remove.
- **Permissions (PBAC):** the UI never decides who may do what. Buttons appear only when the backend
  lists the action in `allowed_actions` for that user and project, and the backend still enforces every
  request. If a request is refused with a policy denial (403), the user sees "You do not have
  permission to do this." followed by the backend's reason.
- **URL access:** a project id in the address bar grants nothing. The page always asks the backend; for a
  missing project and for a project the user is not a member of it answers 404, shown as "Project not
  found" (the two cases are deliberately indistinguishable).
- **Destructive actions** (delete project, remove member) always ask for confirmation first. Removing a
  member says that their assigned tasks become unassigned.
- **Refresh:** successful changes invalidate the project, task, dashboard and activity queries.

The live test `tests/live/projects.live.test.tsx` renders these pages against the real backend with
three real users (owner, member, outsider). See `pnpm test:live`.

## Tasks

`/projects/[projectId]/tasks` (table) and `/projects/[projectId]/tasks/[taskId]` (details) in
`src/features/tasks/`. The project page links to them with a **Tasks** button.

- **Table:** title, status (an inline status selector), priority, assignee and due date (overdue in red).
  Search, status and priority (multi-select), assignee (a member or "Unassigned"), due-date range,
  "Overdue only", sort (every sort the backend supports) and pagination, all in the URL.
- **Create and edit dialog:** title, description, priority, due date (date picker) and assignee (the
  project's members only). Validation mirrors the backend (title 1 to 200, description up to 5000, a
  real calendar date). Edits send only the fields that changed; clearing a field sends `null`.
- **Status** is changed only through `PATCH /tasks/{id}/status`, never through the edit dialog. The
  selector offers the moves the backend accepts (to do, in progress, completed, one step at a time).
- **Permissions (PBAC):** the UI never decides. Edit, Delete and the status selector follow the task's
  `allowed_actions` from the backend:
  - "update" (creator or assignee, while a member) enables editing and the status selector;
  - "complete" (update AND the completion policy: assignee, title, description, priority and due date)
    enables "Completed"; until then the option is shown as "not available yet";
  - "delete" (project owner, only while To do) shows Delete.
    Every action is still enforced by the backend. A 403 policy denial is shown as "You do not have
    permission to do this." with the backend's reason, and the view keeps the previous state.
- **URL access:** a task id in the address bar grants nothing; a task outside the user's projects is
  "Task not found", and a task shown under the wrong project id is refused.

The live test `tests/live/tasks.live.test.tsx` covers every rule above against the real backend with
four users (owner, assignee, member, outsider).

## Activity

`src/features/activity/`. One timeline component is used in three places:

- **`/activity`:** `GET /dashboard/activity`, the activity of every project you belong to, by any member.
  Your own entries say "You". (There is no backend feed of only your own actions, and sign-in
  events are never returned; see `docs/frontend-api-contract.md`, G13.)
- **Project page:** `GET /projects/{id}/activity`, that project's timeline.
- **Dashboard:** the ten recent entries that come with the statistics.

Entries are grouped by day (Today, Yesterday, then dates), newest first as the backend orders them,
20 per page with **Load more**, and repeated entries are dropped when the feed moves while paging.
Each entry is a sentence with the actor, the action, the task or project (linked when it still
exists and you can open it) and the time (`<time>` with the full date for screen readers).
Names come only from real responses; unknown ones read "a task", "a member" or "a project" (G15).
The order of events written in the same transaction is not defined by the backend (G14).

## Design system

The look follows the Finbase reference screenshots in `reference/` (violet brand, pink accent,
double-ring cards, pill tabs, split sign-in). Product name: **Finbase Workdesk** (set by
`NEXT_PUBLIC_APP_NAME`; the backend and database keep their `fintasks` identifiers).

**All colors live in one file: `src/app/globals.css`.**

1. **Raw scales** at the top: `--brand-50` to `--brand-950` (Finbase violet is `--brand-700`),
   `--highlight-50` to `--highlight-700` (the pink accent) and `--highlight-ring`, `--ink-*`
   neutrals, and a few chart and state hues. Change these to re-skin the whole app.
2. **Semantic tokens** that point at the scales: `--primary`, `--background`, `--border`,
   `--success` / `--warning` / `--info` / `--danger` (each with `-soft`), task status
   (`--status-todo`, `--status-in-progress`, `--status-completed`, each with `-soft` and `-solid`),
   task priority (`--priority-low|medium|high` with `-soft`), `--chart-1` to `--chart-5`, the
   sidebar, gradients and elevations.
3. **Tailwind utilities** generated from them (`@theme inline`), which is all components use:

| Purpose           | Utilities                                                                                                                                        |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Brand and accent  | `bg-brand-700`, `text-brand-700`, `bg-brand-50`, `text-highlight-600`, `ring-highlight-ring`                                                     |
| Surfaces and text | `bg-background`, `bg-card`, `bg-input-fill`, `text-foreground`, `text-muted-foreground`, `bg-overlay`                                            |
| States            | `text-success`, `bg-success-soft`, `text-warning`, `text-danger`, `bg-danger-soft`, `bg-info-soft`                                               |
| Tasks             | `bg-status-completed-soft`, `text-status-in-progress`, `bg-status-todo-solid`, `bg-priority-high-soft`, `text-priority-medium`                   |
| Charts            | `bg-chart-1` to `bg-chart-5`                                                                                                                     |
| Gradients         | `bg-brand-gradient` (buttons, active nav), `bg-brand-band` (dashboard greeting), `bg-brand-panel` (sign-in panel), `bg-glow-line` (top bar line) |
| Elevation         | `shadow-card`, `shadow-card-hover`, `shadow-dialog`, `shadow-glow`                                                                               |

Rules, enforced by `tests/design-tokens.test.ts` (it scans every file in `src/`):

- No raw Tailwind palette classes (`bg-slate-100`, `text-emerald-600`, `text-white`, ...) and no hex
  colors in components. Add a token in `globals.css` instead.
- No inline styles, with two exceptions: computed `width` / `height` / `transform` values (progress
  bars, chart segments), and `src/app/global-error.tsx`, which Next.js renders without the app
  stylesheet.

Building blocks: `Button` (gradient default with a glow, violet `outline`, uppercase `cta` size),
`Card` (double ring), dialogs (blurred backdrop, icon tile in the header), `IconTile`, `Eyebrow`,
`PillTabs`, `StatCard`, `InputWithIcon`, `PasswordInput` (show/hide toggle), `InitialsTile`,
`BackLink`. The font is Inter.

**Sign-out** lives at the bottom of the sidebar (desktop and phone menu), with the signed-in name
and email. There is no account popup. It calls `POST /auth/logout`; a failure is shown under the
button and the user stays signed in.

## Experience

- **Toasts** (sonner) confirm every successful change. Failures stay next to the control that caused
  them (inside the dialog, under the form), with the backend's reason.
- **Confirmation dialogs** for every destructive action (delete project, remove member, delete task).
- **Forms** all use React Hook Form + Zod with the backend's limits, inline field errors, server 422
  errors placed on their fields, and disabled submit buttons while saving. The dashboard's quick
  "New task" uses the same task form as the project pages.
- **Loading:** a thin progress bar under the top bar while any request runs, plus a skeleton in each
  section. **Empty and error states** with retry in every list and card.
- **Error boundaries:** `app/(app)/error.tsx` (inside the shell), `app/error.tsx` (public pages) and
  `app/global-error.tsx` (root layout). They never show error details.
- **Keyboard and screen readers:** a "Skip to content" link, a focusable `<main>`, labelled controls,
  `aria-pressed` filter chips, a keyboard-operable mobile navigation, and reduced motion respected.
- **Responsive:** the sidebar becomes a slide-in menu below the `lg` breakpoint; tables scroll
  horizontally on narrow screens.

## Check the connection

With the backend running, open `/diagnostics` (public, not in the sidebar). It calls the health endpoint and
`GET /auth/me` and reports status, timing, request id and whether the CSRF cookie exists. A 401 on
`/auth/me` counts as a pass when you are not signed in. It shows no cookie values.

## Structure

```
src/
  app/                  routes; (app)/ is the route group that uses the application shell
  components/
    layout/             app shell, brand mark, sidebar (with the account block and sign-out), mobile navigation, top bar
    providers/          TanStack Query provider
    shared/             page header, empty state, stat card, icon tile, eyebrow, pill tabs, inputs with icons, password input, back link
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
