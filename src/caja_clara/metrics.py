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

OUTBOX_DELIVERY_DURATION_SECONDS = Histogram(
    "cajaclara_outbox_delivery_duration_seconds",
    "Latencia de entrega de eventos outbox hacia endpoints externos en segundos",
    ["event_type", "status"],
    buckets=[0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

OUTBOX_DELIVERY_RETRIES_TOTAL = Counter(
    "cajaclara_outbox_retries_total",
    "Total de reintentos de despacho de eventos outbox",
    ["event_type"],
)

OUTBOX_EVENTS_TOTAL = Counter(
    "cajaclara_outbox_events_total",
    "Total acumulado de eventos outbox despachados por estado final",
    ["event_type", "status"],
)

FISCAL_ALERTS_TOTAL = Counter(
    "cajaclara_fiscal_alerts_total",
    "Total de anomalías y alertas fiscales detectadas durante la extracción",
    ["alert_type", "severity"],
)


def get_metrics_registry() -> CollectorRegistry:
    """Retorna el registro global de métricas de Prometheus."""
    return REGISTRY
