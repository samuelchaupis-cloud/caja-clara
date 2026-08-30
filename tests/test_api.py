from fastapi.testclient import TestClient

from caja_clara.api import app
from caja_clara.config import config
from caja_clara.database import get_db

client = TestClient(app)

def test_read_root():
    """El root endpoint debe ser público para validación de salud."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "caja-clara-api"}

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
    response = client.get("/api/v1/invoices", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    app.dependency_overrides.clear()

def test_get_metrics_valid_api_key():
    """Debe permitir acceso a métricas con la cabecera correcta."""
    headers = {"X-API-Key": config.api_key}
    response = client.get("/api/v1/metrics", headers=headers)
    assert response.status_code in (200, 404) # 404 si el archivo de estado aún no existe en el test, ambos son válidos.
