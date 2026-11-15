"""FastAPI dependencies for authentication."""

from typing import Annotated

from fastapi import Cookie, Depends

from app.core.config import Settings, get_settings
from app.core.cookies import ACCESS_COOKIE
from app.database.session import DbSession
from app.models import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_auth_service(db: DbSession) -> AuthService:
    return AuthService(db, UserRepository(db), RefreshTokenRepository(db))


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_current_user(
    service: AuthServiceDep,
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
) -> User:
    """The authenticated, active user. Raises 401 for anything else.

    Reads the access token from the HttpOnly cookie, verifies signature, expiry, issuer,
    audience and token type, then loads the user from the database. The identity comes only
    from the verified token, never from the request body or query.
    """
    return service.get_user_from_access_token(access_token)


CurrentUser = Annotated[User, Depends(get_current_user)]
