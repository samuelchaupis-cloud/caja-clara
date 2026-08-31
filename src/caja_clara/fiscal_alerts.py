"""
Módulo de evaluación de alertas fiscales y construcción de esquemas canónicos ERP.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from caja_clara.models import InvoiceRecord, OutboxEvent


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

    subtotal_f = float(record.subtotal) if record.subtotal is not None else None
    tax_f = float(record.tax_amount) if record.tax_amount is not None else None
    total_f = float(record.total_amount) if record.total_amount is not None else None
    detraction_amt_f = float(record.detraction_amount) if record.detraction_amount is not None else None
    detraction_rate_f = float(record.detraction_rate) if record.detraction_rate is not None else None

    is_detraction = record.detraction_amount is not None or record.detraction_rate is not None
    net_payable = None
    if total_f is not None and detraction_amt_f is not None:
        net_payable = round(total_f - detraction_amt_f, 2)

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
        },
        "party": {
            "issuer_ruc": record.issuer_id,
            "issuer_legal_name": record.issuer_name,
            "sender_email": record.sender_email,
        },
        "accounting": {
            "currency_code": record.currency or "PEN",
            "subtotal": subtotal_f,
            "tax_amount": tax_f,
            "total_amount": total_f,
            "detraction": {
                "is_subject": is_detraction,
                "rate_percentage": detraction_rate_f,
                "amount": detraction_amt_f,
                "net_payable_to_vendor": net_payable,
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
            "total_amount": float(record.total_amount) if record.total_amount is not None else None,
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
                    "total_amount": float(record.total_amount),
                    "detraction_rate": float(record.detraction_rate),
                    "expected_detraction": float(expected_detraction),
                    "declared_detraction": float(record.detraction_amount),
                    "discrepancy_amount": float(discrepancy),
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
