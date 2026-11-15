"""FastAPI providers for the authorization module (the only file here that imports FastAPI).

The denied-to-403/404 conversion is not done here: ``AuthorizationService`` raises domain
errors (PermissionDeniedError, NotFoundError) and the central exception handlers in
``app.core.exceptions`` produce the HTTP responses. 401 is a different failure: it comes from
``get_current_user`` before any authorization decision is made.
"""

from typing import Annotated

from fastapi import Depends, Request

from app.authorization.engine import PolicyEngine
from app.authorization.information import PolicyInformationPoint
from app.authorization.service import AuthorizationService
from app.database.session import DbSession


def get_policy_engine(request: Request) -> PolicyEngine:
    """The engine built (and validated) once at application startup."""
    engine: PolicyEngine = request.app.state.policy_engine
    return engine


def get_authorization_service(
    db: DbSession, engine: Annotated[PolicyEngine, Depends(get_policy_engine)]
) -> AuthorizationService:
    return AuthorizationService(engine, PolicyInformationPoint(db))


AuthorizationServiceDep = Annotated[AuthorizationService, Depends(get_authorization_service)]
