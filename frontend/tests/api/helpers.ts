import { vi } from "vitest";

export type FetchMock = ReturnType<typeof vi.fn<typeof fetch>>;

export function stubFetch(): FetchMock {
  const mock = vi.fn<typeof fetch>();
  vi.stubGlobal("fetch", mock);
  return mock;
}

export function reply(status: number, body?: unknown, headers: Record<string, string> = {}) {
  if (body === undefined) return new Response(null, { status, headers });
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

export function replyText(status: number, text: string, contentType = "text/html") {
  return new Response(text, { status, headers: { "content-type": contentType } });
}

export function errorBody(code: string, message: string, extra: object = {}) {
  return { error: { code, message, details: [], request_id: "req-1", ...extra } };
}

/** The URL, as a string, of the nth call (0-based). */
export function callUrl(mock: FetchMock, index = 0): string {
  return String(mock.mock.calls[index][0]);
}

export function callInit(mock: FetchMock, index = 0): RequestInit {
  return mock.mock.calls[index][1] ?? {};
}

export function headersOf(mock: FetchMock, index = 0): Headers {
  return new Headers(callInit(mock, index).headers);
}

export function setCookie(name: string, value: string) {
  document.cookie = `${name}=${value}; path=/`;
}

export function clearCookie(name: string) {
  document.cookie = `${name}=; max-age=0; path=/`;
}
