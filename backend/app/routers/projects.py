"""Project endpoints. HTTP only: validate input, call one service method, map the result."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response, status

from app.auth.dependencies import CurrentUser
from app.models import ProjectStatus
from app.repositories.project_member_repository import MemberRow
from app.routers.dependencies import ProjectServiceDep
from app.schemas.auth import UserOut
from app.schemas.common import Envelope, ErrorResponse, PagedEnvelope, PageMeta, PaginationDep
from app.schemas.project import (
    MemberOut,
    ProjectCreate,
    ProjectDetailOut,
    ProjectOut,
    ProjectUpdate,
    TaskCountsOut,
)
from app.services.project_service import ProjectView

router = APIRouter(prefix="/projects", tags=["projects"])

_Responses = dict[int | str, dict[str, Any]]
_AUTH: _Responses = {401: {"model": ErrorResponse, "description": "Not authenticated"}}
_CSRF: _Responses = {403: {"model": ErrorResponse, "description": "Not allowed"}}
_NOT_FOUND: _Responses = {
    404: {"model": ErrorResponse, "description": "Not found, or not visible to the user"}
}


def member_out(row: MemberRow) -> MemberOut:
    return MemberOut(
        user=UserOut.model_validate(row.user),
        is_owner=row.is_owner,
        joined_at=row.membership.joined_at,
    )


def project_out(view: ProjectView) -> ProjectOut:
    project = view.summary.project
    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        owner=UserOut.model_validate(view.summary.owner),
        member_count=view.summary.member_count,
        task_counts=TaskCountsOut(
            todo=view.summary.task_counts.todo,
            in_progress=view.summary.task_counts.in_progress,
            completed=view.summary.task_counts.completed,
        ),
        allowed_actions=view.allowed_actions,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def project_detail_out(view: ProjectView) -> ProjectDetailOut:
    return ProjectDetailOut(
        **project_out(view).model_dump(),
        members=[member_out(row) for row in view.members or []],
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[ProjectDetailOut],
    summary="Create a project (the caller becomes owner and first member)",
    responses={**_AUTH, **_CSRF},
)
def create_project(
    payload: ProjectCreate, user: CurrentUser, service: ProjectServiceDep
) -> Envelope[ProjectDetailOut]:
    return Envelope(data=project_detail_out(service.create_project(user, payload)))


@router.get(
    "",
    response_model=PagedEnvelope[ProjectOut],
    summary="List the projects the caller is a member of",
    responses=_AUTH,
)
def list_projects(
    user: CurrentUser,
    service: ProjectServiceDep,
    pagination: PaginationDep,
    q: Annotated[
        str | None, Query(max_length=100, description="Name contains (case-insensitive)")
    ] = None,
    status_filter: Annotated[ProjectStatus | None, Query(alias="status")] = None,
) -> PagedEnvelope[ProjectOut]:
    page = service.list_projects(
        user,
        q=q.strip() if q else None,
        status=status_filter,
        offset=pagination.offset,
        limit=pagination.page_size,
    )
    return PagedEnvelope(
        data=[project_out(view) for view in page.items],
        meta=PageMeta.of(page=pagination.page, page_size=pagination.page_size, total=page.total),
    )


@router.get(
    "/{project_id}",
    response_model=Envelope[ProjectDetailOut],
    summary="Project details with owner and members",
    responses={**_AUTH, **_NOT_FOUND},
)
def get_project(
    project_id: uuid.UUID, user: CurrentUser, service: ProjectServiceDep
) -> Envelope[ProjectDetailOut]:
    return Envelope(data=project_detail_out(service.get_project(user, project_id)))


@router.patch(
    "/{project_id}",
    response_model=Envelope[ProjectDetailOut],
    summary="Update a project (owner only, partial update)",
    responses={**_AUTH, **_CSRF, **_NOT_FOUND},
)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    user: CurrentUser,
    service: ProjectServiceDep,
) -> Envelope[ProjectDetailOut]:
    return Envelope(data=project_detail_out(service.update_project(user, project_id, payload)))


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project and everything in it (owner only)",
    responses={**_AUTH, **_CSRF, **_NOT_FOUND},
)
def delete_project(
    project_id: uuid.UUID, user: CurrentUser, service: ProjectServiceDep
) -> Response:
    service.delete_project(user, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
