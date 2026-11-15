"""Time source. One place to replace in tests."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)
