import os
import signal
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from caja_clara.imap_client import IMAPClient
from caja_clara.main import _handle_signal, process_mailbox, shutdown_event, write_status_file
from caja_clara.models import Base, InvoiceRecord
from tests.fakes.fake_imap import FakeMailBox


@pytest.fixture
def memory_db_session():
    """Crea una base de datos SQLite en memoria real con esquema completo para tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@patch("caja_clara.main.config")
@patch("caja_clara.main.os.replace")
def test_write_status_file(mock_replace, mock_config):
    """Test metrics are written atomically to status.json."""
    mock_config.db_path = "cajaclarad.db"
    try:
        write_status_file()
        mock_replace.assert_called_once()
        assert os.path.exists("status.json.tmp") or os.path.exists("/var/lib/cajaclarad/status.json.tmp")
    finally:
        if os.path.exists("status.json.tmp"):
            os.remove("status.json.tmp")


def test_handle_signal():
    """Test that signals correctly set the shutdown event."""
    shutdown_event.clear()
    _handle_signal(signal.SIGINT, None)
    assert shutdown_event.is_set()


@patch("caja_clara.main.extract_email_data")
def test_process_mailbox_deduplication(mock_extract, memory_db_session):
    """Test that duplicate message_id rolls back the nested transaction and marks seen in IMAP."""
    # Pre-insertar un registro con el mismo message_id
    existing_record = InvoiceRecord(
        message_id="<dup@domain.com>",
        imap_uid=100,
        mailbox_account="test@user.com",
        sender_email="proveedor@empresa.com",
        received_date=datetime.now(UTC),
        status="PROCESSED",
    )
    memory_db_session.add(existing_record)
    memory_db_session.commit()

    mock_client = MagicMock()
    mock_msg = MagicMock()
    mock_msg.uid = "123"
    mock_client.fetch_unseen.return_value = [mock_msg]

    mock_data = MagicMock()
    mock_data.model_dump.return_value = {
        "message_id": "<dup@domain.com>",
        "imap_uid": 123,
        "mailbox_account": "test@user.com",
        "sender_email": "proveedor@empresa.com",
        "received_date": datetime.now(UTC),
        "attachment_hash": None,
        "status": "PENDING",
    }
    mock_data.attachment_hash = None
    mock_extract.return_value = (mock_data, None)

    shutdown_event.clear()
    with patch("caja_clara.main.get_db", return_value=iter([memory_db_session])):
        process_mailbox(mock_client)

    # Verifica que mark_seen fue ejecutado para no reintentar infinitamente
    mock_client.mark_seen.assert_called_once_with("123")


@patch("caja_clara.main.extract_email_data")
def test_process_mailbox_hash_deduplication(mock_extract, memory_db_session):
    """Test that a duplicate hash marks the new record as DUPLICATE in real SQLite DB."""
    # Pre-insertar un registro existente con el mismo hash
    existing_record = InvoiceRecord(
        message_id="<orig@domain.com>",
        imap_uid=101,
        mailbox_account="test@user.com",
        sender_email="proveedor@empresa.com",
        received_date=datetime.now(UTC),
        attachment_hash="hash_duplicado_123",
        status="PROCESSED",
    )
    memory_db_session.add(existing_record)
    memory_db_session.commit()

    mock_client = MagicMock()
    mock_msg = MagicMock()
    mock_msg.uid = "124"
    mock_client.fetch_unseen.return_value = [mock_msg]

    mock_extract_data = MagicMock()
    mock_extract_data.attachment_hash = "hash_duplicado_123"
    mock_extract_data.model_dump.return_value = {
        "message_id": "<new@domain.com>",
        "imap_uid": 124,
        "mailbox_account": "test@user.com",
        "sender_email": "proveedor@empresa.com",
        "received_date": datetime.now(UTC),
        "attachment_hash": "hash_duplicado_123",
    }
    mock_extract.return_value = (mock_extract_data, None)

    shutdown_event.clear()
    with patch("caja_clara.main.get_db", return_value=iter([memory_db_session])):
        process_mailbox(mock_client)

    # Verificar que el registro fue guardado con status DUPLICATE en la base de datos real
    record = memory_db_session.query(InvoiceRecord).filter_by(message_id="<new@domain.com>").first()
    assert record is not None
    assert record.status == "DUPLICATE"
    assert "hash duplicado" in (record.error_detail or "")
    mock_client.mark_seen.assert_called_once_with("124")


@patch("caja_clara.main.time.sleep")
def test_idle_network_disconnect_reconnect(mock_sleep):
    """Req 1: Timeouts en IDLE. Simular desconexión de red en IDLE y verificar que intenta reconectar."""
    client = IMAPClient()
    fake_mb = FakeMailBox("fake")
    fake_mb.idle.should_raise = ConnectionError("Network dropped in IDLE")
    client._mailbox = fake_mb

    result = client.wait_for_new_messages(timeout=1)
    assert result is True
    mock_sleep.assert_called_once_with(1)


def test_idle_blocking_interruption():
    """Req 2: Interrupción Bloqueante. Simular SIGTERM/SIGINT durante el IDLE y probar el apagado seguro."""
    client = IMAPClient()
    fake_mb = FakeMailBox("fake")
    client._mailbox = fake_mb
    fake_mb.idle.should_raise = KeyboardInterrupt("SIGINT simulated by user")

    with pytest.raises(KeyboardInterrupt):
        client.wait_for_new_messages(timeout=1)

    shutdown_event.clear()
    _handle_signal(signal.SIGTERM, None)
    assert shutdown_event.is_set()


@patch("caja_clara.main.extract_email_data")
def test_process_mailbox_transactionality(mock_extract, memory_db_session):
    """Req 3: Transaccionalidad. Si falla el procesamiento (excepción), el flag \\Seen NUNCA se setea."""
    client = IMAPClient()
    fake_mb = FakeMailBox("fake")
    client._mailbox = fake_mb
    fake_mb.is_logged_in = True

    mock_msg = MagicMock()
    mock_msg.uid = "999"
    mock_msg.subject = "Factura de Prueba"

    fake_mb.messages_store = [mock_msg]
    mock_extract.side_effect = RuntimeError("Critical processing failure")

    shutdown_event.clear()

    with patch("caja_clara.main.get_db", return_value=iter([memory_db_session])), patch("caja_clara.main.IMAPClient.connect"):
        process_mailbox(client)

    # Verificamos que la BD real no guardó el registro erróneo
    assert memory_db_session.query(InvoiceRecord).count() == 0
    # Verificamos que en el FakeMailBox NUNCA se marcó como visto
    assert len(fake_mb.flagged_uids) == 0
