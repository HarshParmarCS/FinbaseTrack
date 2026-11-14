import json
import logging

from app.core.logging import JsonFormatter, RequestIdFilter, request_id_ctx


def _record(message: str = "hello", exc_info: object = None) -> logging.LogRecord:
    return logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=exc_info,  # type: ignore[arg-type]
    )


def test_json_formatter_emits_single_line_json_with_request_id() -> None:
    record = _record()
    token = request_id_ctx.set("req-1")
    try:
        RequestIdFilter().filter(record)
    finally:
        request_id_ctx.reset(token)

    line = JsonFormatter().format(record)

    payload = json.loads(line)
    assert "\n" not in line
    assert payload["message"] == "hello"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["request_id"] == "req-1"
    assert payload["timestamp"].endswith("+00:00")


def test_json_formatter_includes_exception_traceback() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _record(exc_info=sys.exc_info())

    payload = json.loads(JsonFormatter().format(record))

    assert "ValueError: boom" in payload["exception"]


def test_request_id_defaults_to_dash_outside_a_request() -> None:
    record = _record()

    RequestIdFilter().filter(record)

    assert record.request_id == "-"  # type: ignore[attr-defined]
