from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from caja_clara.database import setup_sqlite_immutability_triggers
from caja_clara.imap_client import IMAPClient
from caja_clara.mailbox_pool import MailboxConfig, MailboxPoolOrchestrator, MailboxWorker
from caja_clara.models import Base, InvoiceRecord
from tests.fakes.fake_imap import FakeMailBox


class DummyAttachment:
    def __init__(self, filename: str, payload: bytes):
        self.filename = filename
        self.payload = payload


class DummyMailMessage:
    def __init__(self, uid: str, from_: str, subject: str, attachments: list[DummyAttachment]):
        self.uid = uid
        self.from_ = from_
        self.subject = subject
        self.attachments = attachments
        self.headers = {"message-id": (f"<{uid}@domain.com>",)}
        self.date = datetime.now(UTC)


@pytest.fixture
def pool_db():
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


def test_mailbox_worker_process_cycle(pool_db, monkeypatch):
    """Valida que un worker procese un correo XML con éxito y persista en base de datos."""
    fake_mb = FakeMailBox(host="imap.test.com")
    monkeypatch.setattr("caja_clara.imap_client.MailBox", lambda *args, **kwargs: fake_mb)

    sample_xml = b"""<?xml version="1.0" encoding="ISO-8859-1"?>
    <Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">
        <ID>F001-00012345</ID>
        <IssueDate>2026-08-31</IssueDate>
        <DocumentCurrencyCode>PEN</DocumentCurrencyCode>
        <LegalMonetaryTotal><PayableAmount>1180.00</PayableAmount></LegalMonetaryTotal>
    </Invoice>"""

    msg = DummyMailMessage(
        uid="1001",
        from_="proveedor@empresa.com",
        subject="Factura F001-12345",
        attachments=[DummyAttachment("F001-12345.xml", sample_xml)],
    )
    fake_mb.messages_store = [msg]

    config = MailboxConfig(
        account_id="facturas@cajaclara.com",
        host="imap.test.com",
        port=993,
        user="facturas@cajaclara.com",
        password="secret_password",
        poll_interval=1,
    )

    client = IMAPClient(user="facturas@cajaclara.com", password="secret_password")
    worker = MailboxWorker(mailbox_config=config, db_factory=pool_db, client=client)

    count = worker.process_cycle()
    assert count == 1
    assert ("1001", ["\\Seen"], True) in fake_mb.flagged_uids

    with pool_db() as session:
        record = session.query(InvoiceRecord).filter(InvoiceRecord.invoice_number == "F001-00012345").first()
        assert record is not None
        assert record.mailbox_account == "facturas@cajaclara.com"
        assert record.total_amount == Decimal("1180.00")
        assert record.status == "PROCESSED"


def test_mailbox_worker_fault_isolation(pool_db, monkeypatch):
    """Valida que si un buzón falla por credenciales inválidas, su estado pase a error sin crashear."""
    fake_mb = FakeMailBox(host="imap.fail.com")
    fake_mb.fail_login = True
    monkeypatch.setattr("caja_clara.imap_client.MailBox", lambda *args, **kwargs: fake_mb)

    config = MailboxConfig(
        account_id="fallido@cajaclara.local",
        host="imap.fail.com",
        port=993,
        user="fallido@cajaclara.local",
        password="wrong_password",
        poll_interval=1,
    )

    client = IMAPClient(user="fallido@cajaclara.local", password="wrong_password")
    worker = MailboxWorker(mailbox_config=config, db_factory=pool_db, client=client)

    with pytest.raises(RuntimeError):
        worker.process_cycle()


def test_mailbox_pool_orchestrator_lifecycle(pool_db):
    """Valida el ciclo de vida de arranque y parada del orquestador multi-buzón."""
    configs = [
        MailboxConfig("box1@empresa.com", "imap.box1.com", 993, "box1@empresa.com", "pass1"),
        MailboxConfig("box2@empresa.com", "imap.box2.com", 993, "box2@empresa.com", "pass2"),
    ]

    orchestrator = MailboxPoolOrchestrator(mailboxes=configs, db_factory=pool_db)
    assert len(orchestrator.mailboxes) == 2
    # Iniciar y detener rápidamente sin bloquear
    orchestrator.start()
    status = orchestrator.get_status()
    assert "box1@empresa.com" in status
    assert "box2@empresa.com" in status
    orchestrator.stop()
