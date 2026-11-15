import { reply, type FetchMock } from "../api/helpers";

export const me = { id: "u1", email: "ana@example.com", name: "Ana Lopez" };
export const ben = { id: "u2", email: "ben@example.com", name: "Ben Carter" };
export const cy = { id: "u3", email: "cy@example.com", name: "Cy Dunn" };

const OWNER_ACTIONS = ["update", "delete", "manage_members", "create_task"];

export function project(id: string, name: string, extra: object = {}) {
  return {
    id,
    name,
    description: `About ${name}`,
    status: "active",
    owner: me,
    member_count: 2,
    task_counts: { todo: 2, in_progress: 1, completed: 3 },
    allowed_actions: OWNER_ACTIONS,
    created_at: "2026-11-01T12:00:00Z",
    updated_at: "2026-11-10T12:00:00Z",
    ...extra,
  };
}

export const member = (user: typeof me, isOwner = false) => ({
  user,
  is_owner: isOwner,
  joined_at: "2026-11-02T12:00:00Z",
});

export function detail(id: string, name: string, extra: object = {}) {
  return {
    ...project(id, name),
    members: [member(me, true), member(ben)],
    ...extra,
  };
}

export const paged = <T>(
  data: T[],
  meta: Partial<{ page: number; total: number; total_pages: number }> = {},
) => ({
  data,
  meta: { page: 1, page_size: 12, total: data.length, total_pages: 1, ...meta },
});

export const failure = (status: number, code: string, message: string, policyId?: string) =>
  reply(status, {
    error: {
      code,
      message,
      details: policyId ? [{ field: null, message, policy_id: policyId }] : [],
      request_id: "req-1",
    },
  });

type Handler = (url: URL, init: RequestInit | undefined) => Response;

/** Routes requests by "METHOD /path". Unknown requests fail the test loudly. */
export function route(fetchMock: FetchMock, handlers: Record<string, Handler>) {
  fetchMock.mockImplementation(async (input, init) => {
    const url = new URL(String(input), "http://localhost");
    const key = `${init?.method ?? "GET"} ${url.pathname}`;
    if (key === "GET /api/v1/auth/me") return reply(200, { data: me });
    const handler = handlers[key];
    // The project page also shows the project's timeline. Tests that are not about activity get
    // an empty, correctly shaped page instead of having to declare it every time.
    if (!handler && /^GET \/api\/v1\/projects\/[^/]+\/activity$/.test(key)) {
      return reply(200, { data: [], meta: { page: 1, page_size: 20, total: 0, total_pages: 0 } });
    }
    if (!handler) throw new Error(`unexpected request ${key}`);
    return handler(url, init);
  });
}

export const calls = (fetchMock: FetchMock, method: string, pathPart: string) =>
  fetchMock.mock.calls.filter(
    ([url, init]) => (init?.method ?? "GET") === method && String(url).includes(pathPart),
  );

export const csrfOf = (init: RequestInit | undefined) =>
  new Headers(init?.headers).get("x-csrf-token");
