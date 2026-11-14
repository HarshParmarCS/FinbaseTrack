import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    desc,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import TaskPriority, TaskStatus, enum_column_type, in_values_check
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="title_not_blank"),
        CheckConstraint(in_values_check("status", TaskStatus), name="status_valid"),
        CheckConstraint(in_values_check("priority", TaskPriority), name="priority_valid"),
        CheckConstraint(
            "(status = 'completed') = (completed_at IS NOT NULL)",
            name="completed_at_matches_status",
        ),
        # An assignee must be a member of the task's project. MATCH SIMPLE: not checked while
        # assignee_id is NULL. A member with assigned tasks cannot be removed (unassign first).
        ForeignKeyConstraint(
            ["project_id", "assignee_id"],
            ["project_members.project_id", "project_members.user_id"],
            name="fk_tasks_assignee_member",
        ),
        Index("ix_tasks_project_status_position", "project_id", "status", "position"),
        Index("ix_tasks_project_created_at", "project_id", desc("created_at")),
        Index("ix_tasks_project_due_date", "project_id", "due_date"),
        Index("ix_tasks_assignee_id", "assignee_id"),
        # Trigram indexes make ILIKE '%text%' search fast.
        Index(
            "ix_tasks_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index(
            "ix_tasks_description_trgm",
            "description",
            postgresql_using="gin",
            postgresql_ops={"description": "gin_trgm_ops"},
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(
        enum_column_type(TaskStatus),
        default=TaskStatus.TODO,
        server_default=TaskStatus.TODO.value,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        enum_column_type(TaskPriority),
        default=TaskPriority.MEDIUM,
        server_default=TaskPriority.MEDIUM.value,
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    position: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped["Project"] = relationship(back_populates="tasks")
    creator: Mapped["User"] = relationship(foreign_keys=[creator_id])
    assignee: Mapped["User | None"] = relationship(foreign_keys=[assignee_id])

    def __repr__(self) -> str:
        return f"Task(id={self.id!r}, title={self.title!r}, status={self.status!r})"
