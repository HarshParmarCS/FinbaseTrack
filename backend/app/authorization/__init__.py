"""Centralized Policy-Based Access Control (PBAC). There are no roles.

Design: docs/authorization-design.md.

PEP  service.py          AuthorizationService.require*  (called by the service layer)
PDP  engine.py           PolicyEngine -> Decision        (+ registry, policies, conditions)
PAP  policies.json       validated at startup by policy_loader.py
PIP  information.py      current facts from PostgreSQL

This package root exports only the framework-free decision side (PDP). Import the enforcement
point explicitly: ``from app.authorization.service import AuthorizationService``.
"""

from app.authorization.context import AuthorizationContext, TaskChanges
from app.authorization.decision import Decision, ReasonCode
from app.authorization.engine import PolicyEngine
from app.authorization.policies import Action, PolicyConfigError
from app.authorization.policy_loader import load_policy_registry
from app.authorization.registry import PolicyRegistry

__all__ = [
    "Action",
    "AuthorizationContext",
    "Decision",
    "PolicyConfigError",
    "PolicyEngine",
    "PolicyRegistry",
    "ReasonCode",
    "TaskChanges",
    "load_policy_registry",
]
