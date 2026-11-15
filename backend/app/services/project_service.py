"""Project business logic.

Every mutation first calls ``AuthorizationService.require(...)``: the decision is made by the
policy engine, never here. This service then applies the business rules inside ONE transaction
(it owns the commit) and records an activity entry in that same transaction.
"""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.authorization.context import ProjectFacts
from app.authorization.policies import Action
from app.authorization.service import AuthorizationService
from app.core.exceptions import NotFoundError
from app.models import Project, ProjectMember, ProjectStatus, User
from app.models.enums import ActivityAction
from app.repositories.activity_repository import ActivityRepository
from app.repositories.project_member_repository import MemberRow, ProjectMemberRepository
from app.repositories.project_repository import ProjectRepository, ProjectSummary
from app.schemas.project import ProjectCreate, ProjectUpdate

logger = logging.getLogger(__name__)

# How the engine's action names map to the `allowed_actions` values in the API contract.
ALLOWED_ACTION_NAMES: dict[Action, str] = {
    Action.PROJECT_UPDATE: "update",
    Action.PROJECT_DELETE: "delete",
    Action.PROJECT_MEMBER_MANAGE: "manage_members",
    Action.TASK_CREATE: "create_task",
}
_DISPLAY_LIMIT = 200  # long text values are shortened in activity metadata


@dataclass(frozen=True, slots=True)
class ProjectView:
    summary: ProjectSummary
    allowed_actions: list[str]
    members: list[MemberRow] | None = None


@dataclass(frozen=True, slots=True)
class ProjectPage:
    items: list[ProjectView]
    total: int


def _shorten(value: object) -> object:
    if isinstance(value, str) and len(value) > _DISPLAY_LIMIT:
        return value[:_DISPLAY_LIMIT] + "..."
    return value


class ProjectService:
    def __init__(
        self,
        db: Session,
        projects: ProjectRepository,
        members: ProjectMemberRepository,
        activity: ActivityRepository,
        authz: AuthorizationService,
    ) -> None:
        self.db = db
        self.projects = projects
        self.members = members
        self.activity = activity
        self.authz = authz

    # ---- create ---------------------------------------------------------------------------

    def create_project(self, user: User, data: ProjectCreate) -> ProjectView:
        """Create the project and the owner's membership in ONE transaction.

        The database refuses to commit a project whose owner is not a member (deferred foreign
        key), so a partial write is impossible even if this code were wrong.
        """
        self.authz.require(user, Action.PROJECT_CREATE)

        project = Project(
            name=data.name,
            description=data.description,
            status=data.status,
            owner_id=user.id,  # always the authenticated user, never taken from the request
            members=[ProjectMember(user_id=user.id, added_by=user.id)],
        )
        self.projects.add(project)
        self.activity.record(
            user_id=user.id,
            action=ActivityAction.PROJECT_CREATED,
            project_id=project.id,
            meta={"name": project.name},
        )
        self.db.commit()
        logger.info("Project created project_id=%s owner_id=%s", project.id, user.id)
        return self._detail(user, project.id)

    # ---- read -----------------------------------------------------------------------------

    def list_projects(
        self,
        user: User,
        *,
        q: str | None,
        status: ProjectStatus | None,
        offset: int,
        limit: int,
    ) -> ProjectPage:
        """Only projects the user is a CURRENT member of (data scoping, see authorization docs)."""
        summaries, total = self.projects.list_summaries_for_member(
            user.id, q=q, status=status, offset=offset, limit=limit
        )
        items = [ProjectView(s, self._allowed_actions(user, s)) for s in summaries]
        return ProjectPage(items, total)

    def get_project(self, user: User, project_id: uuid.UUID) -> ProjectView:
        self.authz.require(user, Action.PROJECT_VIEW, project_id=project_id)
        return self._detail(user, project_id)

    # ---- update ---------------------------------------------------------------------------

    def update_project(self, user: User, project_id: uuid.UUID, data: ProjectUpdate) -> ProjectView:
        self.authz.require(user, Action.PROJECT_UPDATE, project_id=project_id)

        project = self.projects.get(project_id, for_update=True)
        if project is None:  # deleted by someone else between the check and now
            raise NotFoundError()

        changes: dict[str, list[object]] = {}
        for field in data.model_fields_set:  # partial update: only what the client sent
            new_value = getattr(data, field)
            old_value = getattr(project, field)
            if new_value != old_value:
                changes[field] = [_shorten(_text(old_value)), _shorten(_text(new_value))]
                setattr(project, field, new_value)

        if changes:
            self.db.flush()
            self.activity.record(
                user_id=user.id,
                action=ActivityAction.PROJECT_UPDATED,
                project_id=project.id,
                meta={"changes": changes},
            )
        self.db.commit()
        logger.info("Project updated project_id=%s fields=%s", project.id, sorted(changes))
        return self._detail(user, project_id)

    # ---- delete ---------------------------------------------------------------------------

    def delete_project(self, user: User, project_id: uuid.UUID) -> None:
        """Delete the project; the database cascades its memberships and tasks.

        The activity history is kept: ``activity_logs`` has no foreign keys, and a
        ``project.deleted`` entry is written in the same transaction as the delete.
        """
        self.authz.require(user, Action.PROJECT_DELETE, project_id=project_id)

        project = self.projects.get(project_id, for_update=True)
        if project is None:
            raise NotFoundError()
        summary = self.projects.get_summary(project_id)
        counts = summary.task_counts if summary else None

        self.activity.record(
            user_id=user.id,
            action=ActivityAction.PROJECT_DELETED,
            project_id=project.id,
            meta={
                "name": project.name,
                "member_count": summary.member_count if summary else 0,
                "task_count": (counts.todo + counts.in_progress + counts.completed)
                if counts
                else 0,
            },
        )
        self.projects.delete(project)
        self.db.commit()
        logger.info("Project deleted project_id=%s by user_id=%s", project_id, user.id)

    # ---- helpers --------------------------------------------------------------------------

    def _detail(self, user: User, project_id: uuid.UUID) -> ProjectView:
        summary = self.projects.get_summary(project_id)
        if summary is None:
            raise NotFoundError()
        members = self.members.list_rows(project_id, summary.project.owner_id)
        return ProjectView(summary, self._allowed_actions(user, summary), members)

    def _allowed_actions(self, user: User, summary: ProjectSummary) -> list[str]:
        facts = ProjectFacts(id=summary.project.id, owner_id=summary.project.owner_id)
        # The caller is a member: every row came from a membership-scoped or authorized read.
        allowed = self.authz.allowed_project_actions(user, facts, is_member=True)
        return [name for action, name in ALLOWED_ACTION_NAMES.items() if action in allowed]


def _text(value: object) -> object:
    """Enum values are stored and logged as their plain string."""
    return value.value if isinstance(value, ProjectStatus) else value
