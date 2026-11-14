import uuid
from typing import Any

from sqlalchemy import CheckConstraint, Index, String, Uuid, desc, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class ActivityLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Append-only audit trail and activity timeline.

    user_id, project_id and task_id are deliberately NOT foreign keys: with hard deletes, the
    history of a deleted project or task must survive and stay readable (see database-design.md).
    """

    __tablename__ = "activity_logs"
    __table_args__ = (
        CheckConstraint("length(trim(action)) > 0", name="action_not_blank"),
        Index("ix_activity_logs_project_created", "project_id", desc("created_at")),
        Index("ix_activity_logs_user_created", "user_id", desc("created_at")),
        Index("ix_activity_logs_task_created", "task_id", desc("created_at")),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    project_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(String(50))
    # "metadata" is reserved on declarative classes, so the attribute is `meta`.
    meta: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, server_default=text("'{}'::jsonb")
    )

    def __repr__(self) -> str:
        return f"ActivityLog(id={self.id!r}, action={self.action!r})"
