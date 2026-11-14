"""Version 1 of the API: aggregates all v1 routers."""

from fastapi import APIRouter

from app.routers import health

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(health.router)
