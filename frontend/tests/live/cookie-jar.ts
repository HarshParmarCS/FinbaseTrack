/**
 * A minimal browser stand-in for the live tests: stores Set-Cookie headers, sends matching
 * cookies back, adds the Origin header a browser would, and mirrors the readable csrf_token
 * cookie into document.cookie (the only cookie page JavaScript may see).
 */

/** The real network fetch, captured before any test replaces the global one. */
export const realFetch: typeof fetch = globalThis.fetch.bind(globalThis);

export type StoredCookie = { name: string; value: string; path: string; raw: string };

export class CookieJar {
  private cookies = new Map<string, StoredCookie>();
  readonly requests: string[] = [];
  lastSetCookies: string[] = [];

  constructor(private readonly origin: string) {}

  get(name: string): string | undefined {
    return this.cookies.get(name)?.value;
  }

  names(): string[] {
    return [...this.cookies.keys()].sort();
  }

  delete(name: string): void {
    this.cookies.delete(name);
    this.syncDocument();
  }

  set(name: string, value: string, path = "/"): void {
    this.cookies.set(name, { name, value, path, raw: "" });
    this.syncDocument();
  }

  /** How many requests went to a path, for example "POST /api/v1/auth/refresh". */
  count(label: string): number {
    return this.requests.filter((request) => request === label).length;
  }

  readonly fetch: typeof fetch = async (input, init) => {
    const url = new URL(String(input));
    const headers = new Headers(init?.headers);
    headers.set("Origin", this.origin);
    const cookie = [...this.cookies.values()]
      .filter((c) => url.pathname.startsWith(c.path))
      .map((c) => `${c.name}=${c.value}`)
      .join("; ");
    if (cookie) headers.set("Cookie", cookie);
    this.requests.push(`${init?.method ?? "GET"} ${url.pathname}`);

    const response = await realFetch(url, { ...init, headers, credentials: "omit" });
    this.store(response);
    return response;
  };

  private store(response: Response): void {
    this.lastSetCookies = response.headers.getSetCookie();
    for (const raw of this.lastSetCookies) {
      const [pair, ...attributes] = raw.split(";").map((part) => part.trim());
      const separator = pair.indexOf("=");
      const name = pair.slice(0, separator);
      const value = pair.slice(separator + 1);
      const attribute = (key: string) =>
        attributes.find((a) => a.toLowerCase().startsWith(`${key}=`))?.slice(key.length + 1);
      const path = attribute("path") ?? "/";
      if (value === "" || attribute("max-age") === "0") this.cookies.delete(name);
      else this.cookies.set(name, { name, value, path, raw });
    }
    this.syncDocument();
  }

  private syncDocument(): void {
    const csrf = this.cookies.get("csrf_token");
    document.cookie = csrf ? `csrf_token=${csrf.value}; path=/` : "csrf_token=; max-age=0; path=/";
  }
}
