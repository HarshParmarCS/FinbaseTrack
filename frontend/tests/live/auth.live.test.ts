/**
 * End-to-end authentication check against the REAL running backend (no mocks).
 * Run with the backend up:  pnpm test:live
 * It registers one throwaway user (authlive-<timestamp>@example.com) in the backend's database.
 */
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { CookieJar, realFetch } from "./cookie-jar";

const API = process.env.LIVE_API_URL ?? "http://localhost:8000";
const ORIGIN = process.env.LIVE_ORIGIN ?? "http://localhost:3000";

vi.mock("@/config/env", () => ({
  publicEnv: {
    NEXT_PUBLIC_API_BASE_URL: process.env.LIVE_API_URL ?? "http://localhost:8000",
    NEXT_PUBLIC_APP_NAME: "live",
  },
}));

import { login, logout, register } from "@/features/auth/api";
import { fetchSession } from "@/features/auth/session";
import { api, setSessionExpiredHandler } from "@/lib/api/client";
import { getFieldErrors, isApiError } from "@/lib/api/errors";
import type { PagedEnvelope, ProjectOut } from "@/types/api";

const email = `authlive-${Date.now()}@example.com`;
const password = "live-test-password-1";
const jar = new CookieJar(ORIGIN);
const expired = vi.fn();

async function failure(promise: Promise<unknown>) {
  const error = await promise.then(
    () => null,
    (caught: unknown) => caught,
  );
  if (!isApiError(error)) throw new Error(`expected an ApiError, got ${String(error)}`);
  return error;
}

beforeAll(() => {
  vi.stubGlobal("fetch", jar.fetch);
  setSessionExpiredHandler(expired);
});

afterAll(() => {
  setSessionExpiredHandler(null);
  vi.unstubAllGlobals();
});

