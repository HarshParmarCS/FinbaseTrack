"""Refresh token database access. Queries only: no business rules, no commits."""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, token: RefreshToken) -> RefreshToken:
        self.db.add(token)
        self.db.flush()
        return token

    def get_by_hash(self, token_hash: str, *, for_update: bool = False) -> RefreshToken | None:
        """Find a token by the SHA-256 hash of its value.

        ``for_update`` locks the row, so two concurrent refreshes of the same token are
        processed one after the other (the second one is then seen as reuse).
        """
        statement = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalars(statement).first()

    def revoke_family(self, family_id: uuid.UUID, revoked_at: datetime) -> int:
        """Revoke every still-active token of a family. Returns how many were revoked."""
        result = self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
            .execution_options(synchronize_session="fetch")
        )
        return int(result.rowcount)  # type: ignore[attr-defined]  # CursorResult for DML
