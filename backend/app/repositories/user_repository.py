"""User database access. Queries only: no business rules, no authorization, no commits."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, undefer

from app.models import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        """``email`` must already be normalized (lowercase).

        Used by login, so it also loads the (otherwise deferred) password hash.
        """
        statement = select(User).where(User.email == email).options(undefer(User.password_hash))
        return self.db.scalars(statement).first()

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user
