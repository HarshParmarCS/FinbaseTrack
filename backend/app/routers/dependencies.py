"""Dependency providers that wire services for the routers (HTTP-layer composition)."""

from typing import Annotated

from fastapi import Depends

from app.authorization.dependencies import AuthorizationServiceDep
from app.database.session import DbSession
from app.repositories.activity_repository import ActivityQueries, ActivityRepository
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.project_member_repository import ProjectMemberRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.services.dashboard_service import DashboardService
from app.services.project_member_service import ProjectMemberService
from app.services.project_service import ProjectService
from app.services.task_service import TaskService


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


def get_task_service(db: DbSession, authz: AuthorizationServiceDep) -> TaskService:
    return TaskService(
        db, TaskRepository(db), ProjectMemberRepository(db), ActivityRepository(db), authz
    )


def get_dashboard_service(db: DbSession, authz: AuthorizationServiceDep) -> DashboardService:
    return DashboardService(DashboardRepository(db), ActivityQueries(db), authz)


ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
ProjectMemberServiceDep = Annotated[ProjectMemberService, Depends(get_project_member_service)]
TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]
