"""
Módulo de evaluación de alertas fiscales y construcción de esquemas canónicos ERP.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from caja_clara.models import InvoiceRecord, OutboxEvent


def _format_decimal(val: Decimal | None) -> str | None:
    """Formatea un Decimal a string con 2 decimales sin pérdida de precisión de coma flotante."""
    if val is None:
        return None
    return f"{val:.2f}"


def build_canonical_erp_payload(record: InvoiceRecord) -> dict[str, Any]:
    """Construye un payload JSON normalizado (Esquema Canónico ERP v1).

    Compatible con Odoo, SAP Business One, Siigo y Concar.
    """
    serie = None
    number = None
    if record.invoice_number and "-" in record.invoice_number:
        parts = record.invoice_number.split("-", 1)
        serie = parts[0].strip()
        number = parts[1].strip()
    elif record.invoice_number:
        number = record.invoice_number.strip()

    is_detraction = record.detraction_amount is not None or record.detraction_rate is not None
    net_payable: Decimal | None = None
    if record.total_amount is not None and record.detraction_amount is not None:
        net_payable = (record.total_amount - record.detraction_amount).quantize(Decimal("0.01"))

    return {
        "spec_version": "1.0",
        "event_type": "invoice.processed",
        "record_id": record.id,
        "origin": {
            "mailbox": record.mailbox_account,
            "message_id": record.message_id,
            "attachment_hash": record.attachment_hash,
            "received_date": record.received_date.isoformat() if record.received_date else None,
        },
        "document": {
            "sunat_type": record.document_type or "01",
            "serie": serie,
            "number": number,
            "full_number": record.invoice_number,
            "issue_date": record.issue_date.strftime("%Y-%m-%d") if record.issue_date else None,
            "currency": record.currency or "PEN",
            "reference_document_type": record.reference_document_type,
            "reference_invoice_number": record.reference_invoice_number,
            "discrepancy_code": record.discrepancy_code,
            "discrepancy_reason": record.discrepancy_reason,
        },
        "party": {
            "issuer_ruc": record.issuer_id,
            "issuer_legal_name": record.issuer_name,
            "sender_email": record.sender_email,
        },
        "accounting": {
            "currency_code": record.currency or "PEN",
            "subtotal": _format_decimal(record.subtotal),
            "tax_amount": _format_decimal(record.tax_amount),
            "total_amount": _format_decimal(record.total_amount),
            "detraction": {
                "is_subject": is_detraction,
                "rate_percentage": _format_decimal(record.detraction_rate),
                "amount": _format_decimal(record.detraction_amount),
                "net_payable_to_vendor": _format_decimal(net_payable),
            },
        },
        "compliance": {
            "cdr_status": record.cdr_status or "UNKNOWN",
            "status": record.status,
        },
    }


def evaluate_fiscal_alerts(record: InvoiceRecord) -> list[OutboxEvent]:
    """Evalúa reglas de compliance fiscal y genera eventos outbox de alerta si detecta anomalías."""
    alerts: list[OutboxEvent] = []

    # Regla 1: Alerta crítica por CDR rechazado por SUNAT
    if record.cdr_status == "REJECTED":
        alert_data = {
            "alert_type": "cdr_rejected",
            "severity": "CRITICAL",
            "invoice_number": record.invoice_number,
            "issuer_id": record.issuer_id,
            "issuer_name": record.issuer_name,
            "error_detail": record.error_detail or "CDR rechazado por la administración tributaria",
            "total_amount": _format_decimal(record.total_amount),
            "currency": record.currency or "PEN",
        }
        alerts.append(
            OutboxEvent(
                event_type="fiscal.alert.cdr_rejected",
                payload=json.dumps(alert_data, default=str),
                status="PENDING",
            )
        )

    # Regla 2: Discrepancia matemática o falta de detracción SPOT
    if record.total_amount is not None and record.detraction_rate is not None:
        expected_detraction = (record.total_amount * (record.detraction_rate / Decimal("100"))).quantize(Decimal("0.01"))
        if record.detraction_amount is not None:
            discrepancy = abs(record.detraction_amount - expected_detraction)
            if discrepancy > Decimal("0.05"):
                alert_data = {
                    "alert_type": "spot_discrepancy",
                    "severity": "HIGH",
                    "invoice_number": record.invoice_number,
                    "issuer_id": record.issuer_id,
                    "total_amount": _format_decimal(record.total_amount),
                    "detraction_rate": _format_decimal(record.detraction_rate),
                    "expected_detraction": _format_decimal(expected_detraction),
                    "declared_detraction": _format_decimal(record.detraction_amount),
                    "discrepancy_amount": _format_decimal(discrepancy),
                    "detail": "Discrepancia aritmética detectada entre tasa SPOT y monto detraído",
                }
                alerts.append(
                    OutboxEvent(
                        event_type="fiscal.alert.spot_discrepancy",
                        payload=json.dumps(alert_data, default=str),
                        status="PENDING",
                    )
                )

    return alerts
