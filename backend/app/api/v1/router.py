"""Version 1 of the API: aggregates all v1 routers."""

from fastapi import APIRouter

from app.routers import auth, dashboard, health, project_members, projects, tasks

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(health.router)
v1_router.include_router(auth.router)
v1_router.include_router(projects.router)
v1_router.include_router(project_members.router)
v1_router.include_router(tasks.router)
v1_router.include_router(dashboard.router)
