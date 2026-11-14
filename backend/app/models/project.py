import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.enums import ProjectStatus, enum_column_type, in_values_check
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project_member import ProjectMember
    from app.models.task import Task
    from app.models.user import User


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint(in_values_check("status", ProjectStatus), name="status_valid"),
        # The owner must be a member. DEFERRED so the project and the owner's membership row can
        # be inserted in either order inside one transaction; checked at COMMIT. It also stops
        # the owner's membership from being removed while the project exists.
        # use_alter: this constraint closes a table cycle with project_members.
        ForeignKeyConstraint(
            ["id", "owner_id"],
            ["project_members.project_id", "project_members.user_id"],
            name="fk_projects_owner_member",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        Index("ix_projects_owner_id", "owner_id"),
        Index("ix_projects_status", "status"),
    )

    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProjectStatus] = mapped_column(
        enum_column_type(ProjectStatus),
        default=ProjectStatus.ACTIVE,
        server_default=ProjectStatus.ACTIVE.value,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))

    owner: Mapped["User"] = relationship(back_populates="owned_projects", foreign_keys=[owner_id])
    # The database cascades deletes (ON DELETE CASCADE), so the ORM does not load children first.
    members: Mapped[list["ProjectMember"]] = relationship(
        back_populates="project",
        foreign_keys="ProjectMember.project_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"Project(id={self.id!r}, name={self.name!r})"
