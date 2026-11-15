import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchSession } from "@/features/auth/session";
import {
  clearCookie,
  errorBody,
  reply,
  setCookie,
  stubFetch,
  type FetchMock,
} from "../api/helpers";

let fetchMock: FetchMock;

beforeEach(() => {
  fetchMock = stubFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
  clearCookie("csrf_token");
});

describe("fetchSession", () => {
  it("returns null without any request when there is no session hint cookie", async () => {
    await expect(fetchSession()).resolves.toBeNull();

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns the user when the backend confirms the session", async () => {
    setCookie("csrf_token", "t");
    fetchMock.mockImplementation(async () =>
      reply(200, { data: { id: "u1", email: "a@b.co", name: "A" } }),
    );

    await expect(fetchSession()).resolves.toMatchObject({ id: "u1" });
  });

  it("returns null when the session is dead (401 and the refresh fails)", async () => {
    setCookie("csrf_token", "t");
    fetchMock.mockImplementation(async () => reply(401, errorBody("UNAUTHENTICATED", "no")));

    await expect(fetchSession()).resolves.toBeNull();
  });

  it("throws when the backend cannot be asked, so the UI does not pretend to be signed out", async () => {
    setCookie("csrf_token", "t");
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(fetchSession()).rejects.toMatchObject({ status: 0 });
  });
});
