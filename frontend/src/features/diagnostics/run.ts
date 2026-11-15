import { publicEnv } from "@/config/env";
import { readCookie, request } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import { ERROR_CODES, isApiError } from "@/lib/api/errors";
import type { Envelope, HealthOut, UserOut } from "@/types/api";

export type CheckStatus = "pass" | "warn" | "fail";

export type CheckResult = {
  id: "health" | "session" | "csrf";
  label: string;
  status: CheckStatus;
  httpStatus: number | null;
  durationMs: number | null;
  detail: string;
  requestId: string | null;
};

export type DiagnosticsReport = {
  mode: "same-origin" | "direct";
  apiBaseUrl: string;
  checkedAt: string;
  results: CheckResult[];
};

type Outcome = Pick<CheckResult, "status" | "detail"> &
  Partial<Pick<CheckResult, "httpStatus" | "requestId">>;

async function timed(
  id: CheckResult["id"],
  label: string,
  check: () => Promise<Outcome>,
): Promise<CheckResult> {
  const started = performance.now();
  const outcome = await check();
  return {
    id,
    label,
    httpStatus: null,
    requestId: null,
    ...outcome,
    durationMs: Math.round(performance.now() - started),
  };
}

function describeFailure(error: unknown): Outcome {
  if (!isApiError(error)) return { status: "fail", detail: "Unexpected error." };
  const hint =
    error.code === ERROR_CODES.NETWORK_ERROR
      ? " The backend may be stopped, or the browser blocked the call (CORS)."
      : "";
  return {
    status: "fail",
    detail: `${error.message}${hint}`,
    httpStatus: error.status || null,
    requestId: error.requestId,
  };
}

async function checkHealth(): Promise<Outcome> {
  try {
    const body = await request<Envelope<HealthOut>>(endpoints.health, { skipRefresh: true });
    return body.data.status === "ok"
      ? { status: "pass", detail: "Backend reports status ok.", httpStatus: 200 }
      : { status: "fail", detail: `Unexpected status "${body.data.status}".`, httpStatus: 200 };
  } catch (error) {
    return describeFailure(error);
  }
}

// A 401 is the healthy answer when nobody is signed in: it proves routing, cookies and the
// error format work end to end.
async function checkSession(): Promise<Outcome> {
  try {
    const body = await request<Envelope<UserOut>>(endpoints.auth.me, { skipRefresh: true });
    return { status: "pass", detail: `Signed in as ${body.data.email}.`, httpStatus: 200 };
  } catch (error) {
    if (isApiError(error) && error.status === 401) {
      return {
        status: "pass",
        detail: "Backend reachable. Not signed in (401), as expected without a session.",
        httpStatus: 401,
        requestId: error.requestId,
      };
    }
    return describeFailure(error);
  }
}

async function checkCsrfCookie(): Promise<Outcome> {
  return readCookie("csrf_token")
    ? { status: "pass", detail: "csrf_token cookie is present (value not shown)." }
    : {
        status: "warn",
        detail: "No csrf_token cookie yet. It is set at sign-in and is needed for changes.",
      };
}

export async function runDiagnostics(): Promise<DiagnosticsReport> {
  const results = [
    await timed("health", "Backend health", checkHealth),
    await timed("session", "Session (GET /auth/me)", checkSession),
    await timed("csrf", "CSRF cookie", checkCsrfCookie),
  ];
  const base = publicEnv.NEXT_PUBLIC_API_BASE_URL;
  return {
    mode: base ? "direct" : "same-origin",
    apiBaseUrl: base || "same origin (/api/v1, forwarded by Next.js)",
    checkedAt: new Date().toISOString(),
    results,
  };
}
