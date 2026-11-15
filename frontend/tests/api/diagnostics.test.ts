import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { runDiagnostics } from "@/features/diagnostics/run";
import { clearCookie, errorBody, reply, setCookie, stubFetch, type FetchMock } from "./helpers";

let fetchMock: FetchMock;

beforeEach(() => {
  fetchMock = stubFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
  clearCookie("csrf_token");
});

function backend(handlers: { health: () => Response; me: () => Response }) {
  fetchMock.mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/health")) return handlers.health();
    if (url.endsWith("/auth/me")) return handlers.me();
    throw new Error(`unexpected ${url}`);
  });
}

const byId = async () => {
  const report = await runDiagnostics();
  return { report, byId: Object.fromEntries(report.results.map((r) => [r.id, r])) };
};

describe("runDiagnostics", () => {
  it("passes when the backend is healthy and nobody is signed in", async () => {
    backend({
      health: () => reply(200, { data: { status: "ok" } }),
      me: () => reply(401, errorBody("UNAUTHENTICATED", "Authentication is missing.")),
    });

    const { report, byId: r } = await byId();

    expect(report.mode).toBe("same-origin");
    expect(r.health).toMatchObject({ status: "pass", httpStatus: 200 });
    expect(r.session).toMatchObject({ status: "pass", httpStatus: 401, requestId: "req-1" });
    expect(r.csrf.status).toBe("warn");
  });

  it("does not try to refresh the session while diagnosing", async () => {
    backend({
      health: () => reply(200, { data: { status: "ok" } }),
      me: () => reply(401, errorBody("UNAUTHENTICATED", "x")),
    });

    await runDiagnostics();

    expect(fetchMock.mock.calls.map(([u]) => String(u))).not.toContain("/api/v1/auth/refresh");
  });

  it("reports the signed-in user and the CSRF cookie without exposing its value", async () => {
    setCookie("csrf_token", "super-secret-value");
    backend({
      health: () => reply(200, { data: { status: "ok" } }),
      me: () => reply(200, { data: { id: "u1", email: "ana@example.com", name: "Ana" } }),
    });

    const { byId: r } = await byId();

    expect(r.session.detail).toContain("ana@example.com");
    expect(r.csrf.status).toBe("pass");
    expect(JSON.stringify(r)).not.toContain("super-secret-value");
  });

  it("fails with a hint when the backend cannot be reached", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    const { byId: r } = await byId();

    expect(r.health.status).toBe("fail");
    expect(r.health.detail).toContain("CORS");
    expect(r.session.status).toBe("fail");
  });

  it("fails when health returns a server error", async () => {
    backend({
      health: () => reply(500, errorBody("INTERNAL_ERROR", "Unexpected error.")),
      me: () => reply(500, errorBody("INTERNAL_ERROR", "Unexpected error.")),
    });

    const { byId: r } = await byId();

    expect(r.health).toMatchObject({ status: "fail", httpStatus: 500 });
  });
});
