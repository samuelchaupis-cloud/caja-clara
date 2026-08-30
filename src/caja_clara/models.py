"""
SQLAlchemy models for CajaClara.
"""
from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class InvoiceRecord(Base):
    __tablename__ = "invoice_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String, unique=True, nullable=False)
    imap_uid = Column(Integer, nullable=False)
    mailbox_account = Column(String, nullable=False)
    sender_email = Column(String, nullable=False, index=True)
    received_date = Column(DateTime, nullable=False, index=True)
    subject = Column(String, nullable=True)
    body_preview = Column(String, nullable=True)
    has_attachments = Column(Boolean, nullable=False, default=False)
    attachment_filename = Column(String, nullable=True)
    attachment_hash = Column(String, nullable=True)
    attachment_size_bytes = Column(Integer, nullable=True)
    status = Column(String, nullable=False, default="PENDING", index=True)
    error_detail = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
