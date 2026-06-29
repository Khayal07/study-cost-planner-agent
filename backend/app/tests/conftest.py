"""Shared pytest fixtures: an in-memory SQLite DB + FastAPI TestClient.

These power the API-route smoke tests. We use SQLite (no Postgres/pgvector needed
in CI) and create every table except ``knowledge_chunks`` — its pgvector ``Vector``
column has no SQLite equivalent and isn't exercised by the routes under test.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.data import models  # noqa: F401  (registers tables on Base.metadata)
from app.data.db import Base, get_session
from app.main import app


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    tables = [t for name, t in Base.metadata.tables.items() if name != "knowledge_chunks"]
    Base.metadata.create_all(bind=engine, tables=tables)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    def _override() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
