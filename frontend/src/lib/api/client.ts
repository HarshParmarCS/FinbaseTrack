import { publicEnv } from "@/config/env";
import { AUTH_FLOW_PATHS, endpoints } from "@/lib/api/endpoints";
import { ApiError, ERROR_CODES, createApiError, isApiError } from "@/lib/api/errors";

const API_PREFIX = "/api/v1";
export const CSRF_COOKIE = "csrf_token";
const CSRF_HEADER = "X-CSRF-Token";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
const DEFAULT_TIMEOUT_MS = 15_000;

export type QueryValue =
  string | number | boolean | null | undefined | readonly (string | number)[];
export type QueryParams = Record<string, QueryValue>;
export type HttpMethod = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

export type RequestOptions = {
  method?: HttpMethod;
  /** Serialized as JSON. */
  body?: unknown;
  query?: QueryParams;
  signal?: AbortSignal;
  timeoutMs?: number;
  /** `json` (default) for the backend's JSON bodies, `text` for plain-text responses. */
  responseType?: "json" | "text";
  /** Internal: set on the retry after a refresh, and on the refresh call itself. */
  skipRefresh?: boolean;
};

/** Repeated keys for arrays (`status=todo&status=in_progress`), nothing for null or undefined. */
export function buildQueryString(query: QueryParams = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined) continue;
    if (Array.isArray(value)) {
      for (const item of value) search.append(key, String(item));
    } else {
      search.append(key, String(value));
    }
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export function buildUrl(path: string, query?: QueryParams): string {
  return `${publicEnv.NEXT_PUBLIC_API_BASE_URL}${API_PREFIX}${path}${buildQueryString(query)}`;
}

/** Read a cookie from the browser. Returns null on the server or when it is absent. */
export function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  for (const part of document.cookie.split("; ")) {
    const separator = part.indexOf("=");
    if (separator > 0 && part.slice(0, separator) === name) {
      return decodeURIComponent(part.slice(separator + 1));
    }
  }
  return null;
}

/**
 * Remove the readable csrf_token cookie. It is the app's "a session may exist" hint, so a dead
 * session must not leave it behind. HttpOnly cookies cannot be touched from JavaScript (and the
 * backend clears them itself on logout).
 */
export function clearCsrfCookie(): void {
  if (typeof document !== "undefined") {
    document.cookie = `${CSRF_COOKIE}=; Max-Age=0; path=/`;
  }
}

type SessionExpiredHandler = () => void;
let sessionExpiredHandler: SessionExpiredHandler | null = null;

/** Register the single listener told when a refresh fails (the session is really over). */
export function setSessionExpiredHandler(handler: SessionExpiredHandler | null): void {
  sessionExpiredHandler = handler;
}

function notifySessionExpired(): void {
  clearCsrfCookie();
  sessionExpiredHandler?.();
}

function buildHeaders(method: string, hasBody: boolean): Headers {
  const headers = new Headers({ Accept: "application/json" });
  if (hasBody) headers.set("Content-Type", "application/json");
  if (!SAFE_METHODS.has(method)) {
    // Double-submit CSRF: the backend compares this header with the csrf_token cookie.
    const token = readCookie(CSRF_COOKIE);
    if (token) headers.set(CSRF_HEADER, token);
  }
  return headers;
}

function invalidResponse(response: Response): ApiError {
  return new ApiError({
    status: response.status,
    code: ERROR_CODES.INVALID_RESPONSE,
    message: "The server sent a response the app could not read.",
    requestId: response.headers.get("x-request-id"),
  });
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function send<T>(path: string, options: RequestOptions): Promise<T> {
  const method = options.method ?? "GET";
  const hasBody = options.body !== undefined;
  const timeout = AbortSignal.timeout(options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout;

  let response: Response;
  try {
    response = await fetch(buildUrl(path, options.query), {
      method,
      headers: buildHeaders(method, hasBody),
      body: hasBody ? JSON.stringify(options.body) : undefined,
      // Cookies carry the session. Required for direct cross-origin calls, harmless same-origin.
      credentials: "include",
      cache: "no-store",
      signal,
    });
  } catch (error) {
    if (options.signal?.aborted) throw error; // the caller cancelled; let it see the abort
    const timedOut = timeout.aborted;
    throw new ApiError({
      status: 0,
      code: timedOut ? ERROR_CODES.TIMEOUT : ERROR_CODES.NETWORK_ERROR,
      message: timedOut
        ? "The server took too long to respond."
        : "Cannot reach the server. Check your connection and that the backend is running.",
    });
  }

  const isJson = (response.headers.get("content-type") ?? "").includes("application/json");

  if (!response.ok) {
    throw createApiError(response, isJson ? await readJson(response) : null);
  }
  if (response.status === 204 || response.status === 205) return undefined as T;
  if (options.responseType === "text") return (await response.text()) as T;
  if (!isJson) throw invalidResponse(response);

  const body = await readJson(response);
  if (body === null) throw invalidResponse(response);
  // The generic parameter is the caller's contract type; the backend schemas are documented in
  // docs/frontend-api-contract.md and checked by the backend's own tests.
  return body as T;
}

let refreshInFlight: Promise<boolean> | null = null;

/** One refresh at a time: concurrent 401s share the same call. Resolves false if it failed. */
function refreshSession(): Promise<boolean> {
  refreshInFlight ??= send(endpoints.auth.refresh, { method: "POST", skipRefresh: true })
    .then(() => true)
    .catch(() => false)
    .finally(() => {
      refreshInFlight = null;
    });
  return refreshInFlight;
}

/**
 * Perform a request against `/api/v1`. On a 401 from a normal endpoint it refreshes the session
 * once and repeats the request once. If the refresh fails the session-expired handler runs and the
 * original 401 is thrown.
 * Returns the parsed body as the backend sent it (envelope included), or undefined for 204.
 */
export async function request<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  try {
    return await send<T>(path, options);
  } catch (error) {
    const canRefresh = !options.skipRefresh && !AUTH_FLOW_PATHS.has(path);
    if (!canRefresh || !isApiError(error) || error.status !== 401) throw error;

    if (!(await refreshSession())) {
      notifySessionExpired();
      throw error;
    }
    try {
      return await send<T>(path, { ...options, skipRefresh: true });
    } catch (retryError) {
      // Refreshed but still rejected: the session is not usable.
      if (isApiError(retryError) && retryError.status === 401) notifySessionExpired();
      throw retryError;
    }
  }
}

type Extras = Omit<RequestOptions, "method" | "body">;

export const api = {
  get: <T>(path: string, options?: Extras) => request<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: Extras) =>
    request<T>(path, { ...options, method: "POST", body }),
  patch: <T>(path: string, body?: unknown, options?: Extras) =>
    request<T>(path, { ...options, method: "PATCH", body }),
  delete: <T = void>(path: string, options?: Extras) =>
    request<T>(path, { ...options, method: "DELETE" }),
};
