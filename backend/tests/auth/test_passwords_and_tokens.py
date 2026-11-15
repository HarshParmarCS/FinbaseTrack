"""Unit tests for password hashing and JWT creation/verification (no HTTP)."""

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from argon2 import PasswordHasher

from app.auth.passwords import hash_password, password_needs_rehash, verify_password
from app.auth.tokens import (
    ACCESS_AUDIENCE,
    REFRESH_AUDIENCE,
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_token,
)
from app.core.config import get_settings
from tests.auth.helpers import forge_token

USER_ID = uuid.uuid4()


# ---- passwords ---------------------------------------------------------------------------


def test_password_is_hashed_with_argon2id_and_never_stored_in_plaintext() -> None:
    hashed = hash_password("s3cret-password")

    assert hashed.startswith("$argon2id$")
    assert "s3cret-password" not in hashed


def test_same_password_gets_a_different_salted_hash_each_time() -> None:
    assert hash_password("same-password") != hash_password("same-password")


def test_verify_password_accepts_only_the_right_password() -> None:
    hashed = hash_password("right-password")

    assert verify_password("right-password", hashed) is True
    assert verify_password("wrong-password", hashed) is False


@pytest.mark.parametrize("garbage", ["", "plaintext", "$argon2id$broken", "x" * 200])
def test_malformed_hashes_never_verify_and_never_raise(garbage: str) -> None:
    assert verify_password("anything", garbage) is False


def test_hash_with_weaker_parameters_is_flagged_for_rehash() -> None:
    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash("pw")

    assert password_needs_rehash(weak) is True
    assert password_needs_rehash(hash_password("pw")) is False


# ---- token creation ----------------------------------------------------------------------


def test_access_token_has_all_required_claims_and_is_hs256() -> None:
    issued = create_access_token(USER_ID)

    claims = jwt.decode(issued.token, options={"verify_signature": False})
    header = jwt.get_unverified_header(issued.token)
    assert header["alg"] == "HS256"
    assert set(claims) == {"sub", "iat", "exp", "iss", "aud", "jti", "token_type"}
    assert claims["sub"] == str(USER_ID)
    assert claims["iss"] == get_settings().jwt_issuer
    assert claims["aud"] == ACCESS_AUDIENCE
    assert claims["token_type"] == "access"
    assert claims["jti"] == issued.jti


def test_access_token_expires_after_fifteen_minutes() -> None:
    claims = jwt.decode(create_access_token(USER_ID).token, options={"verify_signature": False})

    assert claims["exp"] - claims["iat"] == 15 * 60


def test_refresh_token_has_its_own_audience_type_and_lasts_seven_days() -> None:
    issued = create_refresh_token(USER_ID)

    claims = jwt.decode(issued.token, options={"verify_signature": False})
    assert claims["aud"] == REFRESH_AUDIENCE
    assert claims["token_type"] == "refresh"
    assert claims["exp"] - claims["iat"] == 7 * 24 * 60 * 60
    assert issued.expires_at == datetime.fromtimestamp(claims["exp"], tz=UTC)


def test_every_token_gets_a_unique_jti_so_hashes_never_collide() -> None:
    first = create_refresh_token(USER_ID)
    second = create_refresh_token(USER_ID)

    assert first.jti != second.jti
    assert first.token != second.token
    assert hash_token(first.token) != hash_token(second.token)


def test_token_hash_is_a_64_char_sha256_hex_and_not_the_token() -> None:
    token = create_refresh_token(USER_ID).token

    digest = hash_token(token)

    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert digest != token
    assert hash_token(token) == digest


# ---- token verification --------------------------------------------------------------------


def test_valid_tokens_round_trip() -> None:
    access = decode_access_token(create_access_token(USER_ID).token)
    refresh = decode_refresh_token(create_refresh_token(USER_ID).token)

    assert access.user_id == USER_ID
    assert refresh.user_id == USER_ID


def test_token_signed_with_another_key_is_rejected() -> None:
    forged = forge_token(user_id=USER_ID, key="another-secret-key-that-is-long-enough-123")

    with pytest.raises(InvalidTokenError):
        decode_access_token(forged)


def test_tampered_payload_is_rejected() -> None:
    header, payload, signature = create_access_token(USER_ID).token.split(".")
    other_payload = forge_token(user_id=uuid.uuid4()).split(".")[1]

    with pytest.raises(InvalidTokenError):
        decode_access_token(f"{header}.{other_payload}.{signature}")
    assert payload  # the original payload was valid


def test_expired_token_is_rejected() -> None:
    old = datetime.now(UTC) - timedelta(hours=2)

    with pytest.raises(InvalidTokenError):
        decode_access_token(create_access_token(USER_ID, now=old).token)
    with pytest.raises(InvalidTokenError):
        decode_refresh_token(create_refresh_token(USER_ID, now=old - timedelta(days=8)).token)


def test_access_token_is_not_accepted_as_refresh_token_and_vice_versa() -> None:
    with pytest.raises(InvalidTokenError):
        decode_refresh_token(create_access_token(USER_ID).token)
    with pytest.raises(InvalidTokenError):
        decode_access_token(create_refresh_token(USER_ID).token)


def test_token_type_claim_is_checked_even_when_the_audience_matches() -> None:
    wrong_type = forge_token(user_id=USER_ID, token_type="refresh")  # aud is the access audience

    with pytest.raises(InvalidTokenError):
        decode_access_token(wrong_type)


@pytest.mark.parametrize("claim", ["sub", "iat", "exp", "iss", "aud", "jti"])
def test_every_standard_claim_is_required(claim: str) -> None:
    removed: dict[str, Any] = {claim: None}

    with pytest.raises(InvalidTokenError):
        decode_access_token(forge_token(user_id=USER_ID, **removed))


def test_wrong_issuer_and_audience_are_rejected() -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token(forge_token(user_id=USER_ID, iss="someone-else"))
    with pytest.raises(InvalidTokenError):
        decode_access_token(forge_token(user_id=USER_ID, aud="fintasks:other"))


@pytest.mark.filterwarnings("ignore:The HMAC key is:Warning")
def test_algorithm_is_pinned_to_hs256() -> None:
    secret = get_settings().jwt_secret_key.get_secret_value()
    claims = jwt.decode(create_access_token(USER_ID).token, options={"verify_signature": False})
    hs512 = jwt.encode(claims, secret, algorithm="HS512")  # right key, wrong algorithm
    unsigned = jwt.encode(claims, key=None, algorithm="none")  # "alg: none" attack

    for token in (hs512, unsigned):
        with pytest.raises(InvalidTokenError):
            decode_access_token(token)


@pytest.mark.parametrize("garbage", ["", "not-a-jwt", "a.b.c", "x" * 500])
def test_garbage_is_rejected_without_leaking_the_token(garbage: str) -> None:
    with pytest.raises(InvalidTokenError) as info:
        decode_access_token(garbage)

    assert garbage not in str(info.value) or garbage == ""


def test_non_uuid_subject_is_rejected() -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token(forge_token(user_id="not-a-uuid"))
