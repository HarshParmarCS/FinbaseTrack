"""In-memory builders for authorization tests (no database)."""

import json
import uuid
from datetime import date
from typing import Any

from app.authorization.context import (
    AuthorizationContext,
    ProjectFacts,
    Subject,
    TaskFacts,
)
from app.authorization.engine import PolicyEngine
from app.authorization.policies import Action
from app.authorization.policy_loader import load_policy_registry
from app.core.config import DEFAULT_POLICY_FILE

OWNER = uuid.UUID("00000000-0000-0000-0000-00000000000a")
MEMBER = uuid.UUID("00000000-0000-0000-0000-00000000000b")
ASSIGNEE = uuid.UUID("00000000-0000-0000-0000-00000000000c")
OUTSIDER = uuid.UUID("00000000-0000-0000-0000-00000000000d")
PROJECT = ProjectFacts(id=uuid.UUID("00000000-0000-0000-0000-0000000000a1"), owner_id=OWNER)
OTHER_PROJECT_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a2")


def shipped_engine() -> PolicyEngine:
    return PolicyEngine(load_policy_registry(DEFAULT_POLICY_FILE))


def shipped_document() -> dict[str, Any]:
    """A fresh copy of the real policies.json as parsed JSON (tests mutate it)."""
    document: dict[str, Any] = json.loads(DEFAULT_POLICY_FILE.read_text())
    return document


def make_task(**overrides: Any) -> TaskFacts:
    """A complete, assigned, todo task created by MEMBER and assigned to ASSIGNEE."""
    fields: dict[str, Any] = {
        "id": uuid.UUID("00000000-0000-0000-0000-0000000000f1"),
        "project_id": PROJECT.id,
        "creator_id": MEMBER,
        "assignee_id": ASSIGNEE,
        "status": "todo",
        "title": "Design login page",
        "description": "Wireframes and copy",
        "priority": "high",
        "due_date": date(2026, 12, 1),
    }
    fields.update(overrides)
    return TaskFacts(**fields)


def make_context(
    action: Action | str,
    user_id: uuid.UUID = MEMBER,
    *,
    member: bool = True,
    project: ProjectFacts | None = PROJECT,
    task: TaskFacts | None = None,
    proposed: TaskFacts | None = None,
    assignee_member: bool = True,
    active: bool = True,
) -> AuthorizationContext:
    return AuthorizationContext(
        subject=Subject(id=user_id, is_active=active),
        action=str(action),
        project=project,
        is_project_member=member,
        task=task,
        proposed_task=proposed,
        assignee_is_project_member=assignee_member,
    )
