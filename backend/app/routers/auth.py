"""Authentication endpoints. HTTP only: validate input, call the service, set cookies."""

from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Response, status

from app.auth.dependencies import AuthServiceDep, CurrentUser, SettingsDep
from app.core.cookies import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from app.schemas.auth import LoginIn, RegisterIn, UserOut
from app.schemas.common import Envelope, ErrorResponse

router = APIRouter(prefix="/auth", tags=["auth"])

_Responses = dict[int | str, dict[str, Any]]

_UNAUTHENTICATED: _Responses = {401: {"model": ErrorResponse, "description": "Not authenticated"}}
_CSRF: _Responses = {403: {"model": ErrorResponse, "description": "Origin or CSRF token rejected"}}


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[UserOut],
    summary="Create an account and log in",
    responses={409: {"model": ErrorResponse, "description": "Email already registered"}, **_CSRF},
)
def register(
    payload: RegisterIn, response: Response, service: AuthServiceDep, settings: SettingsDep
) -> Envelope[UserOut]:
    result = service.register(name=payload.name, email=payload.email, password=payload.password)
    set_auth_cookies(response, settings, access=result.access_token, refresh=result.refresh_token)
    return Envelope(data=UserOut.model_validate(result.user))


@router.post(
    "/login",
    response_model=Envelope[UserOut],
    summary="Log in",
    responses={**_UNAUTHENTICATED, **_CSRF},
)
def login(
    payload: LoginIn, response: Response, service: AuthServiceDep, settings: SettingsDep
) -> Envelope[UserOut]:
    result = service.login(email=payload.email, password=payload.password)
    set_auth_cookies(response, settings, access=result.access_token, refresh=result.refresh_token)
    return Envelope(data=UserOut.model_validate(result.user))


@router.post(
    "/refresh",
    response_model=Envelope[UserOut],
    summary="Rotate the refresh token and issue a new access token",
    responses={**_UNAUTHENTICATED, **_CSRF},
)
def refresh(
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> Envelope[UserOut]:
    result = service.refresh(refresh_token)
    set_auth_cookies(response, settings, access=result.access_token, refresh=result.refresh_token)
    return Envelope(data=UserOut.model_validate(result.user))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out (revoke the session and clear cookies)",
    responses=_CSRF,
)
def logout(
    service: AuthServiceDep,
    settings: SettingsDep,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> Response:
    service.logout(refresh_token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookies(response, settings)
    return response


@router.get(
    "/me",
    response_model=Envelope[UserOut],
    summary="The authenticated user",
    responses=_UNAUTHENTICATED,
)
def me(user: CurrentUser) -> Envelope[UserOut]:
    return Envelope(data=UserOut.model_validate(user))
