"""Task endpoints. HTTP only: validate input, call one service method, map the result."""

import datetime as dt
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response, status
from fastapi.exceptions import RequestValidationError

from app.auth.dependencies import CurrentUser
from app.models import TaskPriority, TaskStatus
from app.repositories.task_repository import UNASSIGNED, TaskFilters, TaskSort
from app.routers.dependencies import TaskServiceDep
from app.schemas.auth import UserOut
from app.schemas.common import (
    Envelope,
    ErrorResponse,
    NoNul,
    PagedEnvelope,
    PageMeta,
    PaginationDep,
)
from app.schemas.task import (
    AssignedTaskOut,
    TaskCreate,
    TaskOut,
    TaskProjectOut,
    TaskStatusUpdate,
    TaskUpdate,
)
from app.services.task_service import AssignedTaskItem, TaskItem

router = APIRouter(tags=["tasks"])

_Responses = dict[int | str, dict[str, Any]]
_AUTH: _Responses = {401: {"model": ErrorResponse, "description": "Not authenticated"}}
_DENIED: _Responses = {
    403: {"model": ErrorResponse, "description": "Denied by a policy, or CSRF rejected"}
}
_NOT_FOUND: _Responses = {
    404: {"model": ErrorResponse, "description": "Not found, or not visible to the user"}
}
_RULE: _Responses = {
    422: {"model": ErrorResponse, "description": "Validation error or business rule violation"}
}


def task_out(item: TaskItem) -> TaskOut:
    task = item.row.task
    return TaskOut(
        id=task.id,
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        assignee=UserOut.model_validate(item.row.assignee) if item.row.assignee else None,
        creator=UserOut.model_validate(item.row.creator),
        due_date=task.due_date,
        position=task.position,
        completed_at=task.completed_at,
        allowed_actions=item.allowed_actions,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def assigned_task_out(entry: AssignedTaskItem) -> AssignedTaskOut:
    project = entry.project
    return AssignedTaskOut(
        **task_out(entry.item).model_dump(),
        project=TaskProjectOut(id=project.id, name=project.name, status=project.status),
    )


def _parse_assignee(raw: str | None) -> tuple[uuid.UUID | None, bool]:
    """``assignee_id`` is a UUID or the word ``unassigned``. Anything else is a 422."""
    if raw is None:
        return None, False
    if raw == UNASSIGNED:
        return None, True
    try:
        return uuid.UUID(raw), False
    except ValueError:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("query", "assignee_id"),
                    "msg": "must be a UUID or 'unassigned'",
                    "input": raw,
                }
            ]
        ) from None


@router.post(
    "/projects/{project_id}/tasks",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[TaskOut],
    summary="Create a task in a project (members only)",
    responses={**_AUTH, **_DENIED, **_NOT_FOUND, **_RULE},
)
def create_task(
    project_id: uuid.UUID, payload: TaskCreate, user: CurrentUser, service: TaskServiceDep
) -> Envelope[TaskOut]:
    return Envelope(data=task_out(service.create_task(user, project_id, payload)))


@router.get(
    "/projects/{project_id}/tasks",
    response_model=PagedEnvelope[TaskOut],
    summary="List, search, filter and sort a project's tasks (members only)",
    responses={**_AUTH, **_NOT_FOUND, **_RULE},
)
def list_tasks(
    project_id: uuid.UUID,
    user: CurrentUser,
    service: TaskServiceDep,
    pagination: PaginationDep,
    q: Annotated[
        str | None, Query(max_length=100, description="Title or description contains"), NoNul
    ] = None,
    status_filter: Annotated[list[TaskStatus] | None, Query(alias="status")] = None,
    priority: Annotated[list[TaskPriority] | None, Query()] = None,
    assignee_id: Annotated[str | None, Query(description="A user ID or 'unassigned'")] = None,
    due_after: Annotated[dt.date | None, Query(description="Due on or after")] = None,
    due_before: Annotated[dt.date | None, Query(description="Due on or before")] = None,
    overdue: Annotated[bool | None, Query()] = None,
    sort: Annotated[TaskSort, Query()] = TaskSort.CREATED_AT_DESC,
) -> PagedEnvelope[TaskOut]:
    assignee, unassigned = _parse_assignee(assignee_id)
    filters = TaskFilters(
        q=q.strip() if q else None,
        statuses=tuple(status_filter or ()),
        priorities=tuple(priority or ()),
        assignee_id=assignee,
        unassigned=unassigned,
        due_after=due_after,
        due_before=due_before,
        overdue=overdue,
    )
    page = service.list_tasks(
        user, project_id, filters, sort, offset=pagination.offset, limit=pagination.page_size
    )
    return PagedEnvelope(
        data=[task_out(item) for item in page.items],
        meta=PageMeta.of(page=pagination.page, page_size=pagination.page_size, total=page.total),
    )


