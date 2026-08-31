from datetime import UTC, datetime

from fastapi.testclient import TestClient

from caja_clara.api import app
from caja_clara.config import config
from caja_clara.database import get_db
from caja_clara.models import InvoiceRecord

client = TestClient(app)


def test_read_root():
    """El root endpoint de health debe ser público para validación de salud."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "caja-clara-api"}


def test_get_dashboard(db_session):
    """El dashboard debe renderizar correctamente HTML público."""
    app.dependency_overrides[get_db] = lambda: db_session
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    app.dependency_overrides.clear()


def test_get_prometheus_metrics():
    """El endpoint /metrics debe responder con texto OpenMetrics / Prometheus."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    assert "cajaclara_" in response.text


def test_get_invoices_no_api_key():
    """Debe rechazar peticiones sin la cabecera X-API-Key."""
    response = client.get("/api/v1/invoices")
    assert response.status_code == 403
    assert "Acceso denegado" in response.json()["detail"]


def test_get_invoices_wrong_api_key():
    """Debe rechazar peticiones con una cabecera X-API-Key incorrecta."""
    headers = {"X-API-Key": "llave-equivocada-123"}
    response = client.get("/api/v1/invoices", headers=headers)
    assert response.status_code == 403
    assert "Acceso denegado" in response.json()["detail"]


def test_get_invoices_valid_api_key(db_session):
    """Debe permitir acceso con la cabecera correcta e inyectar BD de prueba."""
    app.dependency_overrides[get_db] = lambda: db_session
    headers = {"X-API-Key": config.api_key}
    response = client.get("/api/v1/invoices?status=PROCESSED", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    app.dependency_overrides.clear()


def test_get_invoice_by_message_id_success_and_404(db_session):
    """Debe retornar una factura por su message_id o 404 si no existe."""
    app.dependency_overrides[get_db] = lambda: db_session
    headers = {"X-API-Key": config.api_key}

    # 1. Caso 404
    resp_404 = client.get("/api/v1/invoices/non_existent_id", headers=headers)
    assert resp_404.status_code == 404

    # 2. Caso Exitoso
    inv = InvoiceRecord(
        message_id="<msg_test_123@domain.com>",
        imap_uid=99,
        mailbox_account="test@user.com",
        sender_email="prov@test.com",
        received_date=datetime.now(UTC),
        status="PROCESSED",
    )
    db_session.add(inv)
    db_session.commit()

    resp_ok = client.get("/api/v1/invoices/<msg_test_123@domain.com>", headers=headers)
    assert resp_ok.status_code == 200
    assert resp_ok.json()["message_id"] == "<msg_test_123@domain.com>"

    app.dependency_overrides.clear()


def test_get_metrics_valid_api_key():
    """Debe permitir acceso a métricas con la cabecera correcta."""
    headers = {"X-API-Key": config.api_key}
    response = client.get("/api/v1/metrics", headers=headers)
    assert response.status_code in (200, 404)
