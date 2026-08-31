from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from caja_clara.database import setup_sqlite_immutability_triggers
from caja_clara.models import Base, InvoiceRecord


@pytest.fixture
def ledger_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    setup_sqlite_immutability_triggers(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    yield session_factory
    Base.metadata.drop_all(bind=engine)


def test_processed_invoice_cannot_be_updated(ledger_db):
    """Valida que un comprobante en estado PROCESSED no pueda ser modificado (Trigger BEFORE UPDATE)."""
    with ledger_db() as session:
        record = InvoiceRecord(
            message_id="<msg-imm-001@cajaclara.local>",
            imap_uid=101,
            mailbox_account="facturas@empresa.com",
            sender_email="proveedor@sunat.gob.pe",
            received_date=datetime.now(UTC),
            document_type="01",
            invoice_number="F001-00009999",
            total_amount=Decimal("1180.00"),
            status="PROCESSED",
        )
        session.add(record)
        session.commit()
        record_id = record.id

    with ledger_db() as session:
        rec = session.query(InvoiceRecord).filter(InvoiceRecord.id == record_id).first()
        rec.total_amount = Decimal("5000.00")  # Intento de mutación arbitraria

        with pytest.raises(IntegrityError) as exc_info:
            session.commit()
        assert "LEDGER_IMMUTABILITY_VIOLATION" in str(exc_info.value)


def test_processed_invoice_cannot_be_deleted(ledger_db):
    """Valida que un comprobante en estado PROCESSED no pueda ser eliminado (Trigger BEFORE DELETE)."""
    with ledger_db() as session:
        record = InvoiceRecord(
            message_id="<msg-imm-002@cajaclara.local>",
            imap_uid=102,
            mailbox_account="facturas@empresa.com",
            sender_email="proveedor@sunat.gob.pe",
            received_date=datetime.now(UTC),
            document_type="01",
            invoice_number="F001-00008888",
            total_amount=Decimal("250.00"),
            status="PROCESSED",
        )
        session.add(record)
        session.commit()
        record_id = record.id

    with ledger_db() as session:
        rec = session.query(InvoiceRecord).filter(InvoiceRecord.id == record_id).first()
        session.delete(rec)

        with pytest.raises(IntegrityError) as exc_info:
            session.commit()
        assert "LEDGER_IMMUTABILITY_VIOLATION" in str(exc_info.value)


def test_pending_invoice_can_transition_to_processed(ledger_db):
    """Valida que un comprobante en estado PENDING sí pueda transicionar legítimamente a PROCESSED."""
    with ledger_db() as session:
        record = InvoiceRecord(
            message_id="<msg-imm-003@cajaclara.local>",
            imap_uid=103,
            mailbox_account="facturas@empresa.com",
            sender_email="proveedor@sunat.gob.pe",
            received_date=datetime.now(UTC),
            document_type="01",
            invoice_number="F001-00007777",
            total_amount=Decimal("300.00"),
            status="PENDING",
        )
        session.add(record)
        session.commit()
        record_id = record.id

    with ledger_db() as session:
        rec = session.query(InvoiceRecord).filter(InvoiceRecord.id == record_id).first()
        rec.status = "PROCESSED"
        rec.cdr_status = "ACCEPTED"
        session.commit()

    with ledger_db() as session:
        rec = session.query(InvoiceRecord).filter(InvoiceRecord.id == record_id).first()
        assert rec.status == "PROCESSED"
        assert rec.cdr_status == "ACCEPTED"


def test_invalid_document_type_rejected_by_check_constraint(ledger_db):
    """Valida que tipos de comprobante ajenos a 01, 03, 07, 08 sean rechazados por CheckConstraint."""
    with ledger_db() as session:
        record = InvoiceRecord(
            message_id="<msg-imm-004@cajaclara.local>",
            imap_uid=104,
            mailbox_account="facturas@empresa.com",
            sender_email="proveedor@sunat.gob.pe",
            received_date=datetime.now(UTC),
            document_type="99",  # Tipo inválido
            status="PENDING",
        )
        session.add(record)
        with pytest.raises(IntegrityError):
            session.commit()
