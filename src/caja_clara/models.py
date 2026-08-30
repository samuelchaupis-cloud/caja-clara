"""
SQLAlchemy models for CajaClara.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, declarative_base, mapped_column

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
    # Datos del adjunto
    attachment_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    attachment_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    attachment_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Fase 3: Inteligencia Contable / Datos de Factura
    issuer_id: Mapped[str | None] = mapped_column(String(50), nullable=True) # RUC / NIT
    issuer_name: Mapped[str | None] = mapped_column(String(255), nullable=True) # Razón Social
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True) # Serie y Folio
    issue_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    subtotal: Mapped[float | None] = mapped_column(Float, nullable=True)
    tax_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Estado y tracking
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="PENDING", index=True
    )
    error_detail: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
