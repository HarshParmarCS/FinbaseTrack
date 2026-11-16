import { describe, expect, it } from "vitest";
import { parsePublicEnv } from "@/config/env";
import { parseServerEnv } from "@/config/server-env";

describe("parsePublicEnv", () => {
  it("defaults the app name", () => {
    expect(parsePublicEnv({}).NEXT_PUBLIC_APP_NAME).toBe("Finbase Workdesk");
  });

  it("uses the configured app name", () => {
    expect(parsePublicEnv({ NEXT_PUBLIC_APP_NAME: "Acme" }).NEXT_PUBLIC_APP_NAME).toBe("Acme");
  });

  it("defaults the API base URL to the same origin", () => {
    expect(parsePublicEnv({}).NEXT_PUBLIC_API_BASE_URL).toBe("");
  });

  it("accepts a full API base URL", () => {
    const env = parsePublicEnv({ NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000" });

    expect(env.NEXT_PUBLIC_API_BASE_URL).toBe("http://localhost:8000");
  });

  it("rejects an API base URL with a trailing slash or that is not a URL", () => {
    expect(() => parsePublicEnv({ NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000/" })).toThrow();
    expect(() => parsePublicEnv({ NEXT_PUBLIC_API_BASE_URL: "localhost:8000" })).toThrow();
  });

  it("rejects an empty app name", () => {
    expect(() => parsePublicEnv({ NEXT_PUBLIC_APP_NAME: "" })).toThrow();
  });
});

describe("parseServerEnv", () => {
  it("defaults to the local backend", () => {
    expect(parseServerEnv({}).BACKEND_INTERNAL_URL).toBe("http://localhost:8000");
  });

  it("rejects a value that is not a URL", () => {
    expect(() => parseServerEnv({ BACKEND_INTERNAL_URL: "backend" })).toThrow();
  });

  it("rejects a trailing slash, which would produce //api in rewrites", () => {
    expect(() => parseServerEnv({ BACKEND_INTERNAL_URL: "http://localhost:8000/" })).toThrow();
  });
});
