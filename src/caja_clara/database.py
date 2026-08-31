"""
Database connection and session management.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Generator

import structlog
from sqlalchemy import Connection, create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from caja_clara.config import config

logger = structlog.get_logger()

engine = create_engine(
    f"sqlite:///{config.db_path}",
    connect_args={"timeout": 30},
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragmas(dbapi_connection: sqlite3.Connection, connection_record: object) -> None:
    """Configura los pragmas de SQLite para concurrencia WAL."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


@event.listens_for(engine, "begin")
def do_begin(conn: Connection) -> None:
    """Fuerza BEGIN IMMEDIATE en SQLite para prevenir deadlocks SQLITE_BUSY (Protocolo 4.2)."""
    conn.exec_driver_sql("BEGIN IMMEDIATE")


def setup_sqlite_immutability_triggers(db_engine: Engine) -> None:
    """Instala triggers de inmutabilidad en SQLite para sellar registros contables PROCESSED."""
    with db_engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS trg_invoice_records_immutable_update
                BEFORE UPDATE ON invoice_records
                FOR EACH ROW
                WHEN OLD.status = 'PROCESSED'
                BEGIN
                    SELECT RAISE(ABORT, 'LEDGER_IMMUTABILITY_VIOLATION: No se permite modificar un comprobante PROCESSED');
                END;
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS trg_invoice_records_immutable_delete
                BEFORE DELETE ON invoice_records
                FOR EACH ROW
                WHEN OLD.status = 'PROCESSED'
                BEGIN
                    SELECT RAISE(ABORT, 'LEDGER_IMMUTABILITY_VIOLATION: No se permite eliminar un comprobante PROCESSED');
                END;
                """
            )
        )
        conn.commit()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Generador que provee sesiones de base de datos seguras."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_db_integrity(db_engine: Engine) -> None:
    """Ejecuta chequeo de integridad en SQLite y aborta si está corrupta."""
    with db_engine.connect() as conn:
        result = conn.execute(text("PRAGMA integrity_check")).scalar()
        if result != "ok":
            logger.critical("falla_integridad_bd", details=result)
            raise RuntimeError(f"Base de datos corrupta: {result}")


def verify_schema_version(db_engine: Engine) -> None:
    """Verifica que la versión de esquema de base de datos coincida con el código."""
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
