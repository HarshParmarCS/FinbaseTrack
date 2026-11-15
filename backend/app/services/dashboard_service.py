"""Dashboard statistics and activity feeds.

These are READ endpoints over the caller's own data. Two kinds of scoping apply:

* the dashboard and the personal feed are scoped by CURRENT membership in the query itself
  (data scoping: nothing outside the user's projects can appear), and
* a project's feed goes through the policy engine (``project.view``) first.
"""

import uuid
from dataclasses import dataclass

from app.authorization.policies import Action
from app.authorization.service import AuthorizationService
from app.core.clock import utcnow
from app.models import User
from app.repositories.activity_repository import ActivityQueries, ActivityRow
from app.repositories.dashboard_repository import DashboardRepository, ProjectStats, TaskStats

RECENT_ACTIVITY_LIMIT = 10


@dataclass(frozen=True, slots=True)
class Dashboard:
    projects: ProjectStats
    tasks: TaskStats
    recent_activity: list[ActivityRow]


@dataclass(frozen=True, slots=True)
class ActivityPage:
    items: list[ActivityRow]
    total: int


class DashboardService:
    def __init__(
        self,
        stats: DashboardRepository,
        activity: ActivityQueries,
        authz: AuthorizationService,
    ) -> None:
        self.stats = stats
        self.activity = activity
        self.authz = authz

    def dashboard(self, user: User) -> Dashboard:
        """Three queries in total (projects, tasks, recent activity), however much data exists."""
        today = utcnow().date()  # "overdue" is judged against today in UTC
        recent, _ = self.activity.for_member(user.id, offset=0, limit=RECENT_ACTIVITY_LIMIT)
        return Dashboard(
            projects=self.stats.project_stats(user.id),
            tasks=self.stats.task_stats(user.id, today),
            recent_activity=recent,
        )

    def user_activity(self, user: User, *, offset: int, limit: int) -> ActivityPage:
        rows, total = self.activity.for_member(user.id, offset=offset, limit=limit)
        return ActivityPage(rows, total)

    def project_activity(
        self, user: User, project_id: uuid.UUID, *, offset: int, limit: int
    ) -> ActivityPage:
        self.authz.require(user, Action.PROJECT_VIEW, project_id=project_id)
        rows, total = self.activity.for_project(project_id, offset=offset, limit=limit)
        return ActivityPage(rows, total)