describe("authentication against the real backend", () => {
  it("is reachable and a visitor has no session", async () => {
    const health = await realFetch(`${API}/api/v1/health`);
    expect(health.status).toBe(200);
    expect(await fetchSession()).toBeNull();
    expect(jar.requests.filter((r) => r.includes("/auth/me"))).toHaveLength(0);
  });

  it("rejects an invalid registration with field-level errors", async () => {
    const error = await failure(register({ name: "", email: "not-an-email", password: "short" }));

    expect(error.status).toBe(422);
    expect(Object.keys(getFieldErrors(error)).sort()).toEqual(["email", "name", "password"]);
  });

  it("registers a user and receives the three session cookies with the documented flags", async () => {
    const user = await register({ name: "Auth Live", email, password });

    expect(user).toMatchObject({ email, name: "Auth Live" });
    expect(jar.names()).toEqual(["access_token", "csrf_token", "refresh_token"]);
    const flags = (name: string) => jar.lastSetCookies.find((c) => c.startsWith(`${name}=`)) ?? "";
    expect(flags("access_token")).toMatch(/HttpOnly/i);
    expect(flags("refresh_token")).toMatch(/HttpOnly/i);
    expect(flags("refresh_token")).toMatch(/Path=\/api\/v1\/auth/i);
    expect(flags("csrf_token")).not.toMatch(/HttpOnly/i);
    expect(document.cookie).toContain("csrf_token="); // the only cookie page JavaScript sees
    expect(document.cookie).not.toContain("access_token");
    expect(document.cookie).not.toContain("refresh_token");
  });

  it("refuses to register the same email twice", async () => {
    const error = await failure(register({ name: "Again", email, password }));

    expect(error.status).toBe(409);
    expect(error.code).toBe("CONFLICT");
  });

  it("keeps the session after a page refresh (a fresh load asks the backend)", async () => {
    // A reload loses all JavaScript state but keeps the cookies.
    const user = await fetchSession();

    expect(user?.email).toBe(email);
  });

  it("serves a protected endpoint to the signed-in user", async () => {
    const body = await api.get<PagedEnvelope<ProjectOut>>("/projects");

    expect(Array.isArray(body.data)).toBe(true);
    expect(body.meta).toMatchObject({ page: 1, page_size: 20 });
  });

  it("rejects a state-changing request without the CSRF header or from a foreign origin", async () => {
    const cookie = `access_token=${jar.get("access_token")}; csrf_token=${jar.get("csrf_token")}`;
    const post = (extra: Record<string, string>) =>
      realFetch(`${API}/api/v1/projects`, {
        method: "POST",
        headers: { "content-type": "application/json", cookie, origin: ORIGIN, ...extra },
        body: JSON.stringify({ name: "must never be created" }),
      });

    const noCsrf = await post({});
    const foreign = await post({
      "x-csrf-token": jar.get("csrf_token") ?? "",
      origin: "http://evil.example",
    });

    expect(noCsrf.status).toBe(403);
    expect((await noCsrf.json()).error.message).toContain("CSRF");
    expect(foreign.status).toBe(403);
    expect((await foreign.json()).error.message).toContain("origin");
  });

  it("answers a wrong password with the generic 401 and does not start a refresh", async () => {
    const before = jar.count("POST /api/v1/auth/refresh");

    const error = await failure(login({ email, password: "wrong-password" }));

    expect(error.status).toBe(401);
    expect(error.message).toBe("Invalid email or password.");
    expect(jar.count("POST /api/v1/auth/refresh")).toBe(before);
  });

  it("logs out through the real endpoint and the session is gone", async () => {
    await logout();

    expect(jar.names()).toEqual([]);
    expect(document.cookie).not.toContain("csrf_token");
    expect(await fetchSession()).toBeNull();
    expect((await failure(api.get("/projects"))).status).toBe(401);
    expired.mockClear();
  });

  it("logs in again", async () => {
    const user = await login({ email, password });

    expect(user.email).toBe(email);
    expect((await fetchSession())?.email).toBe(email);
    expect(expired).not.toHaveBeenCalled();
  });

  it("refreshes transparently when the 15-minute access cookie has expired", async () => {
    const oldRefresh = jar.get("refresh_token");
    jar.delete("access_token"); // what the browser does when Max-Age runs out
    const refreshesBefore = jar.count("POST /api/v1/auth/refresh");

    const body = await api.get<PagedEnvelope<ProjectOut>>("/projects");

    expect(Array.isArray(body.data)).toBe(true);
    expect(jar.count("POST /api/v1/auth/refresh")).toBe(refreshesBefore + 1);
    expect(jar.get("refresh_token")).not.toBe(oldRefresh); // rotated
    expect(jar.get("access_token")).toBeDefined();
    expect(expired).not.toHaveBeenCalled();
  });

  it("shares ONE refresh between concurrent requests", async () => {
    jar.delete("access_token");
    const refreshesBefore = jar.count("POST /api/v1/auth/refresh");

    const results = await Promise.all([
      api.get<PagedEnvelope<ProjectOut>>("/projects"),
      api.get<PagedEnvelope<ProjectOut>>("/dashboard/stats"),
      api.get("/auth/me"),
    ]);

    expect(results).toHaveLength(3);
    expect(jar.count("POST /api/v1/auth/refresh")).toBe(refreshesBefore + 1);
    expect(expired).not.toHaveBeenCalled();
  });

  it("ends the session cleanly when a rotated refresh token is replayed (theft signal)", async () => {
    const stolen = jar.get("refresh_token") ?? "";
    jar.delete("access_token");
    await api.get("/projects"); // legitimate rotation: the token above is now spent
    expect(jar.get("refresh_token")).not.toBe(stolen);

    jar.set("refresh_token", stolen, "/api/v1/auth"); // replay the spent token
    jar.delete("access_token");
    const refreshesBefore = jar.count("POST /api/v1/auth/refresh");
    const error = await failure(api.get("/projects"));

    expect(error.status).toBe(401);
    expect(jar.count("POST /api/v1/auth/refresh")).toBe(refreshesBefore + 1); // no loop
    expect(expired).toHaveBeenCalledTimes(1);
    expect(document.cookie).not.toContain("csrf_token"); // the hint is cleared
    expect(await fetchSession()).toBeNull();
  });

  it("treats a missing refresh cookie (7 days passed) as an expired session", async () => {
    await login({ email, password });
    expired.mockClear();
    jar.delete("access_token");
    jar.delete("refresh_token");

    const error = await failure(api.get("/projects"));

    expect(error.status).toBe(401);
    expect(expired).toHaveBeenCalledTimes(1);
  });

  it("can sign in again after an expired session and sign out for good", async () => {
    await login({ email, password });
    expect((await fetchSession())?.email).toBe(email);

    await logout();

    expect(await fetchSession()).toBeNull();
  });
});
