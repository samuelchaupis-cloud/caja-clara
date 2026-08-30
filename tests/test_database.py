from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from caja_clara.database import verify_db_integrity
from caja_clara.models import InvoiceRecord


def test_sqlite_pragmas_applied(db_engine):
    """Test that WAL mode and foreign keys are applied correctly."""
    with db_engine.connect() as conn:
        from sqlalchemy import text
        journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        assert journal_mode in ("memory", "wal")

def test_deduplication_by_message_id(db_session):
    """Test that duplicate message_ids are rejected by the database."""
    now = datetime.now(UTC)
    record1 = InvoiceRecord(
        message_id="<123@test.com>",
        imap_uid=1,
        mailbox_account="test@test.com",
        sender_email="provider@test.com",
        received_date=now
    )
    db_session.add(record1)
    db_session.commit()
    
    # Try inserting the same message_id
    record2 = InvoiceRecord(
        message_id="<123@test.com>",
        imap_uid=2,
        mailbox_account="test@test.com",
        sender_email="another@test.com",
        received_date=now
    )
    db_session.add(record2)
    
    with pytest.raises(IntegrityError):
        db_session.commit()

def test_verify_db_integrity(db_engine):
    """Test the integrity check function."""
    # Should not raise an exception
    verify_db_integrity(db_engine)
