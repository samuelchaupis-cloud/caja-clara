"""
Validation schemas for data extracted from emails.
"""
import os
import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from caja_clara.constants import (
    ALLOWED_ATTACHMENT_EXTENSIONS,
    MAX_ATTACHMENT_SIZE_BYTES,
    MAX_FILENAME_LENGTH,
    MAX_SUBJECT_LENGTH,
)

class InvoiceExtraction(BaseModel):
    """Esquema de salida estructurada (Structured Output) para que el LLM devuelva JSON puro."""
    issuer_id: str | None = Field(default=None, description="RUC, NIT, RFC o Identificador Fiscal del emisor de la factura. Solo los números.")
    issuer_name: str | None = Field(default=None, description="Razón social o nombre de la empresa que emite la factura.")
    invoice_number: str | None = Field(default=None, description="Número de la factura, comprobante o folio (ejemplo: F001-00123).")
    issue_date: str | None = Field(default=None, description="Fecha de emisión en formato YYYY-MM-DD.")
    currency: str | None = Field(default=None, description="Código de moneda de 3 letras (ejemplo: PEN, USD, MXN).")
    subtotal: float | None = Field(default=None, description="Monto neto antes de impuestos. Solo número float.")
    tax_amount: float | None = Field(default=None, description="Monto de los impuestos (IGV, IVA, etc). Solo número float.")
    total_amount: float | None = Field(default=None, description="Monto total a pagar incluyendo impuestos. Solo número float.")

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
    
    # Fase 3: Variables Financieras (opcionales, se llenan si el extractor las encuentra)
    issuer_id: str | None = None
    issuer_name: str | None = None
    invoice_number: str | None = None
    issue_date: datetime | None = None
    currency: str | None = Field(default=None, max_length=10)
    subtotal: float | None = None
    tax_amount: float | None = None
    total_amount: float | None = None

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
            # Remove null bytes which can break databases
            v = v.replace('\x00', '')
            return v[:MAX_SUBJECT_LENGTH]
        return v

    @field_validator("attachment_filename")
    @classmethod
    def sanitize_filename(cls, v: str | None) -> str | None:
        if not v:
            return None
        
        # Prevent path traversal
        base = os.path.basename(v)
        
        # Regex whitelist: only alphanumeric, dash, dot, underscore
        sanitized = re.sub(r'[^\w\-.]', '_', base)
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
