"""Dependency providers that wire services for the routers (HTTP-layer composition)."""

from typing import Annotated

from fastapi import Depends

from app.authorization.dependencies import AuthorizationServiceDep
from app.database.session import DbSession
from app.repositories.activity_repository import ActivityRepository
from app.repositories.project_member_repository import ProjectMemberRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.services.project_member_service import ProjectMemberService
from app.services.project_service import ProjectService


def get_project_service(db: DbSession, authz: AuthorizationServiceDep) -> ProjectService:
    return ProjectService(
        db, ProjectRepository(db), ProjectMemberRepository(db), ActivityRepository(db), authz
    )


def get_project_member_service(
    db: DbSession, authz: AuthorizationServiceDep
) -> ProjectMemberService:
    return ProjectMemberService(
        db,
        ProjectMemberRepository(db),
        UserRepository(db),
        TaskRepository(db),
        ActivityRepository(db),
        authz,
    )


ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
ProjectMemberServiceDep = Annotated[ProjectMemberService, Depends(get_project_member_service)]
