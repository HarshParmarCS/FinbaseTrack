"""FastAPI application factory."""

import logging

from fastapi import FastAPI

from app.api.router import api_router
from app.authorization.engine import PolicyEngine
from app.authorization.policy_loader import load_policy_registry
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import register_middleware
from app.core.openapi import install_openapi

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. Tests can call this to get an isolated instance."""
    settings = settings or get_settings()
    setup_logging(level=settings.log_level, json_output=settings.environment != "development")

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "FinTasks project management API.\n\n"
            "Authentication uses HttpOnly cookies (`access_token`, `refresh_token`) set by "
            "register/login. State-changing requests that carry cookies must also send the "
            "`X-CSRF-Token` header (the value of the `csrf_token` cookie). Authorization is "
            "policy-based (PBAC): see docs/authorization-design.md."
        ),
    )
    # Fail fast: an invalid or incomplete policy file stops the application from starting.
    registry = load_policy_registry(settings.policy_file)
    app.state.policy_engine = PolicyEngine(registry)
    logger.info("Authorization policies loaded count=%d", len(registry))

    register_middleware(app, settings)
    register_exception_handlers(app)
    app.include_router(api_router)
    install_openapi(app)

    logger.info("Application initialized (environment=%s)", settings.environment)
    return app


app = create_app()
