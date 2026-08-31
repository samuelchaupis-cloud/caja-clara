from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from caja_clara.schemas import EmailExtract


def get_valid_payload():
    return {
        "message_id": "<abc@test.com>",
        "imap_uid": 123,
        "mailbox_account": "test@test.com",
        "sender_email": "provider@test.com",
        "received_date": datetime.now(UTC),
        "subject": "Factura 123",
        "has_attachments": True,
        "attachment_filename": "factura.pdf",
        "attachment_size_bytes": 1024,
    }


def test_valid_email_extract():
    """Test standard valid extraction."""
    payload = get_valid_payload()
    extract = EmailExtract(**payload)
    assert extract.sender_email == "provider@test.com"


def test_missing_from_header():
    """Test validation fails if sender is empty."""
    payload = get_valid_payload()
    payload["sender_email"] = "   "
    with pytest.raises(ValidationError, match="Missing From header"):
        EmailExtract(**payload)


def test_subject_null_bytes_removal():
    """Test null bytes are stripped from subject."""
    payload = get_valid_payload()
    payload["subject"] = "Factura\x00_Secreta"
    extract = EmailExtract(**payload)
    assert extract.subject == "Factura_Secreta"


def test_path_traversal_prevention():
    """Test filenames are sanitized against path traversal."""
    payload = get_valid_payload()
    payload["attachment_filename"] = "../../etc/passwd.pdf"
    extract = EmailExtract(**payload)
    # The regex _ also acts as replacement, but basename handles the path part.
    assert extract.attachment_filename == "passwd.pdf"

    payload["attachment_filename"] = "factura(1).pdf"
    extract2 = EmailExtract(**payload)
    assert extract2.attachment_filename == "factura_1_.pdf"


def test_forbidden_extension():
    """Test executable or dangerous extensions are rejected."""
    payload = get_valid_payload()
    payload["attachment_filename"] = "virus.exe"
    with pytest.raises(ValidationError, match="not allowed"):
        EmailExtract(**payload)


def test_size_exceeds_maximum():
    """Test size limits on attachments."""
    payload = get_valid_payload()
    payload["attachment_size_bytes"] = 50 * 1024 * 1024  # 50 MB
    with pytest.raises(ValidationError, match="exceeds maximum"):
        EmailExtract(**payload)
