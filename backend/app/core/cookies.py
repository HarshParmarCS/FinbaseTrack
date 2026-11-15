"""Authentication cookie names, attributes and helpers (HTTP concern, no business logic)."""

import secrets

from fastapi import Response

from app.core.config import Settings

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"

DEFAULT_COOKIE_PATH = "/"
# The refresh cookie is only sent to the auth endpoints, never to normal API calls.
REFRESH_COOKIE_PATH = "/api/v1/auth"


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _set_cookie(
    response: Response,
    settings: Settings,
    *,
    name: str,
    value: str,
    max_age: int,
    path: str,
    httponly: bool,
) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        path=path,
        domain=settings.cookie_domain,
        secure=settings.cookie_secure,
        httponly=httponly,
        samesite=settings.cookie_samesite,
    )


def set_auth_cookies(response: Response, settings: Settings, *, access: str, refresh: str) -> None:
    """Set the access, refresh and CSRF cookies on a successful authentication."""
    refresh_max_age = settings.refresh_token_expire_days * 24 * 60 * 60
    _set_cookie(
        response,
        settings,
        name=ACCESS_COOKIE,
        value=access,
        max_age=settings.access_token_expire_minutes * 60,
        path=DEFAULT_COOKIE_PATH,
        httponly=True,
    )
    _set_cookie(
        response,
        settings,
        name=REFRESH_COOKIE,
        value=refresh,
        max_age=refresh_max_age,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
    )
    # Readable by the frontend on purpose: it echoes the value in the X-CSRF-Token header.
    # It grants nothing by itself, because the auth cookies are HttpOnly.
    _set_cookie(
        response,
        settings,
        name=CSRF_COOKIE,
        value=new_csrf_token(),
        max_age=refresh_max_age,
        path=DEFAULT_COOKIE_PATH,
        httponly=False,
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    """Expire all authentication cookies (attributes must match those used to set them)."""
    for name, path, httponly in (
        (ACCESS_COOKIE, DEFAULT_COOKIE_PATH, True),
        (REFRESH_COOKIE, REFRESH_COOKIE_PATH, True),
        (CSRF_COOKIE, DEFAULT_COOKIE_PATH, False),
    ):
        response.delete_cookie(
            name,
            path=path,
            domain=settings.cookie_domain,
            secure=settings.cookie_secure,
            httponly=httponly,
            samesite=settings.cookie_samesite,
        )
