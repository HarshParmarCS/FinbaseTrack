import uuid
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import User
from tests.factories import expect_not_null_violation, expect_violation, make_user


def test_user_gets_uuid_defaults_and_timezone_aware_timestamps(db_session: Session) -> None:
    user = make_user(db_session)
    db_session.refresh(user)

    assert isinstance(user.id, uuid.UUID)
    assert user.is_active is True
    assert user.created_at.tzinfo is not None
    assert user.updated_at.tzinfo is not None


def test_email_must_be_unique(db_session: Session) -> None:
    make_user(db_session, email="ana@example.com")

    with expect_violation(db_session, "uq_users_email"):
        make_user(db_session, email="ana@example.com")


def test_email_must_be_lowercase(db_session: Session) -> None:
    with expect_violation(db_session, "ck_users_email_lowercase"):
        make_user(db_session, email="Ana@Example.com")


def test_email_uniqueness_cannot_be_bypassed_with_different_case(db_session: Session) -> None:
    make_user(db_session, email="ana@example.com")

    with expect_violation(db_session, "ck_users_email_lowercase"):
        make_user(db_session, email="ANA@example.com")


def test_blank_name_is_rejected(db_session: Session) -> None:
    with expect_violation(db_session, "ck_users_name_not_blank"):
        make_user(db_session, name="   ")


def test_password_hash_is_required(db_session: Session) -> None:
    with expect_not_null_violation(db_session, "password_hash"):
        db_session.execute(
            text("insert into users (name, email) values ('Ana', 'ana@example.com')")
        )


def test_updated_at_moves_forward_when_the_user_is_updated(db_session: Session) -> None:
    user = make_user(db_session)
    # now() is constant inside a transaction, so push the stored value into the past first.
    db_session.execute(
        text("update users set updated_at = now() - interval '1 day' where id = :id"),
        {"id": user.id},
    )
    db_session.refresh(user)
    before = user.updated_at

    user.name = "Ana Maria"
    db_session.flush()
    db_session.refresh(user)

    assert user.updated_at - before >= timedelta(hours=23)


def test_user_repr_never_contains_the_password_hash(db_session: Session) -> None:
    user = make_user(db_session)

    assert "argon2" not in repr(user)
    assert isinstance(user, User)
