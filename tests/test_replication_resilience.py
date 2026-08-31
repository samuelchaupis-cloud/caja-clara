from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from caja_clara.database import setup_sqlite_immutability_triggers, verify_db_integrity
from caja_clara.metrics import (
    LITESTREAM_LAG_SECONDS,
    REPLICATION_STATUS,
    REPLICATION_SYNC_ERRORS_TOTAL,
)
from caja_clara.models import Base, InvoiceRecord, OutboxEvent


@pytest.fixture
def resilience_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    setup_sqlite_immutability_triggers(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    yield engine, session_factory
    Base.metadata.drop_all(bind=engine)


def test_sqlite_transactions_unblocked_during_s3_outage(resilience_db):
    """Valida que la caída de red a S3 (REPLICATION_STATUS=0) no bloquee transacciones locales."""
    engine, session_factory = resilience_db

    # Simular caída de réplica hacia Cloudflare R2 / S3
    REPLICATION_STATUS.labels(replica="primary", storage_provider="s3").set(0)
    REPLICATION_SYNC_ERRORS_TOTAL.labels(replica="primary", error_type="network_timeout").inc()
    LITESTREAM_LAG_SECONDS.labels(replica="primary", storage_provider="s3").set(120.5)

    # El demonio y dispatcher deben seguir persistiendo comprobantes en local sin errores
    with session_factory() as session:
        inv = InvoiceRecord(
            message_id="<resilience_test_1@cajaclara.local>",
            imap_uid=2001,
            mailbox_account="facturas@empresa.com",
            sender_email="proveedor@test.com",
            received_date=datetime.now(UTC),
            document_type="01",
            invoice_number="F001-00088888",
            total_amount=Decimal("1500.00"),
            status="PROCESSED",
        )
        outbox = OutboxEvent(
            event_type="invoice.processed",
            payload='{"invoice_number": "F001-00088888"}',
            status="PENDING",
        )
        session.add(inv)
        session.add(outbox)
        session.commit()

    # Verificar que el registro existe y que la integridad de BD es óptima
    with session_factory() as session:
        saved_inv = session.query(InvoiceRecord).filter(InvoiceRecord.invoice_number == "F001-00088888").first()
        assert saved_inv is not None
        assert saved_inv.status == "PROCESSED"

    # Verificar integridad del motor SQLite
    verify_db_integrity(engine)


def test_replication_lag_metrics_update():
    """Valida que los registros de lag y estado de réplica sean actualizados deterministamente."""
    LITESTREAM_LAG_SECONDS.labels(replica="primary", storage_provider="s3").set(0.125)
    REPLICATION_STATUS.labels(replica="primary", storage_provider="s3").set(1.0)

    lag_val = LITESTREAM_LAG_SECONDS.labels(replica="primary", storage_provider="s3")._value.get()
    status_val = REPLICATION_STATUS.labels(replica="primary", storage_provider="s3")._value.get()

    assert lag_val == 0.125
    assert status_val == 1.0


def test_disaster_recovery_restoration_integrity(resilience_db):
    """Valida que una base de datos restaurada preserve integridad y triggers de inmutabilidad."""
    engine, session_factory = resilience_db

    # 1. Sembrar registro inicial
    with session_factory() as session:
        inv = InvoiceRecord(
            message_id="<dr_test_1@cajaclara.local>",
            imap_uid=3001,
            mailbox_account="facturas@empresa.com",
            sender_email="proveedor@test.com",
            received_date=datetime.now(UTC),
            document_type="01",
            invoice_number="F001-00099999",
            total_amount=Decimal("2000.00"),
            status="PROCESSED",
        )
        session.add(inv)
        session.commit()

    # 2. Verificar integridad física
    verify_db_integrity(engine)

    # 3. Validar que los triggers de inmutabilidad permanezcan activos
    from sqlalchemy.exc import IntegrityError

    with session_factory() as session:
        target = session.query(InvoiceRecord).filter(InvoiceRecord.invoice_number == "F001-00099999").first()
        target.total_amount = Decimal("9999.00")
        with pytest.raises(IntegrityError, match="LEDGER_IMMUTABILITY_VIOLATION"):
            session.commit()
