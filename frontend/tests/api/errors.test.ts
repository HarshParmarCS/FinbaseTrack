import { describe, expect, it } from "vitest";
import {
  ApiError,
  defaultMessageFor,
  getErrorMessage,
  getFieldErrors,
  isApiError,
  isUnauthorized,
  readErrorBody,
} from "@/lib/api/errors";

const validation = new ApiError({
  status: 422,
  code: "VALIDATION_ERROR",
  message: "Request validation failed.",
  details: [
    { field: "name", message: "Too short" },
    { field: "name", message: "Second message" },
    { field: null, message: "General problem" },
    { field: "due_date", message: "Bad date" },
  ],
});

describe("readErrorBody", () => {
  it("accepts the backend envelope", () => {
    expect(readErrorBody({ error: { code: "X", message: "m", request_id: "r" } })).toMatchObject({
      code: "X",
      message: "m",
      request_id: "r",
      details: [],
    });
  });

  it.each([null, "text", 42, {}, { error: null }, { error: { code: 1, message: "m" } }])(
    "rejects %j",
    (value) => {
      expect(readErrorBody(value)).toBeNull();
    },
  );
});

describe("messages", () => {
  it("has a readable default for every status the app handles", () => {
    for (const status of [400, 401, 403, 404, 422, 429, 500, 503]) {
      expect(defaultMessageFor(status).length).toBeGreaterThan(10);
    }
    expect(defaultMessageFor(418)).toContain("418");
  });

  it("uses the ApiError message and a fallback for anything else", () => {
    expect(getErrorMessage(validation)).toBe("Request validation failed.");
    expect(getErrorMessage(new Error("internal detail"), "Try again")).toBe("Try again");
    expect(getErrorMessage("oops")).toBe("Something went wrong.");
  });
});

describe("getFieldErrors", () => {
  it("returns the first message per named field and ignores general ones", () => {
    expect(getFieldErrors(validation)).toEqual({ name: "Too short", due_date: "Bad date" });
  });

  it("returns an empty object for other errors", () => {
    expect(getFieldErrors(new Error("x"))).toEqual({});
  });
});

describe("type guards", () => {
  it("recognizes ApiError and 401s", () => {
    const unauthorized = new ApiError({ status: 401, code: "UNAUTHENTICATED", message: "m" });

    expect(isApiError(unauthorized)).toBe(true);
    expect(isApiError(new Error("x"))).toBe(false);
    expect(isUnauthorized(unauthorized)).toBe(true);
    expect(isUnauthorized(validation)).toBe(false);
  });
});
