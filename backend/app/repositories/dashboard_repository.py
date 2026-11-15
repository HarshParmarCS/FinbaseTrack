"""Aggregate statistics for the dashboard. Read-only queries."""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Project, ProjectMember, ProjectStatus, Task, TaskStatus


@dataclass(frozen=True, slots=True)
class ProjectStats:
    total: int
    active: int


@dataclass(frozen=True, slots=True)
class TaskStats:
    total: int
    completed: int
    pending: int
    overdue: int
    assigned_to_me: int


class DashboardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def project_stats(self, user_id: uuid.UUID) -> ProjectStats:
        """Projects the user is a current member of: one query."""
        row = self.db.execute(
            select(
                func.count(),
                func.count().filter(Project.status == ProjectStatus.ACTIVE),
            )
            .select_from(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == user_id)
        ).one()
        return ProjectStats(total=row[0], active=row[1])

    def task_stats(self, user_id: uuid.UUID, today: date) -> TaskStats:
        """Counters over the tasks of the user's projects: ONE query with FILTER aggregates."""
        not_completed = Task.status != TaskStatus.COMPLETED
        row = self.db.execute(
            select(
                func.count(),
                func.count().filter(Task.status == TaskStatus.COMPLETED),
                func.count().filter(Task.status.in_((TaskStatus.TODO, TaskStatus.IN_PROGRESS))),
                func.count().filter((Task.due_date < today) & not_completed),
                func.count().filter((Task.assignee_id == user_id) & not_completed),
            )
            .select_from(Task)
            .join(
                ProjectMember,
                (ProjectMember.project_id == Task.project_id) & (ProjectMember.user_id == user_id),
            )
        ).one()
        return TaskStats(
            total=row[0],
            completed=row[1],
            pending=row[2],
            overdue=row[3],
            assigned_to_me=row[4],
        )
