"""Dashboard and activity schemas (see docs/api-contract.md, section 3.6)."""

import datetime as dt
import uuid
from typing import Any

from pydantic import BaseModel

from app.schemas.auth import UserOut


class ActivityOut(BaseModel):
    id: uuid.UUID
    user: UserOut
    project_id: uuid.UUID | None
    task_id: uuid.UUID | None
    action: str
    metadata: dict[str, Any]
    created_at: dt.datetime


class DashboardStats(BaseModel):
    total_projects: int
    active_projects: int
    total_tasks: int
    completed_tasks: int
    pending_tasks: int
    overdue_tasks: int
    assigned_to_me: int
    recent_activity: list[ActivityOut]
