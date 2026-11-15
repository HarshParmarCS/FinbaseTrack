"""Project membership database access. Queries only."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProjectMember, User


@dataclass(frozen=True, slots=True)
class MemberRow:
    membership: ProjectMember
    user: User
    is_owner: bool


class ProjectMemberRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, member: ProjectMember) -> ProjectMember:
        self.db.add(member)
        self.db.flush()
        return member

    def get(self, project_id: uuid.UUID, user_id: uuid.UUID) -> ProjectMember | None:
        return self.db.scalars(
            select(ProjectMember)
            .where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
            .execution_options(populate_existing=True)
        ).first()

    def list_rows(self, project_id: uuid.UUID, owner_id: uuid.UUID) -> list[MemberRow]:
        """Members with their users in ONE query: the owner first, then by join time."""
        rows = self.db.execute(
            select(ProjectMember, User)
            .join(User, User.id == ProjectMember.user_id)
            .where(ProjectMember.project_id == project_id)
            .order_by(
                (ProjectMember.user_id == owner_id).desc(),
                ProjectMember.joined_at,
                User.name,
                User.id,
            )
            .execution_options(populate_existing=True)
        ).all()
        return [MemberRow(membership, user, user.id == owner_id) for membership, user in rows]

    def delete(self, member: ProjectMember) -> None:
        self.db.delete(member)
        self.db.flush()