@router.get(
    "/me/tasks",
    response_model=PagedEnvelope[AssignedTaskOut],
    summary="Tasks assigned to the caller across all of their projects",
    responses={**_AUTH, **_RULE},
)
def list_my_tasks(
    user: CurrentUser,
    service: TaskServiceDep,
    pagination: PaginationDep,
    q: Annotated[
        str | None, Query(max_length=100, description="Title or description contains"), NoNul
    ] = None,
    status_filter: Annotated[list[TaskStatus] | None, Query(alias="status")] = None,
    priority: Annotated[list[TaskPriority] | None, Query()] = None,
    project_id: Annotated[uuid.UUID | None, Query(description="Only this project")] = None,
    due_after: Annotated[dt.date | None, Query(description="Due on or after")] = None,
    due_before: Annotated[dt.date | None, Query(description="Due on or before")] = None,
    overdue: Annotated[bool | None, Query()] = None,
    sort: Annotated[TaskSort, Query()] = TaskSort.CREATED_AT_DESC,
) -> PagedEnvelope[AssignedTaskOut]:
    filters = TaskFilters(
        q=q.strip() if q else None,
        statuses=tuple(status_filter or ()),
        priorities=tuple(priority or ()),
        due_after=due_after,
        due_before=due_before,
        overdue=overdue,
    )
    page = service.list_assigned_tasks(
        user,
        filters,
        sort,
        project_id=project_id,
        offset=pagination.offset,
        limit=pagination.page_size,
    )
    return PagedEnvelope(
        data=[assigned_task_out(entry) for entry in page.items],
        meta=PageMeta.of(page=pagination.page, page_size=pagination.page_size, total=page.total),
    )


@router.get(
    "/tasks/{task_id}",
    response_model=Envelope[TaskOut],
    summary="Task details with creator and assignee (project members only)",
    responses={**_AUTH, **_NOT_FOUND},
)
def get_task(task_id: uuid.UUID, user: CurrentUser, service: TaskServiceDep) -> Envelope[TaskOut]:
    return Envelope(data=task_out(service.get_task(user, task_id)))


@router.patch(
    "/tasks/{task_id}",
    response_model=Envelope[TaskOut],
    summary="Update a task (creator or assignee). Status is changed by PATCH /tasks/{id}/status",
    responses={**_AUTH, **_DENIED, **_NOT_FOUND, **_RULE},
)
def update_task(
    task_id: uuid.UUID, payload: TaskUpdate, user: CurrentUser, service: TaskServiceDep
) -> Envelope[TaskOut]:
    return Envelope(data=task_out(service.update_task(user, task_id, payload)))


@router.patch(
    "/tasks/{task_id}/status",
    response_model=Envelope[TaskOut],
    summary="Change a task's status (and board position)",
    responses={**_AUTH, **_DENIED, **_NOT_FOUND, **_RULE},
)
def change_task_status(
    task_id: uuid.UUID, payload: TaskStatusUpdate, user: CurrentUser, service: TaskServiceDep
) -> Envelope[TaskOut]:
    return Envelope(data=task_out(service.change_status(user, task_id, payload)))


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task (project owner only, and only while it is todo)",
    responses={**_AUTH, **_DENIED, **_NOT_FOUND},
)
def delete_task(task_id: uuid.UUID, user: CurrentUser, service: TaskServiceDep) -> Response:
    service.delete_task(user, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
