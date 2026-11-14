import logging
import uuid

import pytest
from fastapi.testclient import TestClient


def test_health_returns_ok_in_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"data": {"status": "ok"}}


def test_health_is_only_available_under_api_version_prefix(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_health_rejects_unsupported_method_with_error_envelope(client: TestClient) -> None:
    response = client.post("/api/v1/health")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_response_contains_generated_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    request_id = response.headers["X-Request-ID"]
    assert uuid.UUID(request_id)


def test_safe_incoming_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "trace-abc_123"})

    assert response.headers["X-Request-ID"] == "trace-abc_123"


@pytest.mark.parametrize("bad_id", ["has space", "x" * 65, "semi;colon"])
def test_unsafe_incoming_request_id_is_replaced(client: TestClient, bad_id: str) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": bad_id})

    assert response.headers["X-Request-ID"] != bad_id
    assert uuid.UUID(response.headers["X-Request-ID"])


def test_request_is_logged_with_method_path_and_status(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.get("/api/v1/health")

    messages = [record.getMessage() for record in caplog.records if record.name == "app.request"]
    assert any(m.startswith("GET /api/v1/health -> 200") for m in messages)
