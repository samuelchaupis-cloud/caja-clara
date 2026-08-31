"""
API REST para consumo de datos financieros de CajaClara.
Construida con FastAPI y protegida por API Key.
"""

import os
import secrets
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security
from fastapi.responses import PlainTextResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi.templating import Jinja2Templates
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy.orm import Session
from starlette.status import HTTP_403_FORBIDDEN

from caja_clara.cli_monitor import get_status_data
from caja_clara.config import config
from caja_clara.database import get_db
from caja_clara.metrics import (
    LAST_SNAPSHOT_TIMESTAMP,
    LITESTREAM_LAG_SECONDS,
    REPLICATION_STATUS,
    REPLICATION_SYNC_ERRORS_TOTAL,
    get_metrics_registry,
)
from caja_clara.models import InvoiceRecord
from caja_clara.reports import generate_erp_csv, generate_sire_rce

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def get_api_key(api_key: str = Security(api_key_header)) -> str:
    """Valida que la petición incluya el API Key correcto."""
    if api_key and secrets.compare_digest(api_key, config.api_key):
        return api_key
    raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Acceso denegado: API Key inválida o faltante")


app = FastAPI(title="CajaClara API", description="API para la integración y consumo de facturas extraídas (IMAP a ERP).", version="1.1.0")

# Configurar templates usando ruta absoluta para que funcione desde cualquier CWD
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@app.get("/")
def get_dashboard(request: Request, db: Session = Depends(get_db)):
    """Renderiza el Dashboard Visual B2B."""
    metrics = get_status_data() or {}
    invoices = db.query(InvoiceRecord).order_by(InvoiceRecord.received_date.desc()).limit(100).all()
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"metrics": metrics, "invoices": invoices})


@app.get("/health")
@app.get("/health/live")
def read_root() -> dict[str, str]:
    """Liveness probe para balanceadores y Docker."""
    return {"status": "ok", "service": "caja-clara-api"}


@app.get("/health/ready")
def readiness_probe(db: Session = Depends(get_db)) -> dict[str, str]:
    """Readiness probe que valida conexión real con SQLite (Sanitizado CWE-209)."""
    try:
        db.execute(InvoiceRecord.__table__.select().limit(1))
        return {"status": "ready", "database": "connected"}
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/health/replication")
def get_replication_health() -> dict[str, Any]:
    """Endpoint público de telemetría de replicación continua y lag de Litestream."""
    try:
        lag_val = LITESTREAM_LAG_SECONDS.labels(replica="primary", storage_provider="s3")._value.get()
        lag = float(lag_val) if lag_val is not None else 0.0
    except Exception:
        lag = 0.0

    try:
        status_val = REPLICATION_STATUS.labels(replica="primary", storage_provider="s3")._value.get()
        is_synced = status_val == 1.0 and lag < 10.0
    except Exception:
        is_synced = False

    try:
        last_snap = LAST_SNAPSHOT_TIMESTAMP.labels(replica="primary", storage_provider="s3")._value.get() or 0.0
    except Exception:
        last_snap = 0.0

    try:
        sync_err = sum(
            REPLICATION_SYNC_ERRORS_TOTAL.labels(replica="primary", error_type=et)._value.get()
            for et in ("network_timeout", "http_5xx", "auth_error")
        )
    except Exception:
        sync_err = 0

    return {
        "status": "synchronized" if is_synced else "degraded",
        "replication_enabled": bool(config.litestream_bucket),
        "lag_seconds": round(lag, 3),
        "last_snapshot_timestamp": int(last_snap),
        "sync_errors_total": int(sync_err),
        "storage_provider": "s3" if config.litestream_bucket else "none",
    }


@app.get("/api/v1/health/replica", dependencies=[Depends(get_api_key)])
def get_detailed_replica_health() -> dict[str, Any]:
    """Endpoint administrativo protegido para auditoría de réplicas en Cloudflare R2 / S3."""
    health_data = get_replication_health()
    health_data["endpoint"] = config.litestream_endpoint or "none"
    health_data["bucket"] = config.litestream_bucket or "none"
    return health_data


@app.get("/metrics", response_class=PlainTextResponse)
def get_prometheus_metrics():
    """Endpoint de telemetría y métricas para scraping con Prometheus / OpenMetrics."""
    registry = get_metrics_registry()
    return PlainTextResponse(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/v1/invoices", dependencies=[Depends(get_api_key)])
def get_invoices(skip: int = 0, limit: int = 100, status: str | None = None, db: Session = Depends(get_db)):
    """Devuelve la lista de facturas procesadas."""
    query = db.query(InvoiceRecord)
    if status:
        query = query.filter(InvoiceRecord.status == status)

    records = query.offset(skip).limit(limit).all()
    return records


@app.get("/api/v1/invoices/{message_id}", dependencies=[Depends(get_api_key)])
def get_invoice_by_message_id(message_id: str, db: Session = Depends(get_db)):
    """Devuelve una factura específica buscando por su message_id."""
    record = db.query(InvoiceRecord).filter(InvoiceRecord.message_id == message_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return record


@app.get("/api/v1/reports/sire", dependencies=[Depends(get_api_key)])
def export_sire_report(db: Session = Depends(get_db)):
    """Descarga el reporte oficial del Registro de Compras Electrónico (SIRE / RCE - SUNAT)."""
    invoices = db.query(InvoiceRecord).order_by(InvoiceRecord.received_date.asc()).all()
    content = generate_sire_rce(invoices)
    return PlainTextResponse(
        content=content, media_type="text/plain; charset=utf-8", headers={"Content-Disposition": "attachment; filename=sire_compras_rce.txt"}
    )


@app.get("/api/v1/reports/export", dependencies=[Depends(get_api_key)])
def export_erp_csv(db: Session = Depends(get_db)):
    """Descarga un archivo CSV estructurado para importación en ERPs (Concar, Siigo, Excel)."""
    invoices = db.query(InvoiceRecord).order_by(InvoiceRecord.received_date.asc()).all()
    content = generate_erp_csv(invoices)
    return Response(
        content=content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=facturas_cajaclara.csv"}
    )


@app.get("/api/v1/metrics", dependencies=[Depends(get_api_key)])
def get_metrics() -> dict[str, Any]:
    """Devuelve el estado de salud y métricas del demonio en formato JSON."""
    data = get_status_data()
    if not data:
        raise HTTPException(status_code=404, detail="Métricas no disponibles aún")
    return data
