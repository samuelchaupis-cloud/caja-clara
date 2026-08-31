"""
Módulo de observabilidad y métricas para Prometheus / OpenMetrics.
"""

from prometheus_client import REGISTRY, CollectorRegistry, Counter, Gauge, Histogram

# Métricas estándar de CajaClara
INVOICES_TOTAL = Counter(
    "cajaclara_invoices_total",
    "Total de comprobantes fiscales procesados por CajaClara",
    ["status", "document_type", "currency"],
)

PROCESSING_DURATION_SECONDS = Histogram(
    "cajaclara_processing_duration_seconds",
    "Duración de procesamiento y extracción de comprobantes en segundos",
    ["parser", "status"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

IMAP_CONNECTION_STATUS = Gauge(
    "cajaclara_imap_connection_status",
    "Estado actual de la conexión IMAP (1 = conectado, 0 = desconectado)",
)

DB_SIZE_BYTES = Gauge(
    "cajaclara_db_size_bytes",
    "Tamaño en bytes del archivo SQLite local",
)

OUTBOX_QUEUE_DEPTH = Gauge(
    "cajaclara_outbox_queue_depth",
    "Cantidad de eventos outbox encolados por estado",
    ["status"],
)


def get_metrics_registry() -> CollectorRegistry:
    """Retorna el registro global de métricas de Prometheus."""
    return REGISTRY
