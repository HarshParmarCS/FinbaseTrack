import type { FieldPath, FieldValues, UseFormSetError } from "react-hook-form";
import { getErrorMessage, getFieldErrors, isApiError } from "@/lib/api/errors";

type Options = { emailConflictField?: string };

/**
 * Show a failed submit on the form. Field-level problems (422, duplicate email) go on their
 * fields; everything else becomes one message above the form. Returns that message, or null.
 */
export function applyApiError<T extends FieldValues>(
  error: unknown,
  fields: readonly FieldPath<T>[],
  setError: UseFormSetError<T>,
  options: Options = {},
): string | null {
  if (!isApiError(error)) return getErrorMessage(error);

  if (error.status === 409 && options.emailConflictField) {
    setError(options.emailConflictField as FieldPath<T>, {
      type: "server",
      message: error.message,
    });
    return null;
  }

  if (error.status === 422) {
    const byField = getFieldErrors(error);
    let placed = 0;
    for (const field of fields) {
      const message = byField[field];
      if (message) {
        setError(field, { type: "server", message });
        placed += 1;
      }
    }
    return placed > 0 ? null : error.message;
  }

  return error.requestId ? `${error.message} (reference ${error.requestId})` : error.message;
}
