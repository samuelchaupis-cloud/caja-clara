"""
Database connection and session management.
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

# Note: The actual path should be loaded from config, but for Alembic and early
# initialization, we provide a default that config.py will override.
DB_URL = "sqlite:///./cajaclarad.db"

engine = create_engine(
    DB_URL,
    connect_args={"timeout": 15},
    pool_pre_ping=True,
)


@event.listens_for(Engine, "connect")
def set_sqlite_pragmas(dbapi_connection: sqlite3.Connection, connection_record: object) -> None:
    """Sets necessary PRAGMAs for SQLite on every connection."""
    if type(dbapi_connection) is sqlite3.Connection:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


from sqlalchemy import text


def verify_db_integrity(db_engine: Engine) -> None:
    """Check SQLite database integrity."""
    with db_engine.connect() as conn:
        result = conn.execute(text("PRAGMA integrity_check")).scalar()
        if result != "ok":
            logger.critical(f"Database integrity check failed: {result}")
            raise RuntimeError("Database corruption detected")


def verify_schema_version(db_engine: Engine) -> None:
    """Verify Alembic schema version matches expected head."""
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from alembic.script import ScriptDirectory

    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    
    with db_engine.connect() as conn:
        context = MigrationContext.configure(conn)
        current_rev = context.get_current_revision()
        
    head_rev = script.get_current_head()
    
    if current_rev != head_rev:
        logger.critical(f"Incompatible schema version. Current: {current_rev}, Expected: {head_rev}")
        raise RuntimeError("Schema version mismatch")
