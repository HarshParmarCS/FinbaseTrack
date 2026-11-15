"""Authentication business logic: registration, login, token rotation, logout.

No HTTP types here (cookies and status codes belong to the router and the exception handlers)
and no authorization decisions (PBAC arrives in a later milestone). The service owns commits.
"""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.passwords import (
    hash_password,
    password_needs_rehash,
    verify_dummy_password,
    verify_password,
)
from app.auth.tokens import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_token,
)
from app.core.clock import utcnow
from app.core.exceptions import ConflictError, SessionInvalidError, UnauthenticatedError
from app.models import RefreshToken, User
from app.models.enums import ActivityAction
from app.repositories.activity_repository import ActivityRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository

# Never logged: passwords, token values, password hashes. Only IDs.
logger = logging.getLogger(__name__)

INVALID_CREDENTIALS = "Invalid email or password."
NOT_AUTHENTICATED = "Authentication is missing, invalid or expired."


@dataclass(frozen=True)
class AuthResult:
    user: User
    access_token: str
    refresh_token: str


class AuthService:
    def __init__(
        self,
        db: Session,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        activity: ActivityRepository,
    ) -> None:
        self.db = db
        self.users = users
        self.refresh_tokens = refresh_tokens
        self.activity = activity

    # ---- register / login ------------------------------------------------------------------

    def register(self, *, name: str, email: str, password: str) -> AuthResult:
        """Create the account and log the user in. ``email`` is already normalized."""
        if self.users.get_by_email(email) is not None:
            raise ConflictError("An account with this email already exists.")

        user = User(name=name, email=email, password_hash=hash_password(password))
        try:
            self.users.add(user)
            result, _ = self._issue_tokens(user, family_id=uuid.uuid4())
            self.activity.record(user_id=user.id, action=ActivityAction.USER_REGISTERED)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            # Two simultaneous registrations with the same email: the database decides.
            if (
                getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
                == "uq_users_email"
            ):
                raise ConflictError("An account with this email already exists.") from exc
            raise
        logger.info("User registered user_id=%s", user.id)
        return result

    def login(self, *, email: str, password: str) -> AuthResult:
        """Verify credentials and open a new session (a new refresh-token family)."""
        user = self.users.get_by_email(email)
        if user is None:
            verify_dummy_password(password)  # same work as a real check: no timing oracle
            raise UnauthenticatedError(INVALID_CREDENTIALS)
        if not verify_password(password, user.password_hash) or not user.is_active:
            # Wrong password and inactive account are indistinguishable to the caller.
            raise UnauthenticatedError(INVALID_CREDENTIALS)

        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        result, _ = self._issue_tokens(user, family_id=uuid.uuid4())
        self.activity.record(user_id=user.id, action=ActivityAction.AUTH_LOGIN)
        self.db.commit()
        logger.info("User logged in user_id=%s", user.id)
        return result

    # ---- refresh / logout ------------------------------------------------------------------

    def refresh(self, raw_token: str | None) -> AuthResult:
        """Rotate the refresh token: revoke the presented one, issue a new pair.

        A token that was already rotated or revoked and is presented again is a sign of theft
        (or a replayed copy): the whole family is revoked so neither party keeps access.
        """
        if not raw_token:
            raise SessionInvalidError()
        try:
            claims = decode_refresh_token(raw_token)  # rejects access tokens, bad signatures...
        except InvalidTokenError as exc:
            raise SessionInvalidError() from exc

        now = utcnow()
        stored = self.refresh_tokens.get_by_hash(hash_token(raw_token), for_update=True)
        if stored is None or stored.user_id != claims.user_id:
            raise SessionInvalidError()

        if stored.revoked_at is not None:
            self.refresh_tokens.revoke_family(stored.family_id, now)
            self.activity.record(
                user_id=stored.user_id,
                action=ActivityAction.AUTH_REFRESH_REUSE_DETECTED,
                meta={"family_id": str(stored.family_id)},
            )
            self.db.commit()  # persist the revocation BEFORE failing the request
            logger.warning(
                "Refresh token reuse detected; family revoked user_id=%s family_id=%s",
                stored.user_id,
                stored.family_id,
            )
            raise SessionInvalidError()

        if stored.expires_at <= now:
            raise SessionInvalidError()

        user = self.users.get_by_id(stored.user_id)
        if user is None or not user.is_active:
            self.refresh_tokens.revoke_family(stored.family_id, now)
            self.db.commit()
            raise SessionInvalidError()

        result, replacement = self._issue_tokens(user, family_id=stored.family_id)
        stored.revoked_at = now
        stored.replaced_by = replacement.id
        self.db.commit()
        logger.info("Refresh token rotated user_id=%s", user.id)
        return result

    def logout(self, raw_token: str | None) -> None:
        """Revoke the session of the presented refresh token. Never fails on bad input."""
        if not raw_token:
            return
        stored = self.refresh_tokens.get_by_hash(hash_token(raw_token))
        if stored is None:
            return
        self.refresh_tokens.revoke_family(stored.family_id, utcnow())
        self.activity.record(user_id=stored.user_id, action=ActivityAction.AUTH_LOGOUT)
        self.db.commit()
        logger.info("User logged out user_id=%s", stored.user_id)

    # ---- access-token authentication (used by get_current_user) -------------------------------

    def get_user_from_access_token(self, token: str | None) -> User:
        if not token:
            raise UnauthenticatedError(NOT_AUTHENTICATED)
        try:
            claims = decode_access_token(token)
        except InvalidTokenError as exc:
            raise UnauthenticatedError(NOT_AUTHENTICATED) from exc

        user = self.users.get_by_id(claims.user_id)
        if user is None or not user.is_active:
            raise UnauthenticatedError(NOT_AUTHENTICATED)
        return user

    # ---- internals -------------------------------------------------------------------------

    def _issue_tokens(self, user: User, *, family_id: uuid.UUID) -> tuple[AuthResult, RefreshToken]:
        """Create an access token and a refresh token; persist only the refresh token's hash."""
        access = create_access_token(user.id)
        refresh = create_refresh_token(user.id)
        row = self.refresh_tokens.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_token(refresh.token),
                family_id=family_id,
                expires_at=refresh.expires_at,
            )
        )
        return AuthResult(user, access.token, refresh.token), row
