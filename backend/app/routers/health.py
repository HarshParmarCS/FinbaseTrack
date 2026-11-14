"""Health check endpoint."""

from fastapi import APIRouter

from app.schemas.common import Envelope
from app.schemas.health import HealthOut

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=Envelope[HealthOut],
    summary="Liveness check",
)
def health() -> Envelope[HealthOut]:
    """Report that the API process is running. Does not touch the database."""
    return Envelope(data=HealthOut(status="ok"))
