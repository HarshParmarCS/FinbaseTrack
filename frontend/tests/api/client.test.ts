import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  api,
  buildQueryString,
  buildUrl,
  request,
  setSessionExpiredHandler,
} from "@/lib/api/client";
import { ApiError, ERROR_CODES } from "@/lib/api/errors";
import {
  callInit,
  callUrl,
  clearCookie,
  errorBody,
  headersOf,
  reply,
  replyText,
  setCookie,
  stubFetch,
  type FetchMock,
} from "./helpers";

const env = vi.hoisted(() => ({
  publicEnv: { NEXT_PUBLIC_API_BASE_URL: "", NEXT_PUBLIC_APP_NAME: "Finbase Workdesk" },
}));
vi.mock("@/config/env", () => env);

let fetchMock: FetchMock;

beforeEach(() => {
  env.publicEnv.NEXT_PUBLIC_API_BASE_URL = "";
  fetchMock = stubFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
  clearCookie("csrf_token");
});

async function failure(promise: Promise<unknown>): Promise<ApiError> {
  const error = await promise.then(
    () => null,
    (caught: unknown) => caught,
  );
  expect(error).toBeInstanceOf(ApiError);
  return error as ApiError;
}

describe("URL building", () => {
  it("prefixes /api/v1 and uses the same origin by default", () => {
    expect(buildUrl("/projects")).toBe("/api/v1/projects");
  });

  it("uses NEXT_PUBLIC_API_BASE_URL when it is set", () => {
    env.publicEnv.NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000";

    expect(buildUrl("/projects")).toBe("http://localhost:8000/api/v1/projects");
  });

  it("repeats keys for arrays and skips null and undefined", () => {
    const query = buildQueryString({
      status: ["todo", "in_progress"],
      q: "login page",
      overdue: false,
      page: 2,
      assignee_id: undefined,
      due_after: null,
    });

    expect(query).toBe("?status=todo&status=in_progress&q=login+page&overdue=false&page=2");
  });

  it("returns an empty string when there is nothing to send", () => {
    expect(buildQueryString({})).toBe("");
    expect(buildQueryString({ q: undefined })).toBe("");
  });
});

describe("request headers and credentials", () => {
  it("sends cookies, asks for JSON and sends no Content-Type on GET", async () => {
    fetchMock.mockResolvedValue(reply(200, { data: { status: "ok" } }));

    await api.get("/health");

    expect(callInit(fetchMock).credentials).toBe("include");
    expect(callInit(fetchMock).method).toBe("GET");
    expect(headersOf(fetchMock).get("accept")).toBe("application/json");
    expect(headersOf(fetchMock).has("content-type")).toBe(false);
  });

  it("serializes the body as JSON", async () => {
    fetchMock.mockResolvedValue(reply(201, { data: {} }));

    await api.post("/projects", { name: "Website" });

    expect(headersOf(fetchMock).get("content-type")).toBe("application/json");
    expect(callInit(fetchMock).body).toBe('{"name":"Website"}');
  });

  it("copies the csrf_token cookie into X-CSRF-Token on unsafe methods", async () => {
    setCookie("csrf_token", "abc-123");
    fetchMock.mockImplementation(async () => reply(200, { data: {} }));

    await api.patch("/tasks/1", { title: "x" });
    await api.delete("/tasks/1");

    expect(headersOf(fetchMock, 0).get("x-csrf-token")).toBe("abc-123");
    expect(headersOf(fetchMock, 1).get("x-csrf-token")).toBe("abc-123");
  });

  it("does not send the CSRF header on GET", async () => {
    setCookie("csrf_token", "abc-123");
    fetchMock.mockResolvedValue(reply(200, { data: {} }));

    await api.get("/projects");

    expect(headersOf(fetchMock).has("x-csrf-token")).toBe(false);
  });

  it("never sends an Authorization header (cookies are the only credential)", async () => {
    fetchMock.mockResolvedValue(reply(200, { data: {} }));

    await api.get("/auth/me");

    expect(headersOf(fetchMock).has("authorization")).toBe(false);
  });

  it("puts query parameters in the URL", async () => {
    fetchMock.mockResolvedValue(reply(200, { data: [], meta: {} }));

    await api.get("/projects/p1/tasks", { query: { status: ["todo"], page: 1 } });

    expect(callUrl(fetchMock)).toBe("/api/v1/projects/p1/tasks?status=todo&page=1");
  });
});

