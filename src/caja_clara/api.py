"""
API REST para consumo de datos financieros de CajaClara.
Construida con FastAPI y protegida por API Key.
"""
import os
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Security, Request
from fastapi.security.api_key import APIKeyHeader
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.status import HTTP_403_FORBIDDEN

from caja_clara.cli_monitor import get_status_data
from caja_clara.config import config
from caja_clara.database import get_db
from caja_clara.models import InvoiceRecord

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_api_key(api_key: str = Security(api_key_header)) -> str:
    """Valida que la petición incluya el API Key correcto."""
    if api_key == config.api_key:
        return api_key
    raise HTTPException(
        status_code=HTTP_403_FORBIDDEN, detail="Acceso denegado: API Key inválida o faltante"
    )

app = FastAPI(
    title="CajaClara API",
    description="API para la integración y consumo de facturas extraídas (IMAP a ERP).",
    version="1.0.0"
)

# Configurar templates usando ruta absoluta para que funcione desde cualquier CWD
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.get("/")
def get_dashboard(request: Request, db: Session = Depends(get_db)):
    """Renderiza el Dashboard Visual B2B."""
    metrics = get_status_data() or {}
    invoices = db.query(InvoiceRecord).order_by(InvoiceRecord.received_date.desc()).limit(100).all()
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "metrics": metrics,
            "invoices": invoices
        }
    )

@app.get("/health")
def read_root() -> dict[str, str]:
    return {"status": "ok", "service": "caja-clara-api"}

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

@app.get("/api/v1/metrics", dependencies=[Depends(get_api_key)])
def get_metrics() -> dict[str, Any]:
    """Devuelve el estado de salud y métricas del demonio."""
    data = get_status_data()
    if not data:
        raise HTTPException(status_code=404, detail="Métricas no disponibles aún")
    return data
