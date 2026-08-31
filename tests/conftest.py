"""
Configuración centralizada para Pytest y fixtures.
"""

import os

# Inyectamos variables obligatorias ANTES de importar módulos que cargan config.py
os.environ["CAJACLARAD_IMAP_HOST"] = "test.imap.com"
os.environ["CAJACLARAD_IMAP_USER"] = "test@user.com"
os.environ["CAJACLARAD_IMAP_PASSWORD"] = "dummy_pass"
os.environ["CAJACLARAD_DB_PATH"] = ":memory:"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from caja_clara.models import Base


@pytest.fixture
def db_engine():
    """Create a temporary in-memory database engine for tests."""
    # We use StaticPool and check_same_thread=False for in-memory SQLite with SQLAlchemy
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db_engine):
    """Provide a transactional scope for tests."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