describe("response handling", () => {
  it("returns the envelope as the backend sent it", async () => {
    const body = {
      data: [{ id: "1" }],
      meta: { page: 1, page_size: 20, total: 1, total_pages: 1 },
    };
    fetchMock.mockResolvedValue(reply(200, body));

    await expect(api.get("/projects")).resolves.toEqual(body);
  });

  it("returns undefined for 204 responses", async () => {
    fetchMock.mockResolvedValue(reply(204));

    await expect(api.delete("/tasks/1")).resolves.toBeUndefined();
  });

  it("returns text when asked for it", async () => {
    fetchMock.mockResolvedValue(replyText(200, "pong", "text/plain"));

    await expect(request("/ping", { responseType: "text" })).resolves.toBe("pong");
  });

  it("rejects a successful non-JSON response", async () => {
    fetchMock.mockResolvedValue(replyText(200, "<html></html>"));

    const error = await failure(api.get("/projects"));

    expect(error.code).toBe(ERROR_CODES.INVALID_RESPONSE);
  });

  it("rejects a successful response with invalid JSON", async () => {
    fetchMock.mockResolvedValue(
      new Response("{not json", { status: 200, headers: { "content-type": "application/json" } }),
    );

    const error = await failure(api.get("/projects"));

    expect(error.code).toBe(ERROR_CODES.INVALID_RESPONSE);
  });
});

describe("error handling", () => {
  it("turns the backend error envelope into an ApiError", async () => {
    fetchMock.mockResolvedValue(
      reply(404, errorBody("NOT_FOUND", "Project not found.", { request_id: "req-9" })),
    );

    const error = await failure(api.get("/projects/x"));

    expect(error).toMatchObject({
      status: 404,
      code: "NOT_FOUND",
      message: "Project not found.",
      requestId: "req-9",
    });
  });

  it("keeps field-level details of a 422", async () => {
    fetchMock.mockResolvedValue(
      reply(
        422,
        errorBody("VALIDATION_ERROR", "Request validation failed.", {
          details: [{ field: "name", message: "Too short", policy_id: null }],
        }),
      ),
    );

    const error = await failure(api.post("/projects", {}));

    expect(error.status).toBe(422);
    expect(error.details).toEqual([{ field: "name", message: "Too short", policy_id: null }]);
  });

  it("keeps the policy id of a 403", async () => {
    fetchMock.mockResolvedValue(
      reply(
        403,
        errorBody("FORBIDDEN", "Only the owner can delete.", {
          details: [
            { field: null, message: "Only the owner can delete.", policy_id: "project-delete" },
          ],
        }),
      ),
    );

    const error = await failure(api.delete("/projects/1"));

    expect(error.details[0].policy_id).toBe("project-delete");
  });

  it.each([
    [400, "HTTP_ERROR"],
    [401, "UNAUTHENTICATED"],
    [403, "FORBIDDEN"],
    [404, "NOT_FOUND"],
    [422, "VALIDATION_ERROR"],
    [429, "HTTP_ERROR"],
    [500, "INTERNAL_ERROR"],
    [502, "HTTP_ERROR"],
  ])("handles a non-JSON %i from a proxy without crashing", async (status, code) => {
    fetchMock.mockResolvedValue(replyText(status, "<html>Bad gateway</html>"));

    const error = await failure(request("/projects", { skipRefresh: true }));

    expect(error.status).toBe(status);
    expect(error.code).toBe(code);
    expect(error.message).not.toContain("<html>");
    expect(error.message.length).toBeGreaterThan(0);
  });

  it("reads Retry-After on a 429", async () => {
    fetchMock.mockResolvedValue(
      reply(429, errorBody("RATE_LIMITED", "Slow down."), { "retry-after": "30" }),
    );

    const error = await failure(api.get("/projects"));

    expect(error.status).toBe(429);
    expect(error.retryAfterSeconds).toBe(30);
  });

  it("falls back to the X-Request-ID header when the body has none", async () => {
    fetchMock.mockResolvedValue(replyText(500, "boom"));
    fetchMock.mockResolvedValueOnce(
      new Response("boom", { status: 500, headers: { "x-request-id": "hdr-1" } }),
    );

    const error = await failure(api.get("/projects"));

    expect(error.requestId).toBe("hdr-1");
  });

  it("reports a network failure with status 0", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    const error = await failure(api.get("/projects"));

    expect(error).toMatchObject({ status: 0, code: ERROR_CODES.NETWORK_ERROR });
  });

  it("rethrows the abort when the caller cancels", async () => {
    const controller = new AbortController();
    fetchMock.mockImplementation(async () => {
      controller.abort();
      throw new DOMException("Aborted", "AbortError");
    });

    await expect(api.get("/projects", { signal: controller.signal })).rejects.toMatchObject({
      name: "AbortError",
    });
  });
});

