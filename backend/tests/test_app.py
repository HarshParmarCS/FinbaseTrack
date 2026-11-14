from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app as module_level_app
from app.main import create_app


def test_create_app_returns_configured_fastapi_instance() -> None:
    application = create_app()

    assert isinstance(application, FastAPI)
    assert application.title == "FinTasks API"


def test_module_level_app_is_available_for_uvicorn() -> None:
    assert isinstance(module_level_app, FastAPI)


def test_health_route_is_registered_under_api_v1() -> None:
    paths = create_app().openapi()["paths"]

    assert "/api/v1/health" in paths


def test_each_create_app_call_returns_an_independent_instance() -> None:
    assert create_app() is not create_app()


def test_openapi_schema_and_swagger_ui_are_served(client: TestClient) -> None:
    schema = client.get("/openapi.json")
    docs = client.get("/docs")

    assert schema.status_code == 200
    assert "/api/v1/health" in schema.json()["paths"]
    assert docs.status_code == 200
