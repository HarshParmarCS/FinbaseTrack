"""HTTP middleware: request ID propagation and one structured log line per request."""

import logging
import re
import time
import uuid

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.exceptions import REQUEST_ID_HEADER
from app.core.logging import request_id_ctx

logger = logging.getLogger("app.request")

# Only accept client-supplied IDs that are short and harmless (prevents log injection).
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request ID, expose it in logs and the response header, log the outcome."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else str(uuid.uuid4())
        # Not reset afterwards: the 500 handler (outside this middleware) still needs it,
        # and every request runs in its own task, so the value cannot leak across requests.
        request_id_ctx.set(request_id)

        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000

        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "%s %s -> %d (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


def register_middleware(app: FastAPI) -> None:
    app.add_middleware(RequestContextMiddleware)