describe("401 refresh and retry", () => {
  const refreshUrl = "/api/v1/auth/refresh";

  function route(handlers: Record<string, () => Response>) {
    fetchMock.mockImplementation(async (input) => {
      const handler = handlers[String(input)];
      if (!handler) throw new Error(`unexpected request ${String(input)}`);
      return handler();
    });
  }

  const calls = (url: string) => fetchMock.mock.calls.filter(([u]) => String(u) === url).length;

  it("refreshes once and repeats the request once", async () => {
    let attempts = 0;
    route({
      "/api/v1/projects": () =>
        ++attempts === 1
          ? reply(401, errorBody("UNAUTHENTICATED", "expired"))
          : reply(200, { data: [] }),
      [refreshUrl]: () => reply(200, { data: { id: "u1" } }),
    });

    await expect(api.get("/projects")).resolves.toEqual({ data: [] });

    expect(calls("/api/v1/projects")).toBe(2);
    expect(calls(refreshUrl)).toBe(1);
  });

  it("throws the original 401 when the refresh fails, without looping", async () => {
    route({
      "/api/v1/projects": () => reply(401, errorBody("UNAUTHENTICATED", "expired")),
      [refreshUrl]: () => reply(401, errorBody("UNAUTHENTICATED", "refresh expired")),
    });

    const error = await failure(api.get("/projects"));

    expect(error.status).toBe(401);
    expect(error.message).toBe("expired");
    expect(calls("/api/v1/projects")).toBe(1);
    expect(calls(refreshUrl)).toBe(1);
  });

  it("does not loop when the retried request is still 401", async () => {
    route({
      "/api/v1/projects": () => reply(401, errorBody("UNAUTHENTICATED", "still no")),
      [refreshUrl]: () => reply(200, { data: { id: "u1" } }),
    });

    const error = await failure(api.get("/projects"));

    expect(error.status).toBe(401);
    expect(calls("/api/v1/projects")).toBe(2);
    expect(calls(refreshUrl)).toBe(1);
  });

  it("shares one refresh between concurrent 401s", async () => {
    const attempts = new Map<string, number>();
    const first401 = (path: string) => () => {
      attempts.set(path, (attempts.get(path) ?? 0) + 1);
      return attempts.get(path) === 1
        ? reply(401, errorBody("UNAUTHENTICATED", "expired"))
        : reply(200, { data: path });
    };
    route({
      "/api/v1/projects": first401("projects"),
      "/api/v1/dashboard/stats": first401("stats"),
      [refreshUrl]: () => reply(200, { data: { id: "u1" } }),
    });

    await Promise.all([api.get("/projects"), api.get("/dashboard/stats")]);

    expect(calls(refreshUrl)).toBe(1);
  });

  it.each(["/auth/login", "/auth/register"])(
    "does not refresh after a 401 from %s",
    async (path) => {
      route({
        [`/api/v1${path}`]: () =>
          reply(401, errorBody("UNAUTHENTICATED", "Invalid email or password.")),
      });

      const error = await failure(api.post(path, { email: "a@b.co", password: "x" }));

      expect(error.status).toBe(401);
      expect(calls(refreshUrl)).toBe(0);
    },
  );
});

describe("session expiry notification", () => {
  const handler = vi.fn();

  beforeEach(() => {
    handler.mockReset();
    setSessionExpiredHandler(handler);
  });

  afterEach(() => setSessionExpiredHandler(null));

  function route(refresh: () => Response, resource: () => Response) {
    fetchMock.mockImplementation(async (input) =>
      String(input).endsWith("/auth/refresh") ? refresh() : resource(),
    );
  }

  it("fires once and clears the CSRF hint cookie when the refresh fails", async () => {
    setCookie("csrf_token", "t");
    route(
      () => reply(401, errorBody("UNAUTHENTICATED", "refresh expired")),
      () => reply(401, errorBody("UNAUTHENTICATED", "expired")),
    );

    await failure(api.get("/projects"));

    expect(handler).toHaveBeenCalledTimes(1);
    expect(document.cookie).not.toContain("csrf_token");
  });

  it("does not fire when the refresh succeeds and the retry works", async () => {
    let first = true;
    route(
      () => reply(200, { data: {} }),
      () => {
        const response = first
          ? reply(401, errorBody("UNAUTHENTICATED", "expired"))
          : reply(200, { data: [] });
        first = false;
        return response;
      },
    );

    await api.get("/projects");

    expect(handler).not.toHaveBeenCalled();
  });

  it("fires when the retried request is still unauthorized", async () => {
    route(
      () => reply(200, { data: {} }),
      () => reply(401, errorBody("UNAUTHENTICATED", "no")),
    );

    await failure(api.get("/projects"));

    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("does not fire for a wrong password or other non-401 errors", async () => {
    fetchMock.mockImplementation(async () =>
      reply(401, errorBody("UNAUTHENTICATED", "Invalid email or password.")),
    );
    await failure(api.post("/auth/login", { email: "a@b.co", password: "x" }));
    fetchMock.mockImplementation(async () => reply(403, errorBody("FORBIDDEN", "no")));
    await failure(api.get("/projects"));

    expect(handler).not.toHaveBeenCalled();
  });
});
