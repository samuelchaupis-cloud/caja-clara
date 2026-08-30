"""
Pipeline for email extraction and data sanitization.
"""
import hashlib
from datetime import UTC, datetime
from typing import Any

from imap_tools import MailMessage
from pydantic import ValidationError

from caja_clara.schemas import EmailExtract


def hash_attachment(payload: bytes) -> str:
    """Generate SHA-256 hash of the attachment content."""
    return hashlib.sha256(payload).hexdigest()

def extract_email_data(msg: MailMessage, mailbox_account: str) -> tuple[EmailExtract | None, str | None]:
    """
    Extract and sanitize email metadata into an EmailExtract schema.
    Returns (EmailExtract, None) on success, or (None, error_detail) if validation fails.
    """
    try:
        # Fallback date to current UTC if it cannot be parsed properly
        received_date = msg.date if msg.date else datetime.now(UTC)
        
        # Attachments processing (only considering the first relevant attachment for now, 
        # or aggregating if needed, but per schema we track one primary attachment).
        has_attachments = len(msg.attachments) > 0
        attachment_filename = None
        attachment_hash = None
        attachment_size_bytes = None
        
        if has_attachments:
            # For simplicity, we process the first attachment in this iteration
            att = msg.attachments[0]
            attachment_filename = att.filename
            attachment_size_bytes = len(att.payload)
            attachment_hash = hash_attachment(att.payload)

        # Build raw dict
        raw_data: dict[str, Any] = {
            "message_id": msg.headers.get("message-id", (f"<{msg.uid}@unknown>",))[0],
            "imap_uid": msg.uid,
            "mailbox_account": mailbox_account,
            "sender_email": msg.from_,
            "received_date": received_date,
            "subject": msg.subject,
            "has_attachments": has_attachments,
            "attachment_filename": attachment_filename,
            "attachment_hash": attachment_hash,
            "attachment_size_bytes": attachment_size_bytes,
        }
        
        validated = EmailExtract(**raw_data)
        return validated, None

    except ValidationError as e:
        # Capture the first validation error message as detail
        err_msg = str(e.errors()[0]["msg"]) if e.errors() else str(e)
        return None, err_msg
    except Exception as e:
        return None, f"Extraction error: {e!s}"
