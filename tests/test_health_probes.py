from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from caja_clara.api import app
from caja_clara.config import config
from caja_clara.database import get_db
from caja_clara.metrics import LAST_SNAPSHOT_TIMESTAMP, LITESTREAM_LAG_SECONDS, REPLICATION_STATUS

client = TestClient(app)


def test_health_live_endpoint():
    """Valida que /health/live sea público y responda 200 en memoria."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "caja-clara-api"}


def test_health_ready_success(db_session):
    """Valida que /health/ready responda 200 cuando SQLite está conectado."""
    app.dependency_overrides[get_db] = lambda: db_session
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "connected"}
    app.dependency_overrides.clear()


def test_health_ready_sanitized_on_failure():
    """Valida que /health/ready responda 503 sanitizado sin exponer stack traces ni rutas (CWE-209)."""
    mock_failing_db = MagicMock()
    mock_failing_db.execute.side_effect = RuntimeError("disk I/O error at /internal/secret/path/cajaclarad.db")

    app.dependency_overrides[get_db] = lambda: mock_failing_db
    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    # Certificar que la ruta interna sensible NO se filtró
    assert "/internal/secret/path" not in response.text
    app.dependency_overrides.clear()


def test_health_replication_metrics():
    """Valida que /health/replication emita telemetría de lag en segundos."""
    LITESTREAM_LAG_SECONDS.labels(replica="primary", storage_provider="s3").set(0.450)
    REPLICATION_STATUS.labels(replica="primary", storage_provider="s3").set(1.0)
    LAST_SNAPSHOT_TIMESTAMP.labels(replica="primary", storage_provider="s3").set(1725123456)

    response = client.get("/health/replication")
    assert response.status_code == 200
    data = response.json()
    assert data["lag_seconds"] == 0.450
    assert data["status"] in ("synchronized", "degraded")
    assert data["last_snapshot_timestamp"] == 1725123456


def test_health_replica_auth_protection():
    """Valida que /api/v1/health/replica requiera autenticación con X-API-Key."""
    # 1. Sin API Key -> 403
    res_no_auth = client.get("/api/v1/health/replica")
    assert res_no_auth.status_code == 403

    # 2. Con API Key válida -> 200
    headers = {"X-API-Key": config.api_key}
    res_auth = client.get("/api/v1/health/replica", headers=headers)
    assert res_auth.status_code == 200
    assert "endpoint" in res_auth.json()
    assert "bucket" in res_auth.json()
