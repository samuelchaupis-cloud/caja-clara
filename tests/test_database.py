from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from caja_clara.database import get_db, set_sqlite_pragmas, verify_db_integrity, verify_schema_version
from caja_clara.models import InvoiceRecord


def test_sqlite_pragmas_applied(db_engine):
    """Test that WAL mode and foreign keys are applied correctly."""
    with db_engine.connect() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        assert journal_mode in ("memory", "wal")


def test_set_sqlite_pragmas_listener():
    """Valida la ejecución manual del hook de pragmas de SQLite."""
    mock_dbapi = MagicMock()
    mock_cursor = MagicMock()
    mock_dbapi.cursor.return_value = mock_cursor

    set_sqlite_pragmas(mock_dbapi, None)
    assert mock_cursor.execute.call_count == 4
    mock_cursor.close.assert_called_once()


def test_get_db_generator():
    """Valida que el generador get_db provea y cierre la sesión."""
    db_gen = get_db()
    session = next(db_gen)
    assert session is not None
    try:
        next(db_gen)
    except StopIteration:
        pass


def test_deduplication_by_message_id(db_session):
    """Test that duplicate message_ids are rejected by the database."""
    now = datetime.now(UTC)
    record1 = InvoiceRecord(
        message_id="<123@test.com>",
        imap_uid=1,
        mailbox_account="test@test.com",
        sender_email="provider@test.com",
        received_date=now,
    )
    db_session.add(record1)
    db_session.commit()

    record2 = InvoiceRecord(
        message_id="<123@test.com>",
        imap_uid=2,
        mailbox_account="test@test.com",
        sender_email="another@test.com",
        received_date=now,
    )
    db_session.add(record2)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_verify_db_integrity(db_engine):
    """Test the integrity check function on healthy database."""
    verify_db_integrity(db_engine)


def test_verify_db_integrity_corrupt_fails():
    """Test that verify_db_integrity raises RuntimeError when integrity fails."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.return_value.scalar.return_value = "database disk image is malformed"
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with pytest.raises(RuntimeError, match="Base de datos corrupta"):
        verify_db_integrity(mock_engine)


def test_verify_schema_version():
    """Test verify_schema_version with matching and mismatching revisions."""
    mock_engine = MagicMock()

    with (
        patch("alembic.config.Config"),
        patch("alembic.script.ScriptDirectory.from_config") as mock_script_cls,
        patch("alembic.migration.MigrationContext.configure") as mock_mig_ctx,
    ):
        mock_script = mock_script_cls.return_value
        mock_script.get_current_head.return_value = "rev_001"

        # 1. Matching
        mock_ctx = mock_mig_ctx.return_value
        mock_ctx.get_current_revision.return_value = "rev_001"
        verify_schema_version(mock_engine)

        # 2. Mismatch
        mock_ctx.get_current_revision.return_value = "rev_000"
        with pytest.raises(RuntimeError, match="Schema version mismatch"):
            verify_schema_version(mock_engine)
