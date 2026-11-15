"""JWT creation and verification for access and refresh tokens.

Access and refresh tokens are different on purpose: they have different audiences AND a
``token_type`` claim, so one can never be accepted in place of the other. Verification is pinned
to HS256 (no ``alg`` negotiation, so ``none`` and algorithm-confusion tokens are rejected) and
requires every standard claim. The signing key comes from settings and never leaves the server.

Only the SHA-256 hash of a refresh token is ever stored (see ``hash_token``).
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import jwt

from app.core.config import get_settings

ALGORITHM = "HS256"
ACCESS_AUDIENCE = "fintasks:access"
REFRESH_AUDIENCE = "fintasks:refresh"
REQUIRED_CLAIMS = ["sub", "iat", "exp", "iss", "aud", "jti"]


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class InvalidTokenError(Exception):
    """The token is malformed, forged, expired, or not of the expected kind.

    The message is deliberately generic: it never contains the token.
    """


@dataclass(frozen=True)
class IssuedToken:
    token: str
    jti: str
    expires_at: datetime


@dataclass(frozen=True)
class TokenClaims:
    user_id: uuid.UUID
    jti: str
    issued_at: datetime
    expires_at: datetime


_AUDIENCES = {TokenType.ACCESS: ACCESS_AUDIENCE, TokenType.REFRESH: REFRESH_AUDIENCE}


def _issue(
    user_id: uuid.UUID, token_type: TokenType, lifetime: timedelta, now: datetime | None
) -> IssuedToken:
    settings = get_settings()
    issued_at = (now or datetime.now(UTC)).replace(microsecond=0)
    expires_at = issued_at + lifetime
    jti = uuid.uuid4().hex  # unique per token: two tokens never hash to the same value
    payload = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": expires_at,
        "iss": settings.jwt_issuer,
        "aud": _AUDIENCES[token_type],
        "jti": jti,
        "token_type": token_type.value,
    }
    token = jwt.encode(payload, settings.jwt_secret_key.get_secret_value(), algorithm=ALGORITHM)
    return IssuedToken(token=token, jti=jti, expires_at=expires_at)


def create_access_token(user_id: uuid.UUID, *, now: datetime | None = None) -> IssuedToken:
    lifetime = timedelta(minutes=get_settings().access_token_expire_minutes)
    return _issue(user_id, TokenType.ACCESS, lifetime, now)


def create_refresh_token(user_id: uuid.UUID, *, now: datetime | None = None) -> IssuedToken:
    lifetime = timedelta(days=get_settings().refresh_token_expire_days)
    return _issue(user_id, TokenType.REFRESH, lifetime, now)


def _decode(token: str, expected_type: TokenType) -> TokenClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[ALGORITHM],  # restrict verification to the expected algorithm
            audience=_AUDIENCES[expected_type],
            issuer=settings.jwt_issuer,
            options={"require": REQUIRED_CLAIMS},
        )
        if payload.get("token_type") != expected_type.value:
            raise InvalidTokenError("Unexpected token type")
        return TokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            jti=payload["jti"],
            issued_at=datetime.fromtimestamp(payload["iat"], tz=UTC),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
    except InvalidTokenError:
        raise
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
        # Never include the token or the library message (it may echo claims).
        raise InvalidTokenError("Invalid token") from exc


def decode_access_token(token: str) -> TokenClaims:
    """Verify signature, expiry, issuer, audience and type of an ACCESS token."""
    return _decode(token, TokenType.ACCESS)


def decode_refresh_token(token: str) -> TokenClaims:
    """Verify signature, expiry, issuer, audience and type of a REFRESH token."""
    return _decode(token, TokenType.REFRESH)


def hash_token(token: str) -> str:
    """SHA-256 hex digest (64 chars): the only form in which a refresh token is stored."""
    return hashlib.sha256(token.encode()).hexdigest()
