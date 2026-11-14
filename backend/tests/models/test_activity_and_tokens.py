import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import ActivityLog, RefreshToken
from tests.factories import (
    check_deferred_constraints,
    expect_not_null_violation,
    expect_violation,
    make_project,
    make_task,
    make_user,
)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


# ---- activity_logs -------------------------------------------------------------------------


def test_activity_log_round_trips_jsonb_metadata(db_session: Session) -> None:
    user = make_user(db_session)
    entry = ActivityLog(
        user_id=user.id,
        action="task.updated",
        meta={"changes": {"status": ["todo", "in_progress"]}, "tags": [1, 2]},
    )
    db_session.add(entry)
    db_session.flush()
    db_session.expire(entry)

    assert entry.meta == {"changes": {"status": ["todo", "in_progress"]}, "tags": [1, 2]}
    assert entry.created_at.tzinfo is not None
    assert entry.project_id is None
    assert entry.task_id is None


def test_activity_log_metadata_defaults_to_an_empty_object(db_session: Session) -> None:
    user = make_user(db_session)

    db_session.execute(
        text("insert into activity_logs (user_id, action) values (:u, 'auth.login')"),
        {"u": user.id},
    )
    meta = db_session.execute(
        text("select metadata from activity_logs where user_id = :u"), {"u": user.id}
    ).scalar_one()

    assert meta == {}


def test_activity_log_requires_user_and_action(db_session: Session) -> None:
    with expect_not_null_violation(db_session, "user_id"):
        db_session.execute(text("insert into activity_logs (action) values ('x')"))

    with expect_violation(db_session, "ck_activity_logs_action_not_blank"):
        db_session.add(ActivityLog(user_id=uuid.uuid4(), action="  "))
        db_session.flush()


def test_activity_history_survives_deleting_the_task_and_the_project(db_session: Session) -> None:
    owner = make_user(db_session)
    project = make_project(db_session, owner)
    task = make_task(db_session, project, owner)
    db_session.add_all(
        [
            ActivityLog(
                user_id=owner.id, project_id=project.id, task_id=task.id, action="task.created"
            ),
            ActivityLog(
                user_id=owner.id, project_id=project.id, task_id=task.id, action="task.deleted"
            ),
        ]
    )
    db_session.flush()
    project_id = project.id

    db_session.delete(task)
    db_session.flush()
    db_session.delete(project)
    db_session.flush()
    check_deferred_constraints(db_session)

    actions = db_session.scalars(
        select(ActivityLog.action).where(ActivityLog.project_id == project_id)
    ).all()
    assert sorted(actions) == ["task.created", "task.deleted"]


# ---- refresh_tokens ------------------------------------------------------------------------


def make_token(user_id: uuid.UUID, raw: str = "opaque-token", **fields: object) -> RefreshToken:
    return RefreshToken(
        user_id=user_id,
        token_hash=sha256_hex(raw),
        family_id=uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=7),
        **fields,
    )


def test_refresh_token_stores_only_the_hash(db_session: Session) -> None:
    user = make_user(db_session)
    token = make_token(user.id, raw="super-secret-token")
    db_session.add(token)
    db_session.flush()
    db_session.refresh(token)

    assert token.token_hash == sha256_hex("super-secret-token")
    assert "super-secret-token" not in repr(token)
    assert token.revoked_at is None
    assert token.replaced_by is None
    assert token.created_at.tzinfo is not None
    assert token.expires_at.tzinfo is not None


def test_plaintext_tokens_cannot_be_stored(db_session: Session) -> None:
    user = make_user(db_session)

    with expect_violation(db_session, "ck_refresh_tokens_token_hash_sha256_hex"):
        db_session.add(
            RefreshToken(
                user_id=user.id,
                token_hash="a-raw-opaque-token",
                family_id=uuid.uuid4(),
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
        db_session.flush()


def test_token_hash_must_be_unique(db_session: Session) -> None:
    user = make_user(db_session)
    db_session.add(make_token(user.id, raw="same"))
    db_session.flush()

    with expect_violation(db_session, "uq_refresh_tokens_token_hash"):
        db_session.add(make_token(user.id, raw="same"))
        db_session.flush()


def test_token_must_expire_after_it_was_created(db_session: Session) -> None:
    user = make_user(db_session)

    with expect_violation(db_session, "ck_refresh_tokens_expires_after_creation"):
        db_session.add(
            RefreshToken(
                user_id=user.id,
                token_hash=sha256_hex("x"),
                family_id=uuid.uuid4(),
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        db_session.flush()


def test_token_requires_an_existing_user(db_session: Session) -> None:
    with expect_violation(db_session, "fk_refresh_tokens_user_id_users"):
        db_session.add(make_token(uuid.uuid4()))
        db_session.flush()


def test_deleting_a_user_deletes_their_tokens(db_session: Session) -> None:
    user = make_user(db_session)
    db_session.add_all([make_token(user.id, raw="a"), make_token(user.id, raw="b")])
    db_session.flush()

    db_session.execute(text("delete from users where id = :id"), {"id": user.id})

    remaining = db_session.execute(
        text("select count(*) from refresh_tokens where user_id = :id"), {"id": user.id}
    ).scalar_one()
    assert remaining == 0


def test_rotation_chain_is_kept_and_cleared_when_the_replacement_is_deleted(
    db_session: Session,
) -> None:
    user = make_user(db_session)
    old = make_token(user.id, raw="old")
    new = make_token(user.id, raw="new")
    db_session.add_all([old, new])
    db_session.flush()
    old.replaced_by = new.id
    old.revoked_at = datetime.now(UTC)
    db_session.flush()

    assert old.replaced_by == new.id

    db_session.execute(text("delete from refresh_tokens where id = :id"), {"id": new.id})
    db_session.refresh(old)

    assert old.replaced_by is None
    assert old.revoked_at is not None
