import type { ErrorBody, ErrorDetail } from "@/types/api";

/** Codes the backend sends (app/core/exceptions.py) plus the ones the client creates itself. */
export const ERROR_CODES = {
  UNAUTHENTICATED: "UNAUTHENTICATED",
  FORBIDDEN: "FORBIDDEN",
  NOT_FOUND: "NOT_FOUND",
  CONFLICT: "CONFLICT",
  VALIDATION_ERROR: "VALIDATION_ERROR",
  BUSINESS_RULE_VIOLATION: "BUSINESS_RULE_VIOLATION",
  METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
  INTERNAL_ERROR: "INTERNAL_ERROR",
  // Created by the client when the response is not the backend's error envelope.
  HTTP_ERROR: "HTTP_ERROR",
  NETWORK_ERROR: "NETWORK_ERROR",
  TIMEOUT: "TIMEOUT",
  INVALID_RESPONSE: "INVALID_RESPONSE",
} as const;

export type ApiErrorInit = {
  status: number;
  code: string;
  message: string;
  details?: ErrorDetail[];
  requestId?: string | null;
  retryAfterSeconds?: number | null;
};

/** The single error type thrown by the API client. `status` is 0 when no response was received. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ErrorDetail[];
  readonly requestId: string | null;
  readonly retryAfterSeconds: number | null;

  constructor(init: ApiErrorInit) {
    super(init.message);
    this.name = "ApiError";
    this.status = init.status;
    this.code = init.code;
    this.details = init.details ?? [];
    this.requestId = init.requestId ?? null;
    this.retryAfterSeconds = init.retryAfterSeconds ?? null;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

const DEFAULT_MESSAGES: Record<number, string> = {
  400: "The request could not be processed.",
  401: "You need to sign in to continue.",
  403: "You do not have permission to do this.",
  404: "We could not find what you were looking for.",
  405: "This action is not supported.",
  409: "This conflicts with the current state. Refresh and try again.",
  422: "Some of the information is not valid.",
  429: "Too many requests. Please wait a moment and try again.",
  500: "Something went wrong on our side. Please try again.",
  502: "The service is temporarily unavailable. Please try again.",
  503: "The service is temporarily unavailable. Please try again.",
  504: "The service took too long to respond. Please try again.",
};

export function defaultMessageFor(status: number): string {
  if (DEFAULT_MESSAGES[status]) return DEFAULT_MESSAGES[status];
  if (status >= 500) return DEFAULT_MESSAGES[500];
  return `The request failed (HTTP ${status}).`;
}

const STATUS_CODES: Record<number, string> = {
  401: ERROR_CODES.UNAUTHENTICATED,
  403: ERROR_CODES.FORBIDDEN,
  404: ERROR_CODES.NOT_FOUND,
  405: ERROR_CODES.METHOD_NOT_ALLOWED,
  409: ERROR_CODES.CONFLICT,
  422: ERROR_CODES.VALIDATION_ERROR,
  500: ERROR_CODES.INTERNAL_ERROR,
};

/** Accepts only a body shaped like `{ error: { code, message } }`. */
export function readErrorBody(body: unknown): ErrorBody | null {
  if (typeof body !== "object" || body === null || !("error" in body)) return null;
  const error = (body as { error: unknown }).error;
  if (typeof error !== "object" || error === null) return null;
  const { code, message, details, request_id } = error as Record<string, unknown>;
  if (typeof code !== "string" || typeof message !== "string") return null;
  return {
    code,
    message,
    details: Array.isArray(details) ? (details as ErrorDetail[]) : [],
    request_id: typeof request_id === "string" ? request_id : null,
  };
}

function parseRetryAfter(value: string | null): number | null {
  if (value === null) return null;
  const seconds = Number(value);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : null;
}

/**
 * Build an ApiError from a failed response. `body` is the parsed JSON, or null when the body was
 * not JSON (for example an HTML page from a proxy or a plain-text 429).
 */
export function createApiError(response: Response, body: unknown): ApiError {
  const envelope = readErrorBody(body);
  const requestId = envelope?.request_id ?? response.headers.get("x-request-id");
  const retryAfterSeconds = parseRetryAfter(response.headers.get("retry-after"));

  if (envelope) {
    return new ApiError({
      status: response.status,
      code: envelope.code,
      message: envelope.message,
      details: envelope.details,
      requestId,
      retryAfterSeconds,
    });
  }
  return new ApiError({
    status: response.status,
    code: STATUS_CODES[response.status] ?? ERROR_CODES.HTTP_ERROR,
    message: defaultMessageFor(response.status),
    requestId,
    retryAfterSeconds,
  });
}

/** A readable message for any thrown value. */
export function getErrorMessage(error: unknown, fallback = "Something went wrong."): string {
  if (isApiError(error)) return error.message;
  return fallback;
}

/** First message per field from a 422 response, ready to hand to React Hook Form. */
export function getFieldErrors(error: unknown): Record<string, string> {
  if (!isApiError(error)) return {};
  const result: Record<string, string> = {};
  for (const detail of error.details) {
    if (detail.field && !(detail.field in result)) result[detail.field] = detail.message;
  }
  return result;
}

export function isUnauthorized(error: unknown): boolean {
  return isApiError(error) && error.status === 401;
}

/**
 * True when the backend's policy engine denied the action: a 403 that names the policy.
 * (A 403 without a policy id is something else, such as a CSRF or origin failure.)
 */
export function isPermissionDenied(error: unknown): boolean {
  return (
    isApiError(error) &&
    error.status === 403 &&
    error.details.some((detail) => Boolean(detail.policy_id))
  );
}

/** A message for a failed action. Policy denials say so clearly and keep the backend's reason. */
export function getActionErrorMessage(error: unknown, fallback = "Something went wrong."): string {
  if (isPermissionDenied(error)) {
    return `You do not have permission to do this. ${(error as ApiError).message}`;
  }
  return getErrorMessage(error, fallback);
}
