"""
Validation schemas for data extracted from emails.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from caja_clara.constants import (
    ALLOWED_ATTACHMENT_EXTENSIONS,
    MAX_ATTACHMENT_SIZE_BYTES,
    MAX_FILENAME_LENGTH,
    MAX_SUBJECT_LENGTH,
)


class InvoiceExtraction(BaseModel):
    """Esquema de salida estructurada para extracción de facturas (UBL o LLM)."""

    document_type: str | None = Field(default="01", description="Tipo de comprobante: 01 Factura, 03 Boleta, 07 Nota Crédito, 08 Nota Débito.")
    issuer_id: str | None = Field(default=None, description="RUC, NIT, RFC o Identificador Fiscal del emisor de la factura. Solo los números.")
    issuer_name: str | None = Field(default=None, description="Razón social o nombre de la empresa que emite la factura.")
    invoice_number: str | None = Field(default=None, description="Número de la factura, comprobante o folio (ejemplo: F001-00123).")
    issue_date: str | None = Field(default=None, description="Fecha de emisión en formato YYYY-MM-DD.")
    currency: str | None = Field(default="PEN", description="Código de moneda de 3 letras (ejemplo: PEN, USD, EUR).")
    subtotal: Decimal | None = Field(default=None, description="Monto neto antes de impuestos.")
    tax_amount: Decimal | None = Field(default=None, description="Monto de los impuestos (IGV, IVA, etc).")
    total_amount: Decimal | None = Field(default=None, description="Monto total a pagar incluyendo impuestos.")
    detraction_amount: Decimal | None = Field(default=None, description="Monto de detracción SPOT si aplica.")
    detraction_rate: Decimal | None = Field(default=None, description="Porcentaje de detracción SPOT si aplica.")
    cdr_status: str | None = Field(default=None, description="Estado de validación CDR de SUNAT (ej. ACCEPTED).")


class EmailExtract(BaseModel):
    """Schema for validating and sanitizing extracted email data before database insertion."""

    message_id: str
    imap_uid: int
    mailbox_account: EmailStr
    sender_email: str
    received_date: datetime
    subject: str | None = None
    has_attachments: bool = False
    attachment_filename: str | None = None
    attachment_hash: str | None = None
    attachment_size_bytes: int | None = None

    # Variables Fiscales y Financieras
    document_type: str | None = "01"
    issuer_id: str | None = None
    issuer_name: str | None = None
    invoice_number: str | None = None
    issue_date: datetime | None = None
    currency: str | None = Field(default="PEN", max_length=10)
    subtotal: Decimal | None = None
    tax_amount: Decimal | None = None
    total_amount: Decimal | None = None
    detraction_amount: Decimal | None = None
    detraction_rate: Decimal | None = None
    cdr_status: str | None = None

    @field_validator("sender_email", mode="before")
    @classmethod
    def validate_sender(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Missing From header")
        return v.strip()

    @field_validator("subject")
    @classmethod
    def sanitize_subject(cls, v: str | None) -> str | None:
        if v:
            v = v.replace("\x00", "")
            return v[:MAX_SUBJECT_LENGTH]
        return v

    @field_validator("attachment_filename")
    @classmethod
    def sanitize_filename(cls, v: str | None) -> str | None:
        if not v:
            return None

        base = os.path.basename(v)
        sanitized = re.sub(r"[^\w\-.]", "_", base)
        sanitized = sanitized[:MAX_FILENAME_LENGTH]

        _, ext = os.path.splitext(sanitized)
        if ext.lower() not in ALLOWED_ATTACHMENT_EXTENSIONS:
            raise ValueError(f"Extension '{ext}' is not allowed.")

        return sanitized

    @field_validator("attachment_size_bytes")
    @classmethod
    def validate_size(cls, v: int | None) -> int | None:
        if v is not None and v > MAX_ATTACHMENT_SIZE_BYTES:
            raise ValueError(f"Attachment exceeds maximum allowed size ({MAX_ATTACHMENT_SIZE_BYTES} bytes)")
        return v


class OutboxEventCreate(BaseModel):
    """Esquema de creación de un evento outbox."""

    event_type: str
    payload: dict[str, Any]


class OutboxEventResponse(BaseModel):
    """Esquema de serialización de evento outbox."""

    id: int
    event_type: str
    payload: str
    status: str
    retry_count: int
    created_at: datetime
    processed_at: datetime | None = None
    error_detail: str | None = None

    model_config = ConfigDict(from_attributes=True)
