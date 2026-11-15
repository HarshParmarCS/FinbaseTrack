import pytest

from tests.tasks.helpers import team  # noqa: F401  (fixture)


@pytest.fixture(autouse=True)
def _cheap_hashing(fast_password_hashing: None) -> None:
    """These tests exercise the API, not password hashing."""
