import { vi } from "vitest";
import { isApiError } from "@/lib/api/errors";
import type { UserOut } from "@/types/api";
import { CookieJar } from "./cookie-jar";

const origin = process.env.LIVE_ORIGIN ?? "http://localhost:3000";

export type Person = { jar: CookieJar; email: string; name: string; user?: UserOut };

export function person(prefix: string, key: string, name: string, stamp: number): Person {
  return {
    jar: new CookieJar(origin),
    email: `${prefix}-${key}-${stamp}@example.com`,
    name,
  };
}

/** Act as this person: their cookies, their readable csrf cookie. */
export function as(who: Person) {
  vi.stubGlobal("fetch", who.jar.fetch);
  who.jar.activate();
}

/** Run a promise that must fail with an ApiError and return it. */
export async function failure(promise: Promise<unknown>) {
  const error = await promise.then(
    () => null,
    (caught: unknown) => caught,
  );
  if (!isApiError(error)) throw new Error(`expected an ApiError, got ${String(error)}`);
  return error;
}
