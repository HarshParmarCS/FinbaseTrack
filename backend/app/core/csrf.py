"""CSRF protection for cookie-authenticated, state-changing requests.

Two independent checks (defense in depth, on top of SameSite=Lax cookies):

1. Origin check: if the browser sent an ``Origin`` header, it must be the API's own origin or
   one of ALLOWED_ORIGINS. Browsers always send Origin on cross-site POST/PUT/PATCH/DELETE,
   and a page cannot forge it.
2. Double-submit token: when the request carries an authentication cookie, the header
   ``X-CSRF-Token`` must equal the (JavaScript-readable) ``csrf_token`` cookie. A forged
   cross-site request cannot read that cookie, and cannot add the custom header without a CORS
   preflight, which only ALLOWED_ORIGINS pass.

Login and registration are exempt from the token (no session exists yet) but not from the
Origin check, which also protects against login CSRF.
"""

import secrets

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.cookies import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE
from app.core.exceptions import error_response

CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
TOKEN_EXEMPT_PATHS = frozenset({"/api/v1/auth/login", "/api/v1/auth/register"})


def _forbidden(message: str) -> Response:
    return error_response(403, "FORBIDDEN", message)


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, allowed_origins: list[str]) -> None:
        super().__init__(app)
        self.allowed_origins = frozenset(allowed_origins)

    def _origin_allowed(self, request: Request, origin: str) -> bool:
        own_origin = f"{request.url.scheme}://{request.headers.get('host', '')}"
        return origin in self.allowed_origins or origin == own_origin

    @staticmethod
    def _token_valid(request: Request) -> bool:
        header = request.headers.get(CSRF_HEADER)
        cookie = request.cookies.get(CSRF_COOKIE)
        return bool(header) and bool(cookie) and secrets.compare_digest(header or "", cookie or "")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in SAFE_METHODS:
            return await call_next(request)

        origin = request.headers.get("origin")
        if origin is not None and not self._origin_allowed(request, origin):
            return _forbidden("Request origin is not allowed.")

        has_session_cookie = ACCESS_COOKIE in request.cookies or REFRESH_COOKIE in request.cookies
        if (
            has_session_cookie
            and request.url.path not in TOKEN_EXEMPT_PATHS
            and not self._token_valid(request)
        ):
            return _forbidden("CSRF token missing or invalid.")

        return await call_next(request)
