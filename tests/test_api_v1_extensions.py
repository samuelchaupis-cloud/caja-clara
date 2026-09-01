"""
Pruebas de integración y contratos REST para las extensiones de la Fase 13:
Ledger Contable, Consola DLQ y Telemetría en Tiempo Real.
Ejecutadas contra SQLite en memoria real bajo el Protocolo Supremo de Calidad.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from caja_clara.api import app
from caja_clara.config import config
from caja_clara.database import get_db
from caja_clara.models import Base, InvoiceRecord, OutboxEvent


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield testing_session_local
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"X-API-Key": config.api_key}


def test_auth_protection_on_new_endpoints(client):
    """Verifica que todos los nuevos endpoints rechacen peticiones sin API Key con HTTP 403."""
    res_ledger = client.get("/api/v1/ledger")
    assert res_ledger.status_code == 403

    res_dlq = client.get("/api/v1/dlq/events")
    assert res_dlq.status_code == 403

    res_replay = client.post("/api/v1/dlq/replay/1")
    assert res_replay.status_code == 403

    res_batch = client.post("/api/v1/dlq/replay-all")
    assert res_batch.status_code == 403

    res_telem = client.get("/api/v1/telemetry/live")
    assert res_telem.status_code == 403


def test_ledger_empty_database(client, test_db, auth_headers):
    """Verifica que el ledger devuelva listas vacías y totales en 0.00 cuando no hay datos."""
    res = client.get("/api/v1/ledger", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["pagination"]["total_records"] == 0
    assert data["pagination"]["total_pages"] == 1
    assert data["summary"]["total_subtotal_pen"] == "0.00"
    assert data["summary"]["total_tax_pen"] == "0.00"
    assert data["summary"]["total_amount_pen"] == "0.00"
    assert data["summary"]["total_detractions_pen"] == "0.00"
    assert data["summary"]["total_amount_usd"] == "0.00"


def test_ledger_filtering_and_exact_decimal_summary(client, test_db, auth_headers):
    """Verifica filtrado multidimensional y cálculo exacto de sumatorias contables sin floats."""
    session = test_db()
    now = datetime.now(UTC)

    # Inserción de fixtures
    inv1 = InvoiceRecord(
        message_id="<msg-001@test.com>",
        imap_uid=101,
        mailbox_account="facturas@empresa.com",
        sender_email="proveedor1@sunat.gob.pe",
        received_date=now,
        document_type="01",
        issuer_id="20100000001",
        issuer_name="PROVEEDOR UNO S.A.C.",
        invoice_number="F001-0001",
        issue_date=now,
        currency="PEN",
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        detraction_amount=Decimal("141.60"),
        detraction_rate=Decimal("12.00"),
        cdr_status="ACCEPTED",
        status="PROCESSED",
    )
    inv2 = InvoiceRecord(
        message_id="<msg-002@test.com>",
        imap_uid=102,
        mailbox_account="facturas@empresa.com",
        sender_email="proveedor2@sunat.gob.pe",
        received_date=now,
        document_type="03",
        issuer_id="20200000002",
        issuer_name="BODEGA DOS E.I.R.L.",
        invoice_number="B001-0050",
        issue_date=now,
        currency="PEN",
        subtotal=Decimal("200.00"),
        tax_amount=Decimal("36.00"),
        total_amount=Decimal("236.00"),
        detraction_amount=None,
        detraction_rate=None,
        cdr_status="REJECTED",
        status="PROCESSED",
    )
    inv3 = InvoiceRecord(
        message_id="<msg-003@test.com>",
        imap_uid=103,
        mailbox_account="facturas@empresa.com",
        sender_email="proveedor3@usacloud.com",
        received_date=now,
        document_type="01",
        issuer_id="99999999999",
        issuer_name="GLOBAL CLOUD INC",
        invoice_number="INV-2026-99",
        issue_date=now,
        currency="USD",
        subtotal=Decimal("500.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("500.00"),
        detraction_amount=None,
        detraction_rate=None,
        cdr_status="ACCEPTED",
        status="PROCESSED",
    )
    session.add_all([inv1, inv2, inv3])
    session.commit()
    session.close()

    # 1. Consulta general
    res = client.get("/api/v1/ledger", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["pagination"]["total_records"] == 3
    assert data["summary"]["total_subtotal_pen"] == "1200.00"
    assert data["summary"]["total_tax_pen"] == "216.00"
    assert data["summary"]["total_amount_pen"] == "1416.00"
    assert data["summary"]["total_detractions_pen"] == "141.60"
    assert data["summary"]["total_amount_usd"] == "500.00"

    # 2. Filtro por tipo de comprobante 01
    res_01 = client.get("/api/v1/ledger?document_type=01", headers=auth_headers)
    assert res_01.status_code == 200
    data_01 = res_01.json()
    assert data_01["pagination"]["total_records"] == 2
    assert all(item["document_type"] == "01" for item in data_01["items"])

    # 3. Filtro por detracción SPOT (has_spot=true)
    res_spot = client.get("/api/v1/ledger?has_spot=true", headers=auth_headers)
    assert res_spot.status_code == 200
    data_spot = res_spot.json()
    assert data_spot["pagination"]["total_records"] == 1
    assert data_spot["items"][0]["invoice_number"] == "F001-0001"

    # 4. Filtro por estado de CDR (cdr_status=REJECTED)
    res_rej = client.get("/api/v1/ledger?cdr_status=REJECTED", headers=auth_headers)
    assert res_rej.status_code == 200
    data_rej = res_rej.json()
    assert data_rej["pagination"]["total_records"] == 1
    assert data_rej["items"][0]["invoice_number"] == "B001-0050"


def test_dlq_listing_and_replaying(client, test_db, auth_headers):
    """Verifica operaciones atómicas de inspección y reintento en Dead Letter Queue."""
    session = test_db()
    ev1 = OutboxEvent(
        event_type="fiscal.alert.cdr_rejected",
        payload='{"invoice": "F001-1"}',
        status="DEAD_LETTER",
        retry_count=5,
        error_detail="Timeout HTTP 504",
    )
    ev2 = OutboxEvent(
        event_type="fiscal.alert.spot_mismatch",
        payload='{"invoice": "F001-2"}',
        status="DEAD_LETTER",
        retry_count=5,
        error_detail="Error de autenticación 401",
    )
    ev3 = OutboxEvent(
        event_type="invoice.processed",
        payload='{"invoice": "F001-3"}',
        status="DELIVERED",
        retry_count=1,
    )
    session.add_all([ev1, ev2, ev3])
    session.commit()
    ev1_id = ev1.id
    session.close()

    # 1. Listar DLQ
    res_list = client.get("/api/v1/dlq/events?status=DEAD_LETTER", headers=auth_headers)
    assert res_list.status_code == 200
    data_list = res_list.json()
    assert len(data_list["events"]) == 2
    assert data_list["total_dead_letters"] == 2
    assert data_list["total_pending"] == 0

    # 2. Replay individual ev1
    res_rep = client.post(f"/api/v1/dlq/replay/{ev1_id}", headers=auth_headers)
    assert res_rep.status_code == 200
    data_rep = res_rep.json()
    assert data_rep["status"] == "replayed"
    assert data_rep["event_id"] == ev1_id
    assert data_rep["new_status"] == "PENDING"

    # Verificar que no permite reintentar un evento que ya no está en DEAD_LETTER
    res_rep_again = client.post(f"/api/v1/dlq/replay/{ev1_id}", headers=auth_headers)
    assert res_rep_again.status_code == 400

    # Verificar 404 para ID inexistente
    res_rep_404 = client.post("/api/v1/dlq/replay/99999", headers=auth_headers)
    assert res_rep_404.status_code == 404

    # 3. Replay batch para los restantes
    res_batch = client.post("/api/v1/dlq/replay-all", headers=auth_headers)
    assert res_batch.status_code == 200
    data_batch = res_batch.json()
    assert data_batch["status"] == "batch_replayed"
    assert data_batch["replayed_count"] == 1  # Solo quedaba ev2


def test_live_telemetry_endpoint(client, test_db, auth_headers):
    """Verifica que el endpoint de telemetría devuelva la estructura de observabilidad requerida."""
    res = client.get("/api/v1/telemetry/live", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "timestamp" in data
    assert "process" in data
    assert "invoices" in data
    assert "outbox_dlq" in data
    assert "replication" in data
    assert "mailboxes" in data
    assert data["replication"]["storage_provider"] == "s3"
    assert isinstance(data["replication"]["lag_seconds"], float)
    assert isinstance(data["mailboxes"], list)
