"""Project membership business logic (add, list, remove).

Authorization is requested from the policy engine before every call; this service never decides
access itself. Multi-step changes (clearing assignments, deleting the membership, recording
activity) happen in one transaction.
"""

import logging
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.authorization.policies import Action
from app.authorization.service import AuthorizationService
from app.core.exceptions import BusinessRuleViolation, ConflictError, NotFoundError
from app.models import ProjectMember, User
from app.models.enums import ActivityAction
from app.repositories.activity_repository import ActivityRepository
from app.repositories.project_member_repository import MemberRow, ProjectMemberRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.project import MemberCreate

logger = logging.getLogger(__name__)

USER_NOT_FOUND = "User not found."
ALREADY_MEMBER = "This user is already a member of the project."
CANNOT_REMOVE_OWNER = "The project owner cannot be removed from the project."
MEMBER_NOT_FOUND = "Member not found."


class ProjectMemberService:
    def __init__(
        self,
        db: Session,
        members: ProjectMemberRepository,
        users: UserRepository,
        tasks: TaskRepository,
        activity: ActivityRepository,
        authz: AuthorizationService,
    ) -> None:
        self.db = db
        self.members = members
        self.users = users
        self.tasks = tasks
        self.activity = activity
        self.authz = authz

    def list_members(self, user: User, project_id: uuid.UUID) -> list[MemberRow]:
        ctx = self.authz.require(user, Action.PROJECT_VIEW, project_id=project_id)
        assert ctx.project is not None  # a granted project action always has a project
        return self.members.list_rows(project_id, ctx.project.owner_id)

    def add_member(self, actor: User, project_id: uuid.UUID, data: MemberCreate) -> MemberRow:
        ctx = self.authz.require(actor, Action.PROJECT_MEMBER_MANAGE, project_id=project_id)
        assert ctx.project is not None

        target = self._find_user(data)
        if target is None or not target.is_active:
            raise NotFoundError(USER_NOT_FOUND)
        if self.members.get(project_id, target.id) is not None:
            raise ConflictError(ALREADY_MEMBER)

        membership = ProjectMember(project_id=project_id, user_id=target.id, added_by=actor.id)
        try:
            self.members.add(membership)
            self.activity.record(
                user_id=actor.id,
                action=ActivityAction.MEMBER_ADDED,
                project_id=project_id,
                meta={"member_user_id": str(target.id)},
            )
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            # Two owners' requests racing: the unique constraint decides, not our earlier check.
            if _violated(exc) == "uq_project_members_project_user":
                raise ConflictError(ALREADY_MEMBER) from exc
            if _violated(exc) == "fk_project_members_project_id_projects":
                raise NotFoundError() from exc  # the project was deleted meanwhile
            raise

        logger.info("Member added project_id=%s member_id=%s", project_id, target.id)
        return MemberRow(membership, target, is_owner=False)  # the owner is already a member

    def remove_member(self, actor: User, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Remove a member and revoke access immediately.

        Their task assignments in this project are cleared first (the database would refuse to
        remove a member who still has assigned tasks), all in one transaction. Tasks they
        created stay. Nothing is left pointing at a non-member.
        """
        ctx = self.authz.require(actor, Action.PROJECT_MEMBER_MANAGE, project_id=project_id)
        assert ctx.project is not None

        if user_id == ctx.project.owner_id:
            raise BusinessRuleViolation(CANNOT_REMOVE_OWNER)
        membership = self.members.get(project_id, user_id)
        if membership is None:
            raise NotFoundError(MEMBER_NOT_FOUND)

        unassigned = self.tasks.unassign_user_in_project(project_id, user_id)
        self.members.delete(membership)
        self.activity.record(
            user_id=actor.id,
            action=ActivityAction.MEMBER_REMOVED,
            project_id=project_id,
            meta={"member_user_id": str(user_id), "unassigned_task_count": len(unassigned)},
        )
        for task_id in unassigned:
            self.activity.record(
                user_id=actor.id,
                action=ActivityAction.TASK_UNASSIGNED,
                project_id=project_id,
                task_id=task_id,
                meta={"reason": "member_removed", "former_assignee_id": str(user_id)},
            )
        self.db.commit()
        logger.info(
            "Member removed project_id=%s member_id=%s unassigned_tasks=%d",
            project_id,
            user_id,
            len(unassigned),
        )

    def _find_user(self, data: MemberCreate) -> User | None:
        if data.email is not None:
            return self.users.get_by_email(data.email)
        assert data.user_id is not None  # the schema guarantees exactly one identifier
        return self.users.get_by_id(data.user_id)


def _violated(exc: IntegrityError) -> str | None:
    diag = getattr(exc.orig, "diag", None)
    name = getattr(diag, "constraint_name", None)
    return name if isinstance(name, str) else None
