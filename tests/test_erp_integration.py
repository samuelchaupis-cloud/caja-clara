from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from caja_clara.crypto import verify_webhook_signature
from caja_clara.dispatcher import OutboxDispatcher
from caja_clara.erp_adapters import (
    transform_to_odoo_invoice,
    transform_to_sap_b1_invoice,
    transform_to_siigo_invoice,
)
from caja_clara.fiscal_alerts import build_canonical_erp_payload
from caja_clara.models import InvoiceRecord, OutboxEvent


@pytest.fixture
def sample_canonical_payload():
    record = InvoiceRecord(
        id=101,
        message_id="<test-erp-001@proveedor.pe>",
        imap_uid=5001,
        mailbox_account="facturas@empresa.com",
        sender_email="facturas@proveedor.pe",
        received_date=datetime.now(UTC),
        document_type="01",
        invoice_number="F001-00098765",
        issuer_id="20601234567",
        issuer_name="SERVICIOS INDUSTRIALES S.A.C.",
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
    return build_canonical_erp_payload(record)


def test_transform_to_odoo_invoice_format(sample_canonical_payload):
    """Valida la transformación al modelo de asiento borrador (account.move) de Odoo."""
    odoo_data = transform_to_odoo_invoice(sample_canonical_payload)

    assert odoo_data["model"] == "account.move"
    assert odoo_data["method"] == "create"
    vals = odoo_data["values"]
    assert vals["move_type"] == "in_invoice"
    assert vals["ref"] == "F001-00098765"
    assert vals["partner_vat"] == "20601234567"
    assert "SPOT 12" in vals["payment_reference"]
    assert len(vals["invoice_line_ids"]) == 1
    assert vals["invoice_line_ids"][0]["price_unit"] == "1000.00"
    assert vals["invoice_line_ids"][0]["price_total"] == "1180.00"


def test_transform_to_odoo_credit_note(sample_canonical_payload):
    """Valida que una Nota de Crédito (07) se mapee a in_refund en Odoo."""
    sample_canonical_payload["document"]["sunat_type"] = "07"
    odoo_data = transform_to_odoo_invoice(sample_canonical_payload)
    assert odoo_data["values"]["move_type"] == "in_refund"


def test_transform_to_sap_b1_invoice_udfs(sample_canonical_payload):
    """Valida la transformación a PurchaseInvoices de SAP Business One con UDFs SPOT."""
    sap_data = transform_to_sap_b1_invoice(sample_canonical_payload)

    assert sap_data["DocType"] == "dDocument_Items"
    assert sap_data["CardCode"] == "P20601234567"
    assert sap_data["NumAtCard"] == "F001-00098765"
    assert sap_data["U_BKP_Detraccion"] == "Y"
    assert sap_data["U_BKP_TasaDetracc"] == "12.00"
    assert sap_data["U_BKP_MontoDetracc"] == "141.60"
    assert sap_data["U_BKP_NetoPagar"] == "1038.40"
    assert len(sap_data["DocumentLines"]) == 1
    assert sap_data["DocumentLines"][0]["LineTotal"] == 1000.00


def test_transform_to_siigo_invoice_retentions(sample_canonical_payload):
    """Valida la transformación a Factura de Compra de Siigo Cloud con retenciones."""
    siigo_data = transform_to_siigo_invoice(sample_canonical_payload)

    assert siigo_data["document"]["id"] == 24
    assert siigo_data["customer"]["identification"] == "20601234567"
    assert len(siigo_data["items"]) == 1
    assert siigo_data["items"][0]["price"] == "1000.00"
    assert len(siigo_data["retentions"]) == 1
    assert siigo_data["retentions"][0]["id"] == 4
    assert siigo_data["retentions"][0]["value"] == "141.60"


@pytest.mark.anyio
async def test_end_to_end_erp_webhook_contract_and_signature(db_session, sample_canonical_payload):
    """Simula el flujo completo de despacho con OutboxDispatcher y validación de contrato ERP mock."""
    secret = "whsec_test_erp_integration_secret"
    received_requests = []

    def mock_erp_receiver(request: httpx.Request) -> httpx.Response:
        sig_header = request.headers.get("X-CajaClara-Signature", "")
        payload_text = request.read().decode("utf-8")

        # 1. Validar firma criptográfica
        is_valid = verify_webhook_signature(payload_text, sig_header, secret, tolerance_seconds=300)
        assert is_valid is True

        # 2. Validar cabeceras y contrato
        assert request.headers.get("X-CajaClara-Event-Type") == "invoice.processed"
        received_requests.append(payload_text)

        # 3. Responder como Odoo (201 Created)
        return httpx.Response(201, json={"result": {"id": 88412, "state": "draft"}})

    transport = httpx.MockTransport(mock_erp_receiver)
    async with httpx.AsyncClient(transport=transport) as http_client:
        import json

        # Insertar evento outbox en BD real
        ev = OutboxEvent(
            event_type="invoice.processed",
            payload=json.dumps(sample_canonical_payload),
            status="PENDING",
        )
        db_session.add(ev)
        db_session.commit()
        ev_id = ev.id

        dispatcher = OutboxDispatcher(
            db_factory=lambda: db_session,
            http_client=http_client,
            target_url="https://odoo.empresa.com/webhooks/cajaclara",
            webhook_secret=secret,
        )

        processed = await dispatcher.process_batch()
        assert processed == 1

        updated_ev = db_session.query(OutboxEvent).filter(OutboxEvent.id == ev_id).first()
        assert updated_ev is not None
        assert updated_ev.status == "DELIVERED"
        assert updated_ev.processed_at is not None
        assert len(received_requests) == 1
