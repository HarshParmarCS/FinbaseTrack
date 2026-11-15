"""Dashboard statistics and activity feeds. HTTP only."""

import uuid
from typing import Any

from fastapi import APIRouter

from app.auth.dependencies import CurrentUser
from app.repositories.activity_repository import ActivityRow
from app.routers.dependencies import DashboardServiceDep
from app.schemas.auth import UserOut
from app.schemas.common import Envelope, ErrorResponse, PagedEnvelope, PageMeta, PaginationDep
from app.schemas.dashboard import ActivityOut, DashboardStats

router = APIRouter(tags=["dashboard"])

_Responses = dict[int | str, dict[str, Any]]
_AUTH: _Responses = {401: {"model": ErrorResponse, "description": "Not authenticated"}}
_NOT_FOUND: _Responses = {
    404: {"model": ErrorResponse, "description": "Not found, or not visible to the user"}
}


def activity_out(row: ActivityRow) -> ActivityOut:
    entry = row.entry
    return ActivityOut(
        id=entry.id,
        user=UserOut.model_validate(row.user),
        project_id=entry.project_id,
        task_id=entry.task_id,
        action=entry.action,
        metadata=entry.meta,
        created_at=entry.created_at,
    )


@router.get(
    "/dashboard/stats",
    response_model=Envelope[DashboardStats],
    summary="Dashboard statistics for the projects the caller belongs to",
    responses=_AUTH,
)
def dashboard_stats(user: CurrentUser, service: DashboardServiceDep) -> Envelope[DashboardStats]:
    result = service.dashboard(user)
    return Envelope(
        data=DashboardStats(
            total_projects=result.projects.total,
            active_projects=result.projects.active,
            total_tasks=result.tasks.total,
            completed_tasks=result.tasks.completed,
            pending_tasks=result.tasks.pending,
            overdue_tasks=result.tasks.overdue,
            assigned_to_me=result.tasks.assigned_to_me,
            recent_activity=[activity_out(row) for row in result.recent_activity],
        )
    )


@router.get(
    "/dashboard/activity",
    response_model=PagedEnvelope[ActivityOut],
    summary="Activity across the projects the caller belongs to (newest first)",
    responses=_AUTH,
)
def dashboard_activity(
    user: CurrentUser, service: DashboardServiceDep, pagination: PaginationDep
) -> PagedEnvelope[ActivityOut]:
    page = service.user_activity(user, offset=pagination.offset, limit=pagination.page_size)
    return PagedEnvelope(
        data=[activity_out(row) for row in page.items],
        meta=PageMeta.of(page=pagination.page, page_size=pagination.page_size, total=page.total),
    )


@router.get(
    "/projects/{project_id}/activity",
    response_model=PagedEnvelope[ActivityOut],
    summary="A project's activity timeline (members only, newest first)",
    responses={**_AUTH, **_NOT_FOUND},
)
def project_activity(
    project_id: uuid.UUID,
    user: CurrentUser,
    service: DashboardServiceDep,
    pagination: PaginationDep,
) -> PagedEnvelope[ActivityOut]:
    page = service.project_activity(
        user, project_id, offset=pagination.offset, limit=pagination.page_size
    )
    return PagedEnvelope(
        data=[activity_out(row) for row in page.items],
        meta=PageMeta.of(page=pagination.page, page_size=pagination.page_size, total=page.total),
    )
