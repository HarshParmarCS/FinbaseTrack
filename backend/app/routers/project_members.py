"""Project member endpoints. HTTP only."""

import uuid
from typing import Any

from fastapi import APIRouter, Response, status

from app.auth.dependencies import CurrentUser
from app.routers.dependencies import ProjectMemberServiceDep
from app.routers.projects import member_out
from app.schemas.common import Envelope, ErrorResponse
from app.schemas.project import MemberCreate, MemberOut

router = APIRouter(prefix="/projects/{project_id}/members", tags=["project members"])

_Responses = dict[int | str, dict[str, Any]]
_COMMON: _Responses = {
    401: {"model": ErrorResponse, "description": "Not authenticated"},
    403: {"model": ErrorResponse, "description": "Not allowed (owner only) or CSRF rejected"},
    404: {"model": ErrorResponse, "description": "Project not visible, or user/member not found"},
}


@router.get(
    "",
    response_model=Envelope[list[MemberOut]],
    summary="List the project's members (owner first)",
    responses={401: _COMMON[401], 404: _COMMON[404]},
)
def list_members(
    project_id: uuid.UUID, user: CurrentUser, members: ProjectMemberServiceDep
) -> Envelope[list[MemberOut]]:
    rows = members.list_members(user, project_id)
    return Envelope(data=[member_out(row) for row in rows])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[MemberOut],
    summary="Add a member by email or user ID (owner only)",
    responses={
        **_COMMON,
        409: {"model": ErrorResponse, "description": "Already a member"},
    },
)
def add_member(
    project_id: uuid.UUID,
    payload: MemberCreate,
    user: CurrentUser,
    members: ProjectMemberServiceDep,
) -> Envelope[MemberOut]:
    row = members.add_member(user, project_id, payload)
    return Envelope(data=member_out(row))


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member and revoke their access (owner only)",
    responses={
        **_COMMON,
        422: {"model": ErrorResponse, "description": "The project owner cannot be removed"},
    },
)
def remove_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    user: CurrentUser,
    members: ProjectMemberServiceDep,
) -> Response:
    members.remove_member(user, project_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
