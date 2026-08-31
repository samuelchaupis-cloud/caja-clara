from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from caja_clara.api import app
from caja_clara.config import config
from caja_clara.database import get_db
from caja_clara.models import InvoiceRecord
from caja_clara.reports import generate_erp_csv, generate_sire_rce


def test_generate_sire_rce_format():
    """Valida la generación del formato plano SIRE / RCE oficial de SUNAT."""
    inv = InvoiceRecord(
        message_id="<msg01@test.com>",
        imap_uid=1,
        mailbox_account="test@user.com",
        sender_email="proveedor@empresa.com",
        received_date=datetime(2026, 8, 15, 10, 0, tzinfo=UTC),
        issue_date=datetime(2026, 8, 15, 0, 0, tzinfo=UTC),
        issuer_id="20601234567",
        issuer_name="PROVEEDOR S.A.C.",
        invoice_number="F001-000123",
        document_type="01",
        currency="PEN",
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        cdr_status="ACCEPTED",
        status="PROCESSED",
    )

    result = generate_sire_rce([inv])
    assert "20601234567|PROVEEDOR S.A.C.|01|F001|000123|15/08/2026|PEN|1000.00|180.00|1180.00|ACCEPTED|" in result


def test_generate_erp_csv_format():
    """Valida la exportación a CSV estructurado para sistemas contables."""
    inv = InvoiceRecord(
        message_id="<msg02@test.com>",
        imap_uid=2,
        mailbox_account="test@user.com",
        sender_email="proveedor@empresa.com",
        received_date=datetime(2026, 8, 20, 12, 0, tzinfo=UTC),
        issue_date=datetime(2026, 8, 20, 0, 0, tzinfo=UTC),
        issuer_id="20509876543",
        issuer_name="LOGISTICA GLOBAL S.A.",
        invoice_number="FC01-000045",
        document_type="07",
        currency="USD",
        subtotal=Decimal("500.00"),
        tax_amount=Decimal("90.00"),
        total_amount=Decimal("590.00"),
        detraction_amount=Decimal("0.00"),
        cdr_status="ACCEPTED",
        status="PROCESSED",
    )

    csv_str = generate_erp_csv([inv])
    assert "ID_Mensaje,Fecha_Recepcion,Fecha_Emision" in csv_str
    assert "LOGISTICA GLOBAL S.A." in csv_str
    assert "FC01-000045" in csv_str
    assert "590.00" in csv_str


def test_api_report_endpoints(db_session):
    """Valida los endpoints de exportación y los health probes en la API."""
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    # 1. Health Probes
    resp_live = client.get("/health/live")
    assert resp_live.status_code == 200
    assert resp_live.json()["status"] == "ok"

    resp_ready = client.get("/health/ready")
    assert resp_ready.status_code == 200
    assert resp_ready.json()["status"] == "ready"

    # 2. Endpoints protegidos sin API Key
    resp_sire_no_auth = client.get("/api/v1/reports/sire")
    assert resp_sire_no_auth.status_code == 403

    # 3. Endpoints con API Key válida
    headers = {"X-API-Key": config.api_key}
    resp_sire = client.get("/api/v1/reports/sire", headers=headers)
    assert resp_sire.status_code == 200
    assert "text/plain" in resp_sire.headers["content-type"]

    resp_csv = client.get("/api/v1/reports/export", headers=headers)
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]

    app.dependency_overrides.clear()
