import pytest


@pytest.fixture(autouse=True)
def _cheap_hashing(fast_password_hashing: None) -> None:
    """These tests exercise projects/tasks, not password hashing."""
