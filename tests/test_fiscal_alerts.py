from datetime import UTC, datetime
from decimal import Decimal

from caja_clara.fiscal_alerts import (
    build_canonical_erp_payload,
    evaluate_fiscal_alerts,
)
from caja_clara.models import InvoiceRecord, OutboxEvent


def test_build_canonical_erp_payload():
    """Valida la generación del payload normalizado v1 para integración con ERPs."""
    record = InvoiceRecord(
        id=1,
        message_id="<msg-001@proveedor.pe>",
        imap_uid=101,
        mailbox_account="facturas@empresa.com",
        sender_email="facturacion@proveedor.pe",
        received_date=datetime.now(UTC),
        attachment_hash="a1b2c3d4e5f6",
        document_type="01",
        invoice_number="F001-00045678",
        issuer_id="20601234567",
        issuer_name="PROVEEDOR MODELO S.A.C.",
        issue_date=datetime(2026, 8, 30, tzinfo=UTC),
        currency="PEN",
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        detraction_amount=Decimal("141.60"),
        detraction_rate=Decimal("12.00"),
        cdr_status="ACCEPTED",
        status="PROCESSED",
    )

    payload = build_canonical_erp_payload(record)

    assert payload["spec_version"] == "1.0"
    assert payload["event_type"] == "invoice.processed"
    assert payload["document"]["sunat_type"] == "01"
    assert payload["document"]["full_number"] == "F001-00045678"
    assert payload["party"]["issuer_ruc"] == "20601234567"
    assert payload["accounting"]["total_amount"] == "1180.00"
    assert payload["accounting"]["detraction"]["amount"] == "141.60"
    assert payload["accounting"]["detraction"]["net_payable_to_vendor"] == "1038.40"
    assert payload["compliance"]["cdr_status"] == "ACCEPTED"


def test_evaluate_fiscal_alerts_cdr_rejected():
    """Valida la generación de alerta crítica cuando el CDR de SUNAT es rechazado."""
    record = InvoiceRecord(
        id=2,
        message_id="<msg-rej@proveedor.pe>",
        imap_uid=102,
        mailbox_account="facturas@empresa.com",
        sender_email="facturacion@proveedor.pe",
        received_date=datetime.now(UTC),
        document_type="01",
        invoice_number="F001-00099999",
        issuer_id="20609999999",
        issuer_name="EMPRESA OBSERVADA S.A.C.",
        issue_date=datetime(2026, 8, 30, tzinfo=UTC),
        currency="PEN",
        total_amount=Decimal("2500.00"),
        cdr_status="REJECTED",
        error_detail="Codigo 2324: El RUC del emisor no se encuentra activo",
    )

    alerts = evaluate_fiscal_alerts(record)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.event_type == "fiscal.alert.cdr_rejected"
    assert alert.status == "PENDING"
    assert "2324" in alert.payload or "REJECTED" in alert.payload


def test_evaluate_fiscal_alerts_spot_discrepancy():
    """Valida la detección de discrepancia en monto de detracción SPOT."""
    record = InvoiceRecord(
        id=3,
        message_id="<msg-spot@proveedor.pe>",
        imap_uid=103,
        mailbox_account="facturas@empresa.com",
        sender_email="servicios@proveedor.pe",
        received_date=datetime.now(UTC),
        document_type="01",
        invoice_number="F001-00011111",
        issuer_id="20601111111",
        issuer_name="SERVICIOS GENERALES S.A.C.",
        issue_date=datetime(2026, 8, 30, tzinfo=UTC),
        currency="PEN",
        total_amount=Decimal("1000.00"),
        detraction_rate=Decimal("12.00"),
        # Debería ser 120.00, pero declararon 100.00 (Discrepancia de 20.00)
        detraction_amount=Decimal("100.00"),
        cdr_status="ACCEPTED",
    )

    alerts = evaluate_fiscal_alerts(record)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.event_type == "fiscal.alert.spot_discrepancy"
    assert "discrepancia" in alert.payload.lower() or "expected" in alert.payload.lower()


def test_outbox_event_next_retry_at_persistence(db_session):
    """Valida que OutboxEvent persista next_retry_at en base de datos real."""
    future_time = datetime(2026, 8, 31, 20, 0, 0, tzinfo=UTC)
    event = OutboxEvent(
        event_type="invoice.processed",
        payload='{"test": 1}',
        status="PENDING",
        next_retry_at=future_time,
    )
    db_session.add(event)
    db_session.commit()

    retrieved = db_session.query(OutboxEvent).filter(OutboxEvent.id == event.id).first()
    assert retrieved is not None
    assert retrieved.next_retry_at is not None
    assert retrieved.status == "PENDING"
