import pytest
from fastapi import FastAPI
from sqlalchemy.orm import Session

from tests.projects.helpers import Actor


@pytest.fixture
def ana(app: FastAPI, db_session: Session) -> Actor:
    return Actor(app, db_session, "Ana")


@pytest.fixture
def ben(app: FastAPI, db_session: Session) -> Actor:
    return Actor(app, db_session, "Ben")


@pytest.fixture
def cy(app: FastAPI, db_session: Session) -> Actor:
    return Actor(app, db_session, "Cy")
