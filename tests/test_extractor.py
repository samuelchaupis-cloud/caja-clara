from datetime import UTC, datetime
from unittest.mock import MagicMock

from caja_clara.constants import MAX_ATTACHMENT_SIZE_BYTES
from caja_clara.extractor import extract_email_data, hash_attachment


def test_hash_attachment():
    """Test that hashing is stable and correct."""
    payload = b"dummy content"
    hash_val = hash_attachment(payload)
    assert hash_val == "bf0ecbdb9b814248d086c9b69cf26182d9d4138f2ad3d0637c4555fc8cbf68e5"


def test_extract_valid_email():
    """Test standard valid extraction from a mocked MailMessage."""
    mock_msg = MagicMock()
    mock_msg.uid = "100"
    mock_msg.headers = {"message-id": ["<test@msg>"]}
    mock_msg.from_ = "provider@test.com"
    mock_msg.date = datetime.now(UTC)
    mock_msg.subject = "Invoice"

    mock_att = MagicMock()
    mock_att.filename = "invoice.pdf"
    mock_att.payload = b"pdf_data"
    mock_msg.attachments = [mock_att]

    extract, err = extract_email_data(mock_msg, "test@test.com")

    assert err is None
    assert extract is not None
    assert extract.sender_email == "provider@test.com"
    assert extract.has_attachments is True
    assert extract.attachment_size_bytes == 8


def test_extract_xml_and_zip_attachments():
    """Test extraction with XML and ZIP attachments."""
    mock_msg = MagicMock()
    mock_msg.uid = "102"
    mock_msg.headers = {"message-id": ["<xml_msg@test.com>"]}
    mock_msg.from_ = "proveedor@xml.com"
    mock_msg.date = datetime.now(UTC)
    mock_msg.subject = "Factura XML"

    mock_att_xml = MagicMock()
    mock_att_xml.filename = "factura.xml"
    mock_att_xml.payload = b"<Invoice><ID>F001-1</ID></Invoice>"
    mock_msg.attachments = [mock_att_xml]

    extract, err = extract_email_data(mock_msg, "test@test.com")
    assert err is None
    assert extract is not None
    assert extract.attachment_filename == "factura.xml"


def test_extract_oversized_attachment():
    """Test rejection of attachments exceeding size limit."""
    mock_msg = MagicMock()
    mock_msg.uid = "103"
    mock_msg.headers = {"message-id": ["<big@test.com>"]}
    mock_msg.from_ = "big@test.com"
    mock_msg.date = datetime.now(UTC)
    mock_msg.subject = "Big Attachment"

    mock_att = MagicMock()
    mock_att.filename = "huge.pdf"
    mock_att.payload = b"X" * (MAX_ATTACHMENT_SIZE_BYTES + 100)
    mock_msg.attachments = [mock_att]

    extract, err = extract_email_data(mock_msg, "test@test.com")
    assert extract is None
    assert err is not None
    assert "excede el límite" in err


def test_extract_invalid_email_no_sender():
    """Test that extractor gracefully handles and reports invalid emails."""
    mock_msg = MagicMock()
    mock_msg.uid = "101"
    mock_msg.headers = {"message-id": ["<test@msg>"]}
    mock_msg.from_ = ""  # Invalid
    mock_msg.date = datetime.now(UTC)
    mock_msg.subject = "Invoice"
    mock_msg.attachments = []

    extract, err = extract_email_data(mock_msg, "test@test.com")

    assert extract is None
    assert err is not None
    assert "Missing From header" in err
