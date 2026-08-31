"""
SQLAlchemy models for CajaClara.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
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
    # Datos del adjunto (indexado para acelerar deduplicación O(log N))
    attachment_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    attachment_hash: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    attachment_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Inteligencia Contable / Datos de Factura Fiscal
    document_type: Mapped[str | None] = mapped_column(String(10), nullable=True, default="01")  # 01=Factura, 03=Boleta, 07=NC, 08=ND
    issuer_id: Mapped[str | None] = mapped_column(String(50), nullable=True)  # RUC / NIT
    issuer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Razón Social
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Serie y Folio (ej. F001-000123)
    issue_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True, default="PEN")
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    detraction_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    detraction_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    cdr_status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # ACCEPTED / REJECTED

    # Referencia Contable para Notas de Crédito (07) y Débito (08)
    reference_document_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    reference_invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    discrepancy_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    discrepancy_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Estado y tracking
    status: Mapped[str] = mapped_column(String, nullable=False, default="PENDING", index=True)
    error_detail: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (CheckConstraint("document_type IS NULL OR document_type IN ('01', '03', '07', '08')", name="chk_valid_document_type"),)


class OutboxEvent(Base):
    """Modelo de Eventos para el patrón Transactional Outbox (Cero Dual-Write)."""

    __tablename__ = "outbox_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), index=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (Index("ix_outbox_events_dispatch", "status", "next_retry_at", "id"),)
