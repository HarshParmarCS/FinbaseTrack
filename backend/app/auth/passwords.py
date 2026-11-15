"""Password hashing with Argon2id (argon2-cffi defaults, RFC 9106 low-memory profile)."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

# Verified against when the account does not exist, so that "unknown email" and "wrong password"
# take about the same time and cannot be told apart by timing.
_DUMMY_HASH = _hasher.hash("fintasks-dummy-password-for-constant-time-login")


def hash_password(password: str) -> str:
    """Return a salted Argon2id hash. The plaintext is never stored or logged."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """True only if the password matches. Malformed hashes simply fail verification."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def verify_dummy_password(password: str) -> None:
    """Spend the same effort as a real verification (used for unknown accounts)."""
    verify_password(password, _DUMMY_HASH)


def password_needs_rehash(password_hash: str) -> bool:
    """True when the stored hash uses weaker parameters than the current defaults."""
    return _hasher.check_needs_rehash(password_hash)
