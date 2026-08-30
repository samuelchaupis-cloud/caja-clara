"""
API REST para consumo de datos financieros de CajaClara.
Construida con FastAPI.
"""
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from caja_clara.database import get_db
from caja_clara.models import InvoiceRecord
from caja_clara.cli_monitor import get_status_data

app = FastAPI(
    title="CajaClara API",
    description="API para la integración y consumo de facturas extraídas (IMAP a ERP).",
    version="1.0.0"
)

@app.get("/")
def read_root() -> Dict[str, str]:
    return {"status": "ok", "service": "caja-clara-api"}

@app.get("/api/v1/invoices")
def get_invoices(skip: int = 0, limit: int = 100, status: str | None = None, db: Session = Depends(get_db)):
    """Devuelve la lista de facturas procesadas."""
    query = db.query(InvoiceRecord)
    if status:
        query = query.filter(InvoiceRecord.status == status)
        
    records = query.offset(skip).limit(limit).all()
    return records

@app.get("/api/v1/invoices/{message_id}")
def get_invoice_by_message_id(message_id: str, db: Session = Depends(get_db)):
    """Devuelve una factura específica buscando por su message_id."""
    record = db.query(InvoiceRecord).filter(InvoiceRecord.message_id == message_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return record

@app.get("/api/v1/metrics")
def get_metrics() -> Dict[str, Any]:
    """Devuelve el estado de salud y métricas del demonio."""
    data = get_status_data()
    if not data:
        raise HTTPException(status_code=404, detail="Métricas no disponibles aún")
    return data
